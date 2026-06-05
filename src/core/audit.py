"""Helpers pra escrever no haira_audit sem bloquear a request principal.

Política:
- Audit write é fire-and-forget — falhas são logadas e silenciadas, nunca
  propagadas pro endpoint chamador.
- Cada função abre sua própria sessão via get_audit_session() e commita
  imediatamente. Mantém isolamento da transação principal.
- Quando AUDIT_DATABASE_URL não está setado, o engine cai em fallback chain
  e escreve no mesmo Postgres que o resto. As tabelas ainda existem porque
  Base.metadata.create_all (via alembic) cria todas no schema único.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("haira.audit")


def _open_session():
    """Lazy import pra evitar ciclo em testes."""
    from src.api.dependencies import get_audit_session
    gen = get_audit_session()
    session = next(gen)
    return session, gen


def _safe_commit(session, gen, label: str) -> None:
    try:
        session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit/%s commit failed: %s", label, exc)
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        try:
            next(gen, None)
        except Exception:
            pass


def log_auth_event(
    *,
    event_type: str,
    email: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
) -> None:
    """Login/logout/fail/reset. event_type curto (snake_case)."""
    try:
        from src.storage.audit_models import AuthEventLogORM
        session, gen = _open_session()
        session.add(AuthEventLogORM(
            event_type=event_type,
            email=email,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:500],
            detail=detail,
        ))
        _safe_commit(session, gen, "auth_event_log")
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_auth_event(%s): %s", event_type, exc)


def log_kb_retrieval(
    *,
    user_id: str | None,
    conversation_id: str | None,
    query_text: str,
    intent: str | None,
    kb_sources: list[str],
    chunk_count: int = 0,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
) -> None:
    """Cada chamada de /moon/chat. Query crua nunca persiste — só o sha256."""
    try:
        from src.storage.audit_models import KbRetrievalLogORM
        query_hash = hashlib.sha256((query_text or "").strip().lower().encode("utf-8")).hexdigest()
        session, gen = _open_session()
        session.add(KbRetrievalLogORM(
            user_id=user_id,
            conversation_id=conversation_id,
            query_hash=query_hash,
            intent=intent,
            kb_sources=kb_sources or [],
            chunk_count=str(chunk_count)[:8],
            anthropic_tokens_in=str(tokens_in)[:16] if tokens_in is not None else None,
            anthropic_tokens_out=str(tokens_out)[:16] if tokens_out is not None else None,
            latency_ms=str(latency_ms)[:16] if latency_ms is not None else None,
        ))
        _safe_commit(session, gen, "kb_retrieval_log")
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_kb_retrieval: %s", exc)


def log_admin_action(
    *,
    actor_id: str,
    actor_email: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    before: dict | list | None = None,
    after: dict | list | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Editar moon_config, criar marca, alterar produto, etc. Sempre com diff."""
    try:
        from src.storage.audit_models import AdminActionLogORM
        session, gen = _open_session()
        session.add(AdminActionLogORM(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action[:64],
            target_type=target_type,
            target_id=str(target_id)[:255] if target_id is not None else None,
            before=before,
            after=after,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:500],
        ))
        _safe_commit(session, gen, "admin_action_log")
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_admin_action(%s): %s", action, exc)
