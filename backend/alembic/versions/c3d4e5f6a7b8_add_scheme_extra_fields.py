"""add scheme extra fields for link enrichment

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schemes', sa.Column('extra_details', JSONB, nullable=True))
    op.add_column('schemes', sa.Column('link_status', sa.String(20), nullable=True))
    op.add_column('schemes', sa.Column('link_checked_at', sa.DateTime, nullable=True))
    op.add_column('schemes', sa.Column('launch_date', sa.Date, nullable=True))
    op.add_column('schemes', sa.Column('application_deadline', sa.Date, nullable=True))
    op.add_column('schemes', sa.Column('helpline', sa.String(500), nullable=True))
    op.add_column('schemes', sa.Column('benefit_type', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('schemes', 'benefit_type')
    op.drop_column('schemes', 'helpline')
    op.drop_column('schemes', 'application_deadline')
    op.drop_column('schemes', 'launch_date')
    op.drop_column('schemes', 'link_checked_at')
    op.drop_column('schemes', 'link_status')
    op.drop_column('schemes', 'extra_details')
