"""PostgreSQL is authoritative; cache keys include a committed DB revision."""

import json
import logging
from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import settings
from app.db.models.feature_store import FeatureDefinition, FeatureValueOnline
from app.services.batches import unique_events
from fastapi import HTTPException
from sqlalchemy import delete, event, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PostgresOnlineStore:
    def get_online_features(self, entity_keys, feature_id_map, db):
        values = {ek: {name: None for name in feature_id_map.values()} for ek in entity_keys}
        if entity_keys and feature_id_map:
            rows = (
                db.query(
                    FeatureValueOnline.entity_key,
                    FeatureValueOnline.feature_id,
                    FeatureValueOnline.value,
                )
                .filter(
                    FeatureValueOnline.entity_key.in_(entity_keys),
                    FeatureValueOnline.feature_id.in_(feature_id_map),
                )
                .all()
            )
            for row in rows:
                values[row.entity_key][feature_id_map[row.feature_id]] = row.value
        return values

    def write_online_features(
        self, records, db, replace_feature_ids=(), *, advance_revision=True, publish=True
    ):
        ids = {r["feature_id"] for r in records} | set(replace_feature_ids)
        revisions = {}
        if ids and advance_revision:
            db.query(FeatureDefinition.id).filter(FeatureDefinition.id.in_(ids)).order_by(
                FeatureDefinition.id
            ).with_for_update().all()
            revisions = dict(
                db.execute(
                    update(FeatureDefinition)
                    .where(FeatureDefinition.id.in_(ids))
                    .values(online_revision=FeatureDefinition.online_revision + 1)
                    .returning(FeatureDefinition.id, FeatureDefinition.online_revision)
                ).all()
            )
        if replace_feature_ids:
            db.execute(
                delete(FeatureValueOnline).where(
                    FeatureValueOnline.feature_id.in_(replace_feature_ids)
                )
            )
        now = datetime.now(UTC)
        normalized = [
            {**row, "event_time": row.get("event_time") or now, "updated_at": now}
            for row in records
        ]
        events = unique_events(normalized)
        latest = {}
        for row in events:
            key = row["entity_key"], row["feature_id"]
            if key not in latest or row["event_time"] > latest[key]["event_time"]:
                latest[key] = row
        # Collapsing several events to the newest value must not hide a conflict
        # against the currently stored timestamp, including online-only ingestion.
        if len(events) > len(latest):
            keys = list(latest)
            existing = {}
            for offset in range(0, len(keys), settings.materialization_batch_size):
                existing.update(
                    {
                        (row.entity_key, row.feature_id): row
                        for row in db.query(
                            FeatureValueOnline.entity_key,
                            FeatureValueOnline.feature_id,
                            FeatureValueOnline.event_time,
                            FeatureValueOnline.value,
                        )
                        .filter(
                            tuple_(
                                FeatureValueOnline.entity_key, FeatureValueOnline.feature_id
                            ).in_(keys[offset : offset + settings.materialization_batch_size])
                        )
                        .all()
                    }
                )
            for row in events:
                previous = existing.get((row["entity_key"], row["feature_id"]))
                if (
                    previous
                    and previous.event_time == row["event_time"]
                    and previous.value != row["value"]
                ):
                    raise HTTPException(
                        409, "Conflicting online replay at the same event timestamp"
                    )
        accepted = []
        rows = list(latest.values())
        for offset in range(0, len(rows), settings.materialization_batch_size):
            batch = rows[offset : offset + settings.materialization_batch_size]
            statement = insert(FeatureValueOnline).values(batch)
            changed = set(
                db.execute(
                    statement.on_conflict_do_update(
                        index_elements=["entity_key", "feature_id"],
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in ("value", "event_time", "updated_at")
                        },
                        where=(
                            FeatureValueOnline.event_time.is_(None)
                            | (statement.excluded.event_time > FeatureValueOnline.event_time)
                        ),
                    ).returning(FeatureValueOnline.entity_key, FeatureValueOnline.feature_id)
                ).all()
            )
            unchanged = [
                row for row in batch if (row["entity_key"], row["feature_id"]) not in changed
            ]
            if unchanged:
                existing = {
                    (row.entity_key, row.feature_id): row
                    for row in db.query(
                        FeatureValueOnline.entity_key,
                        FeatureValueOnline.feature_id,
                        FeatureValueOnline.event_time,
                        FeatureValueOnline.value,
                    )
                    .filter(
                        tuple_(FeatureValueOnline.entity_key, FeatureValueOnline.feature_id).in_(
                            [(row["entity_key"], row["feature_id"]) for row in unchanged]
                        )
                    )
                    .all()
                }
                for row in unchanged:
                    previous = existing[row["entity_key"], row["feature_id"]]
                    if previous.event_time == row["event_time"] and previous.value != row["value"]:
                        raise HTTPException(
                            409, "Conflicting online replay at the same event timestamp"
                        )
            accepted.extend(
                row for row in batch if (row["entity_key"], row["feature_id"]) in changed
            )
        if publish:
            db.info.setdefault("online_publications", []).append((self, accepted, revisions))
        return len(accepted)

    def publish(self, records, revisions):
        pass


