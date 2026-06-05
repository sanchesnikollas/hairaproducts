"""Initial audit schema — revision_history (migrada) + 3 logs novos.

Cria as 4 tabelas em haira_audit:
- revision_history (entity diff trail — antes era em catalog)
- kb_retrieval_log (cada chamada de /moon/chat que consulta KB)
- admin_action_log (audit de ações admin com before/after)
- auth_event_log (login/logout/falha/reset)

Idempotente: usa IF NOT EXISTS via Alembic's `op.create_table` que checa.
A migration EQUIVALENTE no catalog DB (revision_history original) fica
intocada — só é deletada após o cutover (Fase E) com a confirmação que
dados foram migrados.

Revision ID: 0001_audit_init
Revises:
Create Date: 2026-06-05 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_audit_init"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revision_history",
        sa.Column("revision_id", sa.String(length=36), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("user_kind", sa.String(length=20), nullable=False, server_default="human"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revision_history_entity_type", "revision_history", ["entity_type"])
    op.create_index("ix_revision_history_entity_id", "revision_history", ["entity_id"])
    op.create_index("ix_revision_history_user_id", "revision_history", ["user_id"])
    op.create_index("ix_revision_history_created_at", "revision_history", ["created_at"])

    op.create_table(
        "kb_retrieval_log",
        sa.Column("log_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=True),
        sa.Column("kb_sources", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("chunk_count", sa.String(length=8), nullable=False, server_default="0"),
        sa.Column("anthropic_tokens_in", sa.String(length=16), nullable=True),
        sa.Column("anthropic_tokens_out", sa.String(length=16), nullable=True),
        sa.Column("latency_ms", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_kb_retrieval_log_user_id", "kb_retrieval_log", ["user_id"])
    op.create_index("ix_kb_retrieval_log_conversation_id", "kb_retrieval_log", ["conversation_id"])
    op.create_index("ix_kb_retrieval_log_query_hash", "kb_retrieval_log", ["query_hash"])
    op.create_index("ix_kb_retrieval_log_created_at", "kb_retrieval_log", ["created_at"])
    op.create_index(
        "ix_kb_retrieval_log_created_user", "kb_retrieval_log",
        ["created_at", "user_id"],
    )

    op.create_table(
        "admin_action_log",
        sa.Column("action_id", sa.String(length=36), primary_key=True),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_admin_action_log_actor_id", "admin_action_log", ["actor_id"])
    op.create_index("ix_admin_action_log_action", "admin_action_log", ["action"])
    op.create_index("ix_admin_action_log_target_id", "admin_action_log", ["target_id"])
    op.create_index("ix_admin_action_log_created_at", "admin_action_log", ["created_at"])
    op.create_index(
        "ix_admin_action_log_action_created", "admin_action_log",
        ["action", "created_at"],
    )

    op.create_table(
        "auth_event_log",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_auth_event_log_user_id", "auth_event_log", ["user_id"])
    op.create_index("ix_auth_event_log_email", "auth_event_log", ["email"])
    op.create_index("ix_auth_event_log_event_type", "auth_event_log", ["event_type"])
    op.create_index("ix_auth_event_log_ip_address", "auth_event_log", ["ip_address"])
    op.create_index("ix_auth_event_log_created_at", "auth_event_log", ["created_at"])
    op.create_index(
        "ix_auth_event_log_email_type_created", "auth_event_log",
        ["email", "event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("auth_event_log")
    op.drop_table("admin_action_log")
    op.drop_table("kb_retrieval_log")
    op.drop_table("revision_history")
