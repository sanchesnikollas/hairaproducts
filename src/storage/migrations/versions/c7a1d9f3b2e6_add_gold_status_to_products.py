"""add Gold gate columns to products

The Gold tier is the AI-facing trust axis (see src/core/gold_gate.py), separate
from verification_status. A product becomes 'gold' only by passing every Gold
criterion via evaluate_gold — never by a bare status flip. gold_blockers caches
the unmet criteria so the Ops UI can render a self-documenting checklist.

Revision ID: c7a1d9f3b2e6
Revises: b5d2c8e4f1a9
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a1d9f3b2e6'
down_revision: Union[str, Sequence[str], None] = 'b5d2c8e4f1a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('gold_status', sa.String(length=20), nullable=False, server_default='raw'),
    )
    op.add_column('products', sa.Column('gold_blockers', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('gold_evaluated_at', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('gold_reviewed_by', sa.String(length=36), nullable=True))
    op.add_column('products', sa.Column('gold_review_notes', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('field_provenance', sa.JSON(), nullable=True))
    op.create_index(op.f('ix_products_gold_status'), 'products', ['gold_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_products_gold_status'), table_name='products')
    op.drop_column('products', 'field_provenance')
    op.drop_column('products', 'gold_review_notes')
    op.drop_column('products', 'gold_reviewed_by')
    op.drop_column('products', 'gold_evaluated_at')
    op.drop_column('products', 'gold_blockers')
    op.drop_column('products', 'gold_status')
