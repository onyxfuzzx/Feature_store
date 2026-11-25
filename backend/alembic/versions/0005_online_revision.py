"""Version cache keys with the committed feature generation."""

import sqlalchemy as sa
from alembic import op

revision = "0005_online_revision"
down_revision = "05dd462a6641"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "feature_definition",
        sa.Column("online_revision", sa.BigInteger(), nullable=False, server_default="0"),
        schema="feature_store",
    )


def downgrade():
    op.drop_column("feature_definition", "online_revision", schema="feature_store")
