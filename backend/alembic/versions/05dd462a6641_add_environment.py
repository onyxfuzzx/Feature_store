"""add_environment

Revision ID: 05dd462a6641
Revises: 2326743abe1f
Create Date: 2026-06-05 14:28:03.583782

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "05dd462a6641"
down_revision: str | None = "2326743abe1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_group",
        sa.Column(
            "environment", sa.String(length=40), server_default=sa.text("'dev'"), nullable=False
        ),
        schema="feature_store",
    )
    op.add_column(
        "model",
        sa.Column(
            "environment", sa.String(length=40), server_default=sa.text("'dev'"), nullable=False
        ),
        schema="model_registry",
    )


def downgrade() -> None:
    op.drop_column("model", "environment", schema="model_registry")
    op.drop_column("feature_group", "environment", schema="feature_store")
