"""Cover point-in-time lookups and bounded per-job run history."""

from alembic import op

revision = "0007_p2_lookup_indexes"
down_revision = "0006_p1_integrity_monitoring"
branch_labels = depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX ix_offline_asof_cover ON feature_store.feature_values_offline "
        "(entity_key, feature_id, event_time DESC) INCLUDE (value)"
    )
    op.execute(
        "CREATE INDEX ix_job_run_recent ON jobs.job_run "
        "(job_definition_id, started_at DESC NULLS LAST, id DESC)"
    )


def downgrade():
    op.drop_index("ix_job_run_recent", table_name="job_run", schema="jobs")
    op.drop_index(
        "ix_offline_asof_cover", table_name="feature_values_offline", schema="feature_store"
    )
