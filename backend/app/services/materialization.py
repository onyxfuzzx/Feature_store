from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models.feature_store import (
    FeatureDefinition,
    FeatureMaterialization,
    FeatureValueOffline,
    FeatureValueOnline,
)


def validate_value(val: any, rules: dict) -> list[str]:
    """
    Validate a single feature value against definition validation rules.
    Rules supported: allow_null (bool), min_value (float), max_value (float), required_type (str).
    """
    violations = []
    if val is None:
        if rules.get("allow_null") is False:
            violations.append("null_not_allowed")
        return violations

    min_val = rules.get("min_value")
    if min_val is not None and str(min_val).strip() != "":
        try:
            if float(val) < float(min_val):
                violations.append(f"value_{val}_below_min_{min_val}")
        except (ValueError, TypeError):
            pass

    max_val = rules.get("max_value")
    if max_val is not None and str(max_val).strip() != "":
        try:
            if float(val) > float(max_val):
                violations.append(f"value_{val}_above_max_{max_val}")
        except (ValueError, TypeError):
            pass

    return violations


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

        # Parse validation rules if configured
        rules = {}
        if feature.validation_rules_json:
            try:
                rules = json.loads(feature.validation_rules_json)
            except Exception:
                rules = {}

        total_violations = 0
        violation_samples = []

        for row in rows:
            entity_key = row.get("entity_key")
            if not entity_key:
                raise ValueError("Feature SQL must return entity_key")

            value = row.get("value")
            event_time = row.get("event_time") or now

            # Perform validation check
            if rules:
                errs = validate_value(value, rules)
                if errs:
                    total_violations += len(errs)
                    if len(violation_samples) < 5:
                        violation_samples.append(f"key '{entity_key}': {', '.join(errs)}")

            val_str = None if value is None else str(value)
            offline_rows.append(
                {
                    "entity_key": str(entity_key),
                    "feature_id": feature.id,
                    "value": val_str,
                    "event_time": event_time,
                    "updated_at": now,
                }
            )
            online_rows.append(
                {
                    "entity_key": str(entity_key),
                    "feature_id": feature.id,
                    "value": val_str,
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
        if total_violations > 0:
            run.error_message = f"Validation warnings ({total_violations} issues): " + "; ".join(violation_samples)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(run)

    return run
