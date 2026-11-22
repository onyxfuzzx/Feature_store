import logging
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models.feature_store import FeatureValueOnline

logger = logging.getLogger(__name__)


class BaseOnlineStore(ABC):
    @abstractmethod
    def get_online_features(
        self,
        entity_keys: List[str],
        feature_id_map: Dict[UUID, str],  # feature_id -> feature_name
        db: Session,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """
        Retrieve latest online feature values for the given entities and features.
        Returns: {entity_key: {feature_name: value}}
        """
        pass

    @abstractmethod
    def write_online_features(
        self,
        records: List[Dict[str, Any]],  # [{entity_key, feature_id, value, event_time}]
        db: Session,
    ) -> int:
        """
        Write feature values to the online serving store.
        """
        pass


class PostgresOnlineStore(BaseOnlineStore):
    def get_online_features(
        self,
        entity_keys: List[str],
        feature_id_map: Dict[UUID, str],
        db: Session,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        feature_ids = list(feature_id_map.keys())
        result_map: Dict[str, Dict[str, Optional[str]]] = {
            ek: {f_name: None for f_name in feature_id_map.values()}
            for ek in entity_keys
        }

        if not entity_keys or not feature_ids:
            return result_map

        rows = (
            db.query(FeatureValueOnline)
            .filter(
                FeatureValueOnline.entity_key.in_(entity_keys),
                FeatureValueOnline.feature_id.in_(feature_ids),
            )
            .all()
        )

        for row in rows:
            feat_name = feature_id_map.get(row.feature_id)
            if feat_name and row.entity_key in result_map:
                result_map[row.entity_key][feat_name] = row.value

        return result_map

    def write_online_features(
        self,
        records: List[Dict[str, Any]],
        db: Session,
    ) -> int:
        now = datetime.utcnow()
        written = 0
        for rec in records:
            entity_key = rec["entity_key"]
            feature_id = rec["feature_id"]
            value = rec.get("value")
            event_time = rec.get("event_time") or now

            entry = (
                db.query(FeatureValueOnline)
                .filter(
                    FeatureValueOnline.entity_key == entity_key,
                    FeatureValueOnline.feature_id == feature_id,
                )
                .first()
            )
            if entry:
                entry.value = value
                entry.event_time = event_time
                entry.updated_at = now
            else:
                entry = FeatureValueOnline(
                    entity_key=entity_key,
                    feature_id=feature_id,
                    value=value,
                    event_time=event_time,
                    updated_at=now,
                )
                db.add(entry)
            written += 1
        return written


class RedisOnlineStore(BaseOnlineStore):
    """
    High-performance in-memory key-value online store using Redis.
    Keys are organized as `fs:{feature_id}:{entity_key}`.
    Pipelines multi-keys for sub-millisecond batch retrieval.
    Falls back gracefully to PostgreSQL if Redis is unavailable.
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._fallback = PostgresOnlineStore()
        self._client = None
        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True, socket_timeout=1.0)
            self._client.ping()
            logger.info("Connected to Redis Online Store at %s", redis_url)
        except Exception as e:
            logger.warning("Redis online store unavailable (%s). Falling back to PostgreSQL.", e)
            self._client = None

    def get_online_features(
        self,
        entity_keys: List[str],
        feature_id_map: Dict[UUID, str],
        db: Session,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        if not self._client:
            return self._fallback.get_online_features(entity_keys, feature_id_map, db)

        result_map: Dict[str, Dict[str, Optional[str]]] = {
            ek: {f_name: None for f_name in feature_id_map.values()}
            for ek in entity_keys
        }

        try:
            # Build keys and coordinate pipeline
            pipe = self._client.pipeline()
            key_index = []  # [(entity_key, feature_name)]
            for ek in entity_keys:
                for f_id, f_name in feature_id_map.items():
                    rkey = f"fs:{f_id}:{ek}"
                    pipe.get(rkey)
                    key_index.append((ek, f_name))

            values = pipe.execute()
            for (ek, f_name), val in zip(key_index, values):
                result_map[ek][f_name] = val

            return result_map
        except Exception as e:
            logger.error("Redis lookup error: %s. Falling back to DB.", e)
            return self._fallback.get_online_features(entity_keys, feature_id_map, db)

    def write_online_features(
        self,
        records: List[Dict[str, Any]],
        db: Session,
    ) -> int:
        # Write to PostgreSQL for durable persistence
        written = self._fallback.write_online_features(records, db)

        # Mirror writes to Redis for fast online serving
        if self._client:
            try:
                pipe = self._client.pipeline()
                for rec in records:
                    rkey = f"fs:{rec['feature_id']}:{rec['entity_key']}"
                    pipe.set(rkey, str(rec.get("value") or ""), ex=86400 * 30)  # 30 day TTL
                pipe.execute()
            except Exception as e:
                logger.warning("Failed to mirror feature write to Redis: %s", e)

        return written


def get_online_store() -> BaseOnlineStore:
    backend_choice = getattr(settings, "online_store_backend", "postgres").lower()
    if backend_choice == "redis":
        return RedisOnlineStore(settings.redis_url)
    return PostgresOnlineStore()
