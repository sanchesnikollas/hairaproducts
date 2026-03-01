"""widen evidence_locator to text

Revision ID: af81e7273ce7
Revises: bf5a62d6a28b
Create Date: 2026-02-27 22:03:23.217752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af81e7273ce7'
down_revision: Union[str, Sequence[str], None] = 'bf5a62d6a28b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('product_evidence') as batch_op:
        batch_op.alter_column('evidence_locator',
                   existing_type=sa.VARCHAR(length=500),
                   type_=sa.Text(),
                   existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('product_evidence') as batch_op:
        batch_op.alter_column('evidence_locator',
                   existing_type=sa.Text(),
                   type_=sa.VARCHAR(length=500),
                   existing_nullable=True)
