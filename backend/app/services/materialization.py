from datetime import UTC, datetime

from app.core.config import settings
from app.db.models.feature_store import (
    FeatureDefinition,
    FeatureMaterialization,
    FeatureValueOffline,
)
from app.services.batches import unique_events
from app.services.online_store import get_online_store
from app.services.source_queries import source_query_batches
from app.services.validation import parse_rules, validate_value
from fastapi import HTTPException
from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session


def write_offline_values(db, records):
    rows = unique_events(records)
    for offset in range(0, len(rows), settings.materialization_batch_size):
        batch = rows[offset : offset + settings.materialization_batch_size]
        statement = insert(FeatureValueOffline).values(batch)
        inserted = set(
            db.execute(
                statement.on_conflict_do_nothing(
                    index_elements=["entity_key", "feature_id", "event_time"],
                ).returning(
                    FeatureValueOffline.entity_key,
                    FeatureValueOffline.feature_id,
                    FeatureValueOffline.event_time,
                )
            ).all()
        )
        unchanged = [
            row
            for row in batch
            if (row["entity_key"], row["feature_id"], row["event_time"]) not in inserted
        ]
        if unchanged:
            existing = {
                (row.entity_key, row.feature_id, row.event_time): row.value
                for row in db.query(
                    FeatureValueOffline.entity_key,
                    FeatureValueOffline.feature_id,
                    FeatureValueOffline.event_time,
                    FeatureValueOffline.value,
                )
                .filter(
                    tuple_(
                        FeatureValueOffline.entity_key,
                        FeatureValueOffline.feature_id,
                        FeatureValueOffline.event_time,
                    ).in_(
                        [
                            (row["entity_key"], row["feature_id"], row["event_time"])
                            for row in unchanged
                        ]
                    )
                )
                .all()
            }
            if any(
                existing[row["entity_key"], row["feature_id"], row["event_time"]] != row["value"]
                for row in unchanged
            ):
                raise HTTPException(
                    409, "Conflicting replay: an event timestamp already has a different value"
                )


def materialize_feature(db: Session, feature_id) -> FeatureMaterialization:
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise ValueError("Feature not found")
    run = FeatureMaterialization(
        feature_id=feature.id, status="running", started_at=datetime.now(UTC)
    )
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        rules = parse_rules(feature.validation_rules_json)
        total = 0
        store = get_online_store()
        with source_query_batches(
            feature.source_sql, settings.source_max_rows + 1, settings.materialization_batch_size
        ) as (columns, batches):
            if not {"entity_key", "value"}.issubset(columns):
                raise ValueError("Feature SQL must return entity_key and value columns")
            # One revision invalidates the whole refresh. Large refreshes warm Redis on read,
            # so no unbounded list of post-commit publication records is retained.
            store.write_online_features([], db, replace_feature_ids=[feature.id])
            now = datetime.now(UTC)
            for batch in batches:
                total += len(batch)
                if total > settings.source_max_rows:
                    raise ValueError("Source query exceeds SOURCE_MAX_ROWS")
                records = []
                for row in batch:
                    if row["entity_key"] is None or not str(row["entity_key"]):
                        raise ValueError("Feature SQL returned an empty entity_key")
                    errors = validate_value(row["value"], rules, feature.dtype)
                    if errors:
                        raise ValueError(
                            f"Validation rejected entity {row['entity_key']}: {', '.join(errors)}"
                        )
                    records.append(
                        {
                            "entity_key": str(row["entity_key"]),
                            "feature_id": feature.id,
                            "value": None if row["value"] is None else str(row["value"]),
                            "event_time": row.get("event_time") or now,
                            "updated_at": now,
                        }
                    )
                write_offline_values(db, records)
                store.write_online_features(records, db, advance_revision=False, publish=False)
        run.status = "success"
        run.row_count = total
        run.finished_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(FeatureMaterialization, run_id)
        run.status = "failed"
        run.row_count = 0
        run.error_message = str(exc)
        run.finished_at = datetime.now(UTC)
        db.commit()
    db.refresh(run)
    return run
