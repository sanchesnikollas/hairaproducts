"""hair_profiles table (Moon contextual — perfil capilar do usuário)

Revision ID: h41rpr0f1l3
Revises: m00n1f0und4t10n
Create Date: 2026-05-22 17:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h41rpr0f1l3"
down_revision = "m00n1f0und4t10n"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hair_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("hair_types", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_hair_profile_user"),
    )
    op.create_index("idx_hair_profile_user", "hair_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_hair_profile_user", table_name="hair_profiles")
    op.drop_table("hair_profiles")
