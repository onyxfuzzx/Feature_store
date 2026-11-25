from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.db.models.feature_store import FeatureDefinition, FeatureMaterialization, FeatureValueOffline
from app.services.online_store import get_online_store
from app.services.source_queries import execute_source_query
from app.services.validation import parse_rules, validate_value


def write_offline_values(db, records):
    for row in records:
        statement = insert(FeatureValueOffline).values(**row)
        inserted = db.execute(statement.on_conflict_do_nothing(
            index_elements=["entity_key", "feature_id", "event_time"],
        ).returning(FeatureValueOffline.entity_key)).first()
        if not inserted:
            existing = db.query(FeatureValueOffline).filter_by(entity_key=row["entity_key"],
                feature_id=row["feature_id"], event_time=row["event_time"]).one()
            if existing.value != row["value"]:
                raise HTTPException(409, "Conflicting replay: an event timestamp already has a different value")


def materialize_feature(db: Session, feature_id) -> FeatureMaterialization:
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise ValueError("Feature not found")
    run = FeatureMaterialization(feature_id=feature.id, status="running", started_at=datetime.now(timezone.utc))
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        rules = parse_rules(feature.validation_rules_json)
        columns, rows = execute_source_query(feature.source_sql, settings.source_max_rows + 1)
        if not {"entity_key", "value"}.issubset(columns):
            raise ValueError("Feature SQL must return entity_key and value columns")
        if len(rows) > settings.source_max_rows:
            raise ValueError("Source query exceeds SOURCE_MAX_ROWS")
        now = datetime.now(timezone.utc)
        records = []
        for row in rows:
            if row["entity_key"] is None or not str(row["entity_key"]):
                raise ValueError("Feature SQL returned an empty entity_key")
            errors = validate_value(row["value"], rules, feature.dtype)
            if errors:
                raise ValueError(f"Validation rejected entity {row['entity_key']}: {', '.join(errors)}")
            records.append({"entity_key": str(row["entity_key"]), "feature_id": feature.id,
                            "value": None if row["value"] is None else str(row["value"]),
                            "event_time": row.get("event_time") or now, "updated_at": now})
        write_offline_values(db, records)
        get_online_store().write_online_features(records, db, replace_feature_ids=[feature.id])
        run.status = "success"
        run.row_count = len(records)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(FeatureMaterialization, run_id)
        run.status = "failed"
        run.row_count = 0
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    db.refresh(run)
    return run
