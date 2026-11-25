import json
from datetime import datetime

from sqlalchemy import text

from app.core.config import settings
from app.core.roles import ADMIN, ANALYST, DATA_SCIENTIST, ML_ENGINEER
from app.core.security import hash_password
from app.db.models.core import Role, User, UserRole
from app.db.models.feature_store import FeatureDefinition, FeatureGroup
from app.db.models.jobs import JobDefinition
from app.db.models.model_registry import Model, ModelStageHistory, ModelVersion, ModelLineage
from app.db.session import SessionLocal


def seed(include_demo: bool = True) -> None:
    db = SessionLocal()
    try:
        roles = [ADMIN, ML_ENGINEER, DATA_SCIENTIST, ANALYST]
        role_rows = {}
        for role_name in roles:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.commit()
                db.refresh(role)
            role_rows[role_name] = role

        admin = db.query(User).filter(User.email == settings.admin_email).first()
        if not admin:
            admin = User(
                name=settings.admin_name,
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        if not db.query(UserRole).filter(UserRole.user_id == admin.id).first():
            db.add(UserRole(user_id=admin.id, role_id=role_rows[ADMIN].id))
            db.commit()

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS feature_store.sample_events (
                    customer_id VARCHAR(50) NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,
                    event_time TIMESTAMPTZ NOT NULL
                );
                """
            )
        )
        db.commit()
        if not include_demo:
            return
        db.execute(
            text(
                """
                INSERT INTO feature_store.sample_events (customer_id, amount, event_time)
                SELECT * FROM (VALUES
                    ('cust_001', 120.50, NOW()),
                    ('cust_002', 89.25, NOW() - INTERVAL '1 day'),
                    ('cust_001', 49.99, NOW() - INTERVAL '2 days')
                ) AS v(customer_id, amount, event_time)
                WHERE NOT EXISTS (SELECT 1 FROM feature_store.sample_events);
                """
            )
        )
        db.commit()

        group = db.query(FeatureGroup).first()
        if not group:
            group = FeatureGroup(
                name="Payments",
                description="Features built from payments data",
                owner_id=admin.id,
                tags_json=json.dumps(["payments", "core"]),
            )
            db.add(group)
            db.commit()
            db.refresh(group)

        feature = db.query(FeatureDefinition).first()
        if not feature:
            feature = FeatureDefinition(
                group_id=group.id,
                name="customer_30d_spend",
                dtype="float",
                description="Rolling 30-day spend per customer",
                source_sql=(
                    "SELECT customer_id AS entity_key, "
                    "SUM(amount) AS value, "
                    "MAX(event_time) AS event_time "
                    "FROM feature_store.sample_events "
                    "GROUP BY customer_id"
                ),
                refresh_interval="hourly",
                status="active",
            )
            db.add(feature)
            db.commit()
            db.refresh(feature)

        model = db.query(Model).first()
        if not model:
            model = Model(
                name="Churn Predictor",
                description="Predicts churn risk",
                owner_id=admin.id,
            )
            db.add(model)
            db.commit()
            db.refresh(model)

        version = db.query(ModelVersion).first()
        if not version:
            version = ModelVersion(
                model_id=model.id,
                version="1.0",
                stage="Production",
                metrics_json=json.dumps({"roc_auc": 0.92, "precision": 0.86}),
                params_json=json.dumps({"max_depth": 6, "n_estimators": 250}),
            )
            db.add(version)
            db.commit()
            db.refresh(version)
            from uuid import uuid4
            from app.services.artifacts import artifact_path
            version.artifact_uri = f"artifact://{model.id}/{version.id}/{uuid4()}"
            path = artifact_path(version.artifact_uri, model.id, version.id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "format": "featureops.linear.v1", "task": "binary_classification",
                "inputs": [{"name": feature.name, "feature_id": str(feature.id), "dtype": "float"}],
                "coefficients": [0.01], "intercept": -1.0, "classes": [0, 1],
            }))
            db.add(ModelLineage(model_version_id=version.id, feature_ids_json=json.dumps([str(feature.id)])))
            db.commit()

        if not db.query(ModelStageHistory).first():
            history = ModelStageHistory(
                model_version_id=version.id,
                from_stage="Staging",
                to_stage="Production",
                changed_by=admin.id,
                changed_at=datetime.utcnow(),
            )
            db.add(history)
            db.commit()

        job = db.query(JobDefinition).first()
        if not job:
            job = JobDefinition(
                name="Materialize Payments",
                type="feature_materialization",
                cron="0 * * * *",
                payload_json=json.dumps({"feature_id": str(feature.id)}),
                is_active=True,
            )
            db.add(job)
            db.commit()
    finally:
        db.close()
