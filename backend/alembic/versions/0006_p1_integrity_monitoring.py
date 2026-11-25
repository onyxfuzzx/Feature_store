"""Registry identities, scheduler slots, and persisted model drift evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_p1_integrity_monitoring"
down_revision = "0005_online_revision"
branch_labels = depends_on = None


def upgrade():
    # Existing conflicting identities require an operator decision; never delete or rename data here.
    for query in (
        "SELECT 1 FROM model_registry.model_version GROUP BY model_id, version HAVING count(*) > 1",
        "SELECT 1 FROM model_registry.model_version WHERE stage = 'Production' GROUP BY model_id HAVING count(*) > 1",
        "SELECT 1 FROM model_registry.model_version WHERE stage NOT IN ('Staging', 'Production', 'Archived')",
        "SELECT 1 FROM feature_store.feature_group GROUP BY environment, name HAVING count(*) > 1",
        "SELECT 1 FROM feature_store.feature_definition GROUP BY group_id, name HAVING count(*) > 1",
    ):
        if op.get_bind().execute(sa.text(query)).first():
            raise RuntimeError(
                "P1 migration found conflicting identities/stages. Resolve duplicates explicitly before retrying: "
                + query
            )
    op.create_unique_constraint(
        "uq_model_version_identity",
        "model_version",
        ["model_id", "version"],
        schema="model_registry",
    )
    op.create_check_constraint(
        "ck_model_version_stage",
        "model_version",
        "stage IN ('Staging', 'Production', 'Archived')",
        schema="model_registry",
    )
    op.create_index(
        "uq_model_one_production",
        "model_version",
        ["model_id"],
        unique=True,
        schema="model_registry",
        postgresql_where=sa.text("stage = 'Production'"),
    )
    op.create_unique_constraint(
        "uq_feature_group_scope", "feature_group", ["environment", "name"], schema="feature_store"
    )
    op.create_unique_constraint(
        "uq_feature_definition_scope",
        "feature_definition",
        ["group_id", "name"],
        schema="feature_store",
    )
    op.add_column("job_run", sa.Column("scheduled_for", sa.DateTime(timezone=True)), schema="jobs")
    op.create_unique_constraint(
        "uq_job_scheduled_slot", "job_run", ["job_definition_id", "scheduled_for"], schema="jobs"
    )
    op.create_table(
        "drift_baseline",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_registry.model_version.id"),
            nullable=False,
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("distributions", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="model_registry",
    )
    op.create_index(
        "ix_drift_baseline_model_version_id",
        "drift_baseline",
        ["model_version_id"],
        schema="model_registry",
    )
    op.create_table(
        "inference_observation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_registry.model_version.id"),
            nullable=False,
        ),
        sa.Column("entity_key", sa.String(120), nullable=False),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("values_json", JSONB, nullable=False),
        schema="model_registry",
    )
    op.create_index(
        "ix_inference_version_time",
        "inference_observation",
        ["model_version_id", "observed_at"],
        schema="model_registry",
    )
    op.create_table(
        "drift_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("model_registry.model_version.id"),
            nullable=False,
        ),
        sa.Column(
            "baseline_id", UUID(as_uuid=True), sa.ForeignKey("model_registry.drift_baseline.id")
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("result_json", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="model_registry",
    )
    op.create_index(
        "ix_drift_run_model_version_id", "drift_run", ["model_version_id"], schema="model_registry"
    )


def downgrade():
    for table in ("drift_run", "inference_observation", "drift_baseline"):
        op.drop_table(table, schema="model_registry")
    op.drop_constraint("uq_job_scheduled_slot", "job_run", schema="jobs")
    op.drop_column("job_run", "scheduled_for", schema="jobs")
    op.drop_constraint("uq_feature_definition_scope", "feature_definition", schema="feature_store")
    op.drop_constraint("uq_feature_group_scope", "feature_group", schema="feature_store")
    op.drop_index("uq_model_one_production", table_name="model_version", schema="model_registry")
    op.drop_constraint("ck_model_version_stage", "model_version", schema="model_registry")
    op.drop_constraint("uq_model_version_identity", "model_version", schema="model_registry")
