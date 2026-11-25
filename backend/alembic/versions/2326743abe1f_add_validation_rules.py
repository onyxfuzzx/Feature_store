"""add_validation_rules

Revision ID: 2326743abe1f
Revises: c035ccd4da68
Create Date: 2026-06-05 14:26:34.327852

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2326743abe1f"
down_revision: str | None = "c035ccd4da68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_definition",
        sa.Column("validation_rules_json", sa.Text(), nullable=True),
        schema="feature_store",
    )


def downgrade() -> None:
    op.drop_column("feature_definition", "validation_rules_json", schema="feature_store")