class RedisOnlineStore(PostgresOnlineStore):
    def __init__(self, redis_url):
        import redis

        self._client = redis.from_url(
            redis_url, decode_responses=True, socket_timeout=1, socket_connect_timeout=1
        )

    @staticmethod
    def key(feature_id, revision, entity_key):
        return f"fs:v2:{feature_id}:{revision}:{entity_key}"

    def get_online_features(self, entity_keys, feature_id_map, db):
        if not entity_keys or not feature_id_map:
            return super().get_online_features(entity_keys, feature_id_map, db)
        revisions = dict(
            db.query(FeatureDefinition.id, FeatureDefinition.online_revision)
            .filter(FeatureDefinition.id.in_(feature_id_map))
            .all()
        )
        coordinates = [
            (ek, fid, name) for ek in entity_keys for fid, name in feature_id_map.items()
        ]
        try:
            cached = self._client.mget(
                [self.key(fid, revisions.get(fid, 0), ek) for ek, fid, _ in coordinates]
            )
            values = {ek: {} for ek in entity_keys}
            missing = []
            for (ek, fid, name), value in zip(coordinates, cached):
                if value is None:
                    missing.append((ek, fid, name))
                else:
                    values[ek][name] = json.loads(value)
            if missing:
                durable = super().get_online_features(entity_keys, feature_id_map, db)
                with self._client.pipeline() as pipe:
                    for ek, fid, name in missing:
                        values[ek][name] = durable[ek][name]
                        # A concurrent writer advances the DB revision; this key then becomes unreachable.
                        pipe.set(
                            self.key(fid, revisions.get(fid, 0), ek),
                            json.dumps(durable[ek][name]),
                            ex=settings.redis_ttl_seconds,
                        )
                    pipe.execute()
            return values
        except Exception:
            logger.warning("Redis read unavailable; using PostgreSQL", exc_info=True)
            return super().get_online_features(entity_keys, feature_id_map, db)

    def publish(self, records, revisions):
        try:
            with self._client.pipeline() as pipe:
                for row in records:
                    pipe.set(
                        self.key(
                            row["feature_id"], revisions[row["feature_id"]], row["entity_key"]
                        ),
                        json.dumps(row["value"]),
                        ex=settings.redis_ttl_seconds,
                    )
                pipe.execute()
        except Exception:
            # DB revision already advanced: old cache values are unreachable.
            logger.warning("Cache publication failed; reads fall back to DB", exc_info=True)


@event.listens_for(Session, "after_commit")
def publish_committed_values(session):
    for store, records, revisions in session.info.pop("online_publications", []):
        store.publish(records, revisions)


@event.listens_for(Session, "after_rollback")
def discard_rolled_back_values(session):
    session.info.pop("online_publications", None)


@lru_cache(maxsize=8)
def _store(backend, redis_url):
    return RedisOnlineStore(redis_url) if backend == "redis" else PostgresOnlineStore()


def get_online_store():
    return _store(settings.online_store_backend, settings.redis_url)
