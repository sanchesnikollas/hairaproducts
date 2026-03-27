"""add external_inci and enrichment_queue tables

Revision ID: 5ccfa5a86395
Revises: 760c4a916b6b
Create Date: 2026-03-27 16:35:44.943075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ccfa5a86395'
down_revision: Union[str, Sequence[str], None] = '760c4a916b6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('enrichment_queue',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('external_inci_id', sa.String(length=36), nullable=False),
    sa.Column('match_score', sa.Float(), nullable=False),
    sa.Column('match_details', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enrichment_queue_product_id'), 'enrichment_queue', ['product_id'], unique=False)
    op.create_table('external_inci',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('brand_slug', sa.String(length=255), nullable=False),
    sa.Column('product_name', sa.Text(), nullable=True),
    sa.Column('product_type', sa.String(length=100), nullable=True),
    sa.Column('inci_raw', sa.Text(), nullable=True),
    sa.Column('inci_ingredients', sa.JSON(), nullable=True),
    sa.Column('ean', sa.String(length=50), nullable=True),
    sa.Column('scraped_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'source_url', name='uq_external_inci_source_url')
    )
    op.create_index(op.f('ix_external_inci_brand_slug'), 'external_inci', ['brand_slug'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_external_inci_brand_slug'), table_name='external_inci')
    op.drop_table('external_inci')
    op.drop_index(op.f('ix_enrichment_queue_product_id'), table_name='enrichment_queue')
    op.drop_table('enrichment_queue')
