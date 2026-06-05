"""brand_registry table — catálogo editável de marcas via UI

Permite que admin/Clarisse cadastrem marcas novas direto pelo painel
(/ops/brands → "+ Nova Marca") sem precisar editar `config/brands.json`
e redeploy.

Seed inicial via data migration: copia tudo de `config/brands.json` da
container.

Revision ID: b5d2c8e4f1a9
Revises: a4b9c8d2e3f7
Create Date: 2026-06-05 01:30:00.000000
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.brand_registry")

revision: str = 'b5d2c8e4f1a9'
down_revision: Union[str, Sequence[str], None] = 'a4b9c8d2e3f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'brand_registry',
        sa.Column('brand_slug', sa.String(length=255), primary_key=True),
        sa.Column('brand_name', sa.String(length=255), nullable=False),
        sa.Column('official_url_root', sa.String(length=2000), nullable=True),
        sa.Column('country', sa.String(length=80), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('platform', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Seed inicial — copia brands.json se o arquivo existir no container.
    # Não falha o upgrade se o arquivo sumir; só pula o seed.
    brands_json = Path('config/brands.json')
    if not brands_json.exists():
        logger.warning("config/brands.json não encontrado; seed pulado")
        return

    try:
        records = json.loads(brands_json.read_text())
    except Exception as exc:
        logger.warning("config/brands.json malformado, seed pulado: %s", exc)
        return

    conn = op.get_bind()
    inserted = 0
    for r in records:
        slug = r.get('brand_slug')
        name = r.get('brand_name')
        if not slug or not name:
            continue
        conn.execute(
            sa.text("""
                INSERT INTO brand_registry
                  (brand_slug, brand_name, official_url_root, country, priority, status, notes)
                VALUES (:slug, :name, :url, :country, :priority, :status, :notes)
                ON CONFLICT (brand_slug) DO NOTHING
            """),
            {
                "slug": slug,
                "name": name,
                "url": r.get('official_url_root'),
                "country": r.get('country'),
                "priority": r.get('priority'),
                "status": r.get('status') or 'active',
                "notes": r.get('notes'),
            },
        )
        inserted += 1
    logger.info("brand_registry seedada com %d marcas de config/brands.json", inserted)


def downgrade() -> None:
    op.drop_table('brand_registry')
