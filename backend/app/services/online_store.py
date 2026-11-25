"""PostgreSQL is authoritative; cache keys include a committed DB revision."""
import json
import logging
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import delete, event, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.feature_store import FeatureDefinition, FeatureValueOnline

logger = logging.getLogger(__name__)


class PostgresOnlineStore:
    def get_online_features(self, entity_keys, feature_id_map, db):
        values = {ek: {name: None for name in feature_id_map.values()} for ek in entity_keys}
        if entity_keys and feature_id_map:
            rows = db.query(FeatureValueOnline).filter(
                FeatureValueOnline.entity_key.in_(entity_keys),
                FeatureValueOnline.feature_id.in_(feature_id_map),
            ).all()
            for row in rows:
                values[row.entity_key][feature_id_map[row.feature_id]] = row.value
        return values

    def write_online_features(self, records, db, replace_feature_ids=()):
        ids = {r["feature_id"] for r in records} | set(replace_feature_ids)
        revisions = {}
        # Stable lock order prevents concurrent multi-feature writers deadlocking.
        for feature_id in sorted(ids, key=str):
            revisions[feature_id] = db.execute(
                update(FeatureDefinition).where(FeatureDefinition.id == feature_id)
                .values(online_revision=FeatureDefinition.online_revision + 1)
                .returning(FeatureDefinition.online_revision)).scalar_one()
        if replace_feature_ids:
            db.execute(delete(FeatureValueOnline).where(FeatureValueOnline.feature_id.in_(replace_feature_ids)))
        accepted = []
        for record in records:
            row = dict(record)
            row["event_time"] = row.get("event_time") or datetime.now(timezone.utc)
            row["updated_at"] = datetime.now(timezone.utc)
            stmt = insert(FeatureValueOnline).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["entity_key", "feature_id"],
                set_={key: getattr(stmt.excluded, key) for key in ("value", "event_time", "updated_at")},
                where=(FeatureValueOnline.event_time.is_(None) |
                       (stmt.excluded.event_time >= FeatureValueOnline.event_time)),
            ).returning(FeatureValueOnline.entity_key)
            if db.execute(stmt).first():
                accepted.append(row)
        # Publish only after a successful commit; rollback discards this queue.
        db.info.setdefault("online_publications", []).append((self, accepted, revisions))
        return len(accepted)

    def publish(self, records, revisions):
        pass


class RedisOnlineStore(PostgresOnlineStore):
    def __init__(self, redis_url):
        import redis
        self._client = redis.from_url(redis_url, decode_responses=True,
                                      socket_timeout=1, socket_connect_timeout=1)

    @staticmethod
    def key(feature_id, revision, entity_key):
        return f"fs:v2:{feature_id}:{revision}:{entity_key}"

    def get_online_features(self, entity_keys, feature_id_map, db):
        if not entity_keys or not feature_id_map:
            return super().get_online_features(entity_keys, feature_id_map, db)
        revisions = dict(db.query(FeatureDefinition.id, FeatureDefinition.online_revision)
                         .filter(FeatureDefinition.id.in_(feature_id_map)).all())
        coordinates = [(ek, fid, name) for ek in entity_keys for fid, name in feature_id_map.items()]
        try:
            cached = self._client.mget([self.key(fid, revisions.get(fid, 0), ek)
                                        for ek, fid, _ in coordinates])
            values = {ek: {} for ek in entity_keys}
            missing = []
            for (ek, fid, name), value in zip(coordinates, cached):
                if value is None:
                    missing.append((ek, fid, name))
                else:
                    values[ek][name] = json.loads(value)
            if missing:
                durable = super().get_online_features(entity_keys, feature_id_map, db)
                for ek, fid, name in missing:
                    values[ek][name] = durable[ek][name]
            return values
        except Exception:
            logger.warning("Redis read unavailable; using PostgreSQL", exc_info=True)
            return super().get_online_features(entity_keys, feature_id_map, db)

    def publish(self, records, revisions):
        try:
            with self._client.pipeline() as pipe:
                for row in records:
                    pipe.set(self.key(row["feature_id"], revisions[row["feature_id"]], row["entity_key"]),
                             json.dumps(row["value"]), ex=settings.redis_ttl_seconds)
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
