"""add hair classification fields

Revision ID: a1b2c3d4e5f6
Revises: 5ccfa5a86395
Create Date: 2026-04-28 12:00:00.000000

Adiciona ph, hair_type, audience_age, function_objective, image_url_front, image_url_back.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5ccfa5a86395'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('ph', sa.Float(), nullable=True))
    op.add_column('products', sa.Column('hair_type', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('audience_age', sa.String(length=20), nullable=True))
    op.add_column('products', sa.Column('function_objective', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('image_url_front', sa.String(length=2000), nullable=True))
    op.add_column('products', sa.Column('image_url_back', sa.String(length=2000), nullable=True))

    op.create_index('ix_products_ph', 'products', ['ph'])
    op.create_index('ix_products_audience_age', 'products', ['audience_age'])
    op.create_index('ix_products_function_objective', 'products', ['function_objective'])


def downgrade() -> None:
    op.drop_index('ix_products_function_objective', table_name='products')
    op.drop_index('ix_products_audience_age', table_name='products')
    op.drop_index('ix_products_ph', table_name='products')

    op.drop_column('products', 'image_url_back')
    op.drop_column('products', 'image_url_front')
    op.drop_column('products', 'function_objective')
    op.drop_column('products', 'audience_age')
    op.drop_column('products', 'hair_type')
    op.drop_column('products', 'ph')
