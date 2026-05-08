"""ingredient category compatibility matrix (Moon AI foundation)

Revision ID: m00n1f0und4t10n
Revises: 0a8d10f67b8d
Create Date: 2026-05-08 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'm00n1f0und4t10n'
down_revision: Union[str, Sequence[str], None] = '0a8d10f67b8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ingredient_category_compatibility',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('hair_type', sa.String(length=32), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),  # -1, 0, +1
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', 'hair_type', name='uq_compat_cat_hair'),
    )
    op.create_index('idx_compat_cat', 'ingredient_category_compatibility', ['category'])
    op.create_index('idx_compat_hair', 'ingredient_category_compatibility', ['hair_type'])


def downgrade() -> None:
    op.drop_index('idx_compat_hair', table_name='ingredient_category_compatibility')
    op.drop_index('idx_compat_cat', table_name='ingredient_category_compatibility')
    op.drop_table('ingredient_category_compatibility')
