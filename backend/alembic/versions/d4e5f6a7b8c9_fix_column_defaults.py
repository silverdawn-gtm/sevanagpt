"""fix column defaults for status, featured, source

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix status: set server_default and make non-nullable
    op.alter_column('schemes', 'status',
                     existing_type=sa.String(20),
                     server_default='active',
                     nullable=False)
    # Backfill any NULLs
    op.execute("UPDATE schemes SET status = 'active' WHERE status IS NULL")

    # Fix featured: set server_default and make non-nullable
    op.alter_column('schemes', 'featured',
                     existing_type=sa.Boolean(),
                     server_default=sa.text('false'),
                     nullable=False)
    op.execute("UPDATE schemes SET featured = false WHERE featured IS NULL")

    # Fix source: set server_default and make non-nullable
    op.alter_column('schemes', 'source',
                     existing_type=sa.String(50),
                     server_default='manual',
                     nullable=False)
    op.execute("UPDATE schemes SET source = 'manual' WHERE source IS NULL")


def downgrade() -> None:
    op.alter_column('schemes', 'source',
                     existing_type=sa.String(50),
                     server_default=None,
                     nullable=True)
    op.alter_column('schemes', 'featured',
                     existing_type=sa.Boolean(),
                     server_default=None,
                     nullable=True)
    op.alter_column('schemes', 'status',
                     existing_type=sa.String(20),
                     server_default=None,
                     nullable=True)
