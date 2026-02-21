"""add scheme_translations table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheme_translations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scheme_id', UUID(as_uuid=True), sa.ForeignKey('schemes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lang', sa.String(10), nullable=False),
        sa.Column('name', sa.String(500), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('benefits', sa.Text, nullable=True),
        sa.Column('eligibility_criteria', sa.Text, nullable=True),
        sa.Column('application_process', sa.Text, nullable=True),
        sa.Column('documents_required', sa.Text, nullable=True),
        sa.Column('tags_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        'ix_scheme_translations_scheme_lang',
        'scheme_translations',
        ['scheme_id', 'lang'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_scheme_translations_scheme_lang', table_name='scheme_translations')
    op.drop_table('scheme_translations')
