"""add soft delete (is_hidden, hidden_reason, hidden_at) to products

Reviewers flag rows that are not real products (collection pages, blog posts,
non-hair items). Instead of hard-deleting we set is_hidden=True so the rows
stay queryable for restore. Default queries filter is_hidden=False.

Revision ID: e7c93d2f1a4b
Revises: a88cdb85fe82
Create Date: 2026-06-02 11:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7c93d2f1a4b'
down_revision: Union[str, Sequence[str], None] = 'a88cdb85fe82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column('products', sa.Column('hidden_reason', sa.String(length=50), nullable=True))
    op.add_column('products', sa.Column('hidden_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_products_is_hidden'), 'products', ['is_hidden'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_products_is_hidden'), table_name='products')
    op.drop_column('products', 'hidden_at')
    op.drop_column('products', 'hidden_reason')
    op.drop_column('products', 'is_hidden')
