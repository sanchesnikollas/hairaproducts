"""add product_category column

Revision ID: c3a7f1b2d456
Revises: af81e7273ce7
Create Date: 2026-02-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a7f1b2d456'
down_revision: Union[str, Sequence[str], None] = 'af81e7273ce7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('products', sa.Column('product_category', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_products_product_category'), 'products', ['product_category'], unique=False)

    # Backfill existing products based on product_type_normalized
    from src.core.taxonomy import CATEGORY_MAP, _COLORACAO_KEYWORDS

    conn = op.get_bind()

    # First: map known product types to categories
    for product_type, category in CATEGORY_MAP.items():
        conn.execute(
            sa.text(
                "UPDATE products SET product_category = :category "
                "WHERE product_type_normalized = :ptype AND product_category IS NULL"
            ),
            {"category": category, "ptype": product_type},
        )

    # Second: detect coloração by product name keywords
    for kw in _COLORACAO_KEYWORDS:
        conn.execute(
            sa.text(
                "UPDATE products SET product_category = 'coloracao' "
                "WHERE LOWER(product_name) LIKE :pattern AND product_category IS NULL"
            ),
            {"pattern": f"%{kw}%"},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_products_product_category'), table_name='products')
    op.drop_column('products', 'product_category')
