"""add composition care_usage source_section_label

Revision ID: d4b8e2f3a567
Revises: c3a7f1b2d456
Create Date: 2026-03-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b8e2f3a567'
down_revision: Union[str, Sequence[str], None] = 'c3a7f1b2d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add taxonomy columns for section-aware extraction."""
    op.add_column('products', sa.Column('composition', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('care_usage', sa.Text(), nullable=True))
    op.add_column('product_evidence', sa.Column('source_section_label', sa.String(255), nullable=True))

    # Data migration: copy usage_instructions -> care_usage where applicable
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE products SET care_usage = usage_instructions WHERE usage_instructions IS NOT NULL")
    )


def downgrade() -> None:
    """Remove taxonomy columns."""
    op.drop_column('product_evidence', 'source_section_label')
    op.drop_column('products', 'care_usage')
    op.drop_column('products', 'composition')
