"""add ean to products (OCR barcode match)

The OCR /moon/identify flow matches a physical product to the catalog. EAN
(barcode) is the strongest exact key. Backfill from external_inci.ean is a later
step.

Revision ID: d8e2f1a4c0b7
Revises: c7a1d9f3b2e6
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e2f1a4c0b7'
down_revision: Union[str, Sequence[str], None] = 'c7a1d9f3b2e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('ean', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_products_ean'), 'products', ['ean'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_products_ean'), table_name='products')
    op.drop_column('products', 'ean')
