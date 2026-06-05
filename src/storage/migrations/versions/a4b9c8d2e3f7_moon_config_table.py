"""moon_config table for editable Moon personality

Tabela de chaves/valores pra Moon (system_prompt, intent.saude_couro, etc.)
ser editável via UI no painel admin (/ops/knowledge aba Identidade & Tom).
Seeds inserts via INSERT ON CONFLICT DO NOTHING para não estourar em deploys
em que `src/api/main.py` startup já tenha rodado.

Revision ID: a4b9c8d2e3f7
Revises: f2e8a4d7c1b3
Create Date: 2026-06-04 19:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4b9c8d2e3f7'
down_revision: Union[str, Sequence[str], None] = 'f2e8a4d7c1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'moon_config',
        sa.Column('key', sa.String(length=64), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.user_id'], ondelete='SET NULL'),
    )


def downgrade() -> None:
    op.drop_table('moon_config')
