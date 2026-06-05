"""Audit log models — append-only, lives in `haira_audit` DB.

Tabelas separadas das de operação porque:
1. **Performance**: writes de audit não competem com queries do app principal.
2. **Retenção**: audit precisa ficar 365+ dias; operação rota 30-90.
3. **Segurança**: backup/restore separado, permite WORM (write-once-read-many).

Quando `AUDIT_DATABASE_URL` está setada, essas tabelas vivem na DB própria.
Sem ela, caem na mesma DB do core via fallback em `dependencies.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, JSON, Index
from sqlalchemy.orm import DeclarativeBase


class AuditBase(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RevisionHistoryORM(AuditBase):
    """Versionamento de ProductORM, IngredientORM, etc.

    Movida de orm_models.py — mesmo schema. Migration garante coexistência
    durante a transição (read+write em ambas até cutover).
    """
    __tablename__ = "revision_history"

    revision_id = Column(String(36), primary_key=True, default=_uuid)
    entity_type = Column(String(50), nullable=False, index=True)    # 'product' | 'ingredient' | 'brand' | 'moon_config'
    entity_id = Column(String(255), nullable=False, index=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=False)
    change_reason = Column(Text, nullable=True)
    user_id = Column(String(36), nullable=True, index=True)
    user_kind = Column(String(20), nullable=False, default="human")  # 'human' | 'pipeline' | 'sync'
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


class KbRetrievalLogORM(AuditBase):
    """Cada chamada do Moon que consulta a KB grava uma linha aqui.

    Query original NÃO é gravada — só o sha256 — porque pode conter PII do
    usuário (sintomas, hábitos). O hash permite agrupar 'mesma query' sem
    armazenar texto.
    """
    __tablename__ = "kb_retrieval_log"

    log_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), nullable=True, index=True)         # quem perguntou
    conversation_id = Column(String(36), nullable=True, index=True)
    query_hash = Column(String(64), nullable=False, index=True)     # sha256 da query normalizada
    intent = Column(String(32), nullable=True)
    kb_sources = Column(JSON, nullable=False, default=list)          # list[str] — fontes carregadas
    chunk_count = Column(String(8), nullable=False, default="0")     # quantos chunks retornados
    anthropic_tokens_in = Column(String(16), nullable=True)
    anthropic_tokens_out = Column(String(16), nullable=True)
    latency_ms = Column(String(16), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


Index("ix_kb_retrieval_log_created_user", KbRetrievalLogORM.created_at, KbRetrievalLogORM.user_id)


class AdminActionLogORM(AuditBase):
    """Audit trail de ações admin com diff.

    Quem editou system_prompt da Moon, quem criou marca, quem mudou config —
    tudo aqui com before/after. Imutável: nunca UPDATE/DELETE nessas linhas.
    """
    __tablename__ = "admin_action_log"

    action_id = Column(String(36), primary_key=True, default=_uuid)
    actor_id = Column(String(36), nullable=False, index=True)        # FK lógica users.user_id
    actor_email = Column(String(255), nullable=True)                 # snapshot (caso user seja deletado)
    action = Column(String(64), nullable=False, index=True)          # 'moon_config.update' | 'brand.create' | etc.
    target_type = Column(String(64), nullable=True)
    target_id = Column(String(255), nullable=True, index=True)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


Index("ix_admin_action_log_action_created", AdminActionLogORM.action, AdminActionLogORM.created_at)


class AuthEventLogORM(AuditBase):
    """Login, logout, reset, falha de token. Permite detectar brute-force,
    credenciais comprometidas, padrões anômalos."""
    __tablename__ = "auth_event_log"

    event_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    event_type = Column(String(32), nullable=False, index=True)      # 'login_ok' | 'login_fail' | 'logout' | 'token_invalid' | 'admin_reset'
    ip_address = Column(String(64), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    detail = Column(Text, nullable=True)                              # razão da falha, se aplicável
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)


Index("ix_auth_event_log_email_type_created",
      AuthEventLogORM.email, AuthEventLogORM.event_type, AuthEventLogORM.created_at)
