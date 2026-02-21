"""add source column to schemes

Revision ID: a1b2c3d4e5f6
Revises: 6736873b8656
Create Date: 2026-02-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6736873b8656'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'schemes',
        sa.Column('source', sa.String(length=50), nullable=True, server_default='manual'),
    )
    # Backfill existing rows
    op.execute("UPDATE schemes SET source = 'manual' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_column('schemes', 'source')
