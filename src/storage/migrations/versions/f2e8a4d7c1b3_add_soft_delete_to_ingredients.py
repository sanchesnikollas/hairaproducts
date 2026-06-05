"""add soft delete (is_hidden, hidden_reason, hidden_at) to ingredients

Limpa contaminação histórica do extrator: JS code (answer.classList.add),
frases de marketing ('hidrata e nutre'), nomes de produtos inteiros que
viraram 'ingrediente'. Padrão hide-not-erase pra permitir restore.

Aplicado em prod via SQL direto + 2.642 linhas marcadas (categorias
js_code, sentence, marketing, product_name, too_many_words, etc).

Revision ID: f2e8a4d7c1b3
Revises: e7c93d2f1a4b
Create Date: 2026-06-04 02:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2e8a4d7c1b3'
down_revision: Union[str, Sequence[str], None] = 'e7c93d2f1a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ingredients',
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column('ingredients', sa.Column('hidden_reason', sa.String(length=50), nullable=True))
    op.add_column('ingredients', sa.Column('hidden_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_ingredients_is_hidden'), 'ingredients', ['is_hidden'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ingredients_is_hidden'), table_name='ingredients')
    op.drop_column('ingredients', 'hidden_at')
    op.drop_column('ingredients', 'hidden_reason')
    op.drop_column('ingredients', 'is_hidden')
