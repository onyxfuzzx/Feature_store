"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-03 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    op.execute("CREATE SCHEMA IF NOT EXISTS feature_store")
    op.execute("CREATE SCHEMA IF NOT EXISTS model_registry")
    op.execute("CREATE SCHEMA IF NOT EXISTS jobs")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="core",
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        schema="core",
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.roles.id"), primary_key=True),
        schema="core",
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="core",
    )

    op.create_table(
        "feature_group",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id"), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="feature_store",
    )

    op.create_table(
        "feature_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_store.feature_group.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("dtype", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("source_sql", sa.Text(), nullable=False),
        sa.Column("refresh_interval", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="feature_store",
    )

    op.create_table(
        "feature_lineage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_store.feature_definition.id"), nullable=False),
        sa.Column("source_table", sa.String(length=200), nullable=False),
        sa.Column("source_columns_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="feature_store",
    )

    op.create_table(
        "feature_materialization",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_store.feature_definition.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        schema="feature_store",
    )

    op.create_table(
        "feature_values_online",
        sa.Column("entity_key", sa.String(length=120), primary_key=True),
        sa.Column("feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_store.feature_definition.id"), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="feature_store",
    )

    op.create_table(
        "feature_values_offline",
        sa.Column("entity_key", sa.String(length=120), primary_key=True),
        sa.Column("feature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("feature_store.feature_definition.id"), primary_key=True),
        sa.Column("event_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="feature_store",
    )

    op.create_table(
        "model",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="model_registry",
    )

    op.create_table(
        "model_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_registry.model.id"), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False, server_default=sa.text("'Staging'")),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("artifact_uri", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="model_registry",
    )

    op.create_table(
        "model_lineage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_registry.model_version.id"), nullable=False),
        sa.Column("feature_ids_json", sa.Text(), nullable=True),
        sa.Column("dataset_uri", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="model_registry",
    )

    op.create_table(
        "model_stage_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_registry.model_version.id"), nullable=False),
        sa.Column("from_stage", sa.String(length=40), nullable=False),
        sa.Column("to_stage", sa.String(length=40), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="model_registry",
    )

    op.create_table(
        "job_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("cron", sa.String(length=60), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="jobs",
    )

    op.create_table(
        "job_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_definition.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        schema="jobs",
    )

    op.create_index("idx_feature_definition_group", "feature_definition", ["group_id"], schema="feature_store")
    op.create_index("idx_feature_values_online_feature", "feature_values_online", ["feature_id"], schema="feature_store")
    op.create_index("idx_model_version_model", "model_version", ["model_id"], schema="model_registry")
    op.create_index("idx_job_run_job", "job_run", ["job_definition_id"], schema="jobs")


def downgrade() -> None:
    op.drop_index("idx_job_run_job", table_name="job_run", schema="jobs")
    op.drop_index("idx_model_version_model", table_name="model_version", schema="model_registry")
    op.drop_index("idx_feature_values_online_feature", table_name="feature_values_online", schema="feature_store")
    op.drop_index("idx_feature_definition_group", table_name="feature_definition", schema="feature_store")

    op.drop_table("job_run", schema="jobs")
    op.drop_table("job_definition", schema="jobs")
    op.drop_table("model_stage_history", schema="model_registry")
    op.drop_table("model_lineage", schema="model_registry")
    op.drop_table("model_version", schema="model_registry")
    op.drop_table("model", schema="model_registry")
    op.drop_table("feature_values_offline", schema="feature_store")
    op.drop_table("feature_values_online", schema="feature_store")
    op.drop_table("feature_materialization", schema="feature_store")
    op.drop_table("feature_lineage", schema="feature_store")
    op.drop_table("feature_definition", schema="feature_store")
    op.drop_table("feature_group", schema="feature_store")
    op.drop_table("audit_log", schema="core")
    op.drop_table("user_roles", schema="core")
    op.drop_table("roles", schema="core")
    op.drop_table("users", schema="core")

    op.execute("DROP SCHEMA IF EXISTS jobs")
    op.execute("DROP SCHEMA IF EXISTS model_registry")
    op.execute("DROP SCHEMA IF EXISTS feature_store")
    op.execute("DROP SCHEMA IF EXISTS core")
