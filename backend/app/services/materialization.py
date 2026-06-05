from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models.feature_store import (
    FeatureDefinition,
    FeatureMaterialization,
    FeatureValueOffline,
    FeatureValueOnline,
)


def materialize_feature(db: Session, feature_id) -> FeatureMaterialization:
    feature = db.get(FeatureDefinition, feature_id)
    if not feature:
        raise ValueError("Feature not found")

    run = FeatureMaterialization(
        feature_id=feature.id,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        sql = feature.source_sql.strip()
        if not sql.lower().startswith("select"):
            raise ValueError("Feature source SQL must start with SELECT")

        rows = db.execute(text(sql)).mappings().all()
        offline_rows = []
        online_rows = []
        now = datetime.utcnow()

        for row in rows:
            entity_key = row.get("entity_key")
            if not entity_key:
                raise ValueError("Feature SQL must return entity_key")

            value = row.get("value")
            event_time = row.get("event_time") or now

            offline_rows.append(
                {
                    "entity_key": str(entity_key),
                    "feature_id": feature.id,
                    "value": None if value is None else str(value),
                    "event_time": event_time,
                    "updated_at": now,
                }
            )
            online_rows.append(
                {
                    "entity_key": str(entity_key),
                    "feature_id": feature.id,
                    "value": None if value is None else str(value),
                    "event_time": event_time,
                    "updated_at": now,
                }
            )

        if offline_rows:
            db.execute(FeatureValueOffline.__table__.insert(), offline_rows)

        db.execute(
            delete(FeatureValueOnline).where(FeatureValueOnline.feature_id == feature.id)
        )
        if online_rows:
            db.execute(FeatureValueOnline.__table__.insert(), online_rows)

        run.status = "success"
        run.row_count = len(offline_rows)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(run)

    return run
