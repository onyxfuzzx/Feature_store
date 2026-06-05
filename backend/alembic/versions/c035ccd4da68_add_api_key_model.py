"""add_api_key_model

Revision ID: c035ccd4da68
Revises: 0001_initial
Create Date: 2026-06-05 14:24:51.396307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision: str = 'c035ccd4da68'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('api_keys',
        sa.Column('id', mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column('user_id', mssql.UNIQUEIDENTIFIER(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('sysutcdatetime()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['core.users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
        schema='core'
    )


def downgrade() -> None:
    op.drop_table('api_keys', schema='core')
