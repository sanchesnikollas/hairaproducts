"""Read-only viewer pra audit logs (admin-only).

- GET /api/admin/audit/auth-events
- GET /api/admin/audit/admin-actions
- GET /api/admin/audit/kb-retrievals
- GET /api/admin/audit/summary           # KPIs agregados

Cada um aceita ?limit=N (default 100, max 500). Filtros opcionais por
query string (email, action, intent, date_from, date_to).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_audit_session
from src.storage.audit_models import (
    AdminActionLogORM,
    AuthEventLogORM,
    KbRetrievalLogORM,
)

router = APIRouter(prefix="/admin/audit", tags=["admin"])


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/auth-events")
def list_auth_events(
    limit: int = Query(default=100, ge=1, le=500),
    email: str | None = None,
    event_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_audit_session),
):
    """Lista os auth events mais recentes (default 100). Filtros opcionais."""
    q = session.query(AuthEventLogORM).order_by(AuthEventLogORM.created_at.desc())
    if email:
        q = q.filter(AuthEventLogORM.email == email)
    if event_type:
        q = q.filter(AuthEventLogORM.event_type == event_type)
    if (df := _parse_date(date_from)):
        q = q.filter(AuthEventLogORM.created_at >= df)
    if (dt := _parse_date(date_to)):
        q = q.filter(AuthEventLogORM.created_at <= dt)
    rows = q.limit(limit).all()
    return {
        "events": [
            {
                "event_id": r.event_id,
                "event_type": r.event_type,
                "email": r.email,
                "user_id": r.user_id,
                "ip_address": r.ip_address,
                "user_agent": (r.user_agent or "")[:120],
                "detail": r.detail,
                "created_at": _iso(r.created_at),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/admin-actions")
def list_admin_actions(
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = None,
    actor_email: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_audit_session),
):
    q = session.query(AdminActionLogORM).order_by(AdminActionLogORM.created_at.desc())
    if action:
        q = q.filter(AdminActionLogORM.action == action)
    if actor_email:
        q = q.filter(AdminActionLogORM.actor_email == actor_email)
    if target_type:
        q = q.filter(AdminActionLogORM.target_type == target_type)
    if target_id:
        q = q.filter(AdminActionLogORM.target_id == target_id)
    if (df := _parse_date(date_from)):
        q = q.filter(AdminActionLogORM.created_at >= df)
    if (dt := _parse_date(date_to)):
        q = q.filter(AdminActionLogORM.created_at <= dt)
    rows = q.limit(limit).all()
    return {
        "actions": [
            {
                "action_id": r.action_id,
                "actor_id": r.actor_id,
                "actor_email": r.actor_email,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "before": r.before,
                "after": r.after,
                "ip_address": r.ip_address,
                "created_at": _iso(r.created_at),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/kb-retrievals")
def list_kb_retrievals(
    limit: int = Query(default=100, ge=1, le=500),
    intent: str | None = None,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_audit_session),
):
    q = session.query(KbRetrievalLogORM).order_by(KbRetrievalLogORM.created_at.desc())
    if intent:
        q = q.filter(KbRetrievalLogORM.intent == intent)
    if user_id:
        q = q.filter(KbRetrievalLogORM.user_id == user_id)
    if (df := _parse_date(date_from)):
        q = q.filter(KbRetrievalLogORM.created_at >= df)
    if (dt := _parse_date(date_to)):
        q = q.filter(KbRetrievalLogORM.created_at <= dt)
    rows = q.limit(limit).all()
    return {
        "retrievals": [
            {
                "log_id": r.log_id,
                "user_id": r.user_id,
                "conversation_id": r.conversation_id,
                "query_hash": r.query_hash,
                "intent": r.intent,
                "kb_sources": r.kb_sources,
                "chunk_count": r.chunk_count,
                "anthropic_tokens_in": r.anthropic_tokens_in,
                "anthropic_tokens_out": r.anthropic_tokens_out,
                "latency_ms": r.latency_ms,
                "created_at": _iso(r.created_at),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/summary")
def audit_summary(
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_audit_session),
):
    """KPIs agregados pra dashboard. Sem filtro — sempre totais all-time."""
    auth_total = session.query(func.count(AuthEventLogORM.event_id)).scalar() or 0
    login_ok = session.query(func.count(AuthEventLogORM.event_id)).filter(
        AuthEventLogORM.event_type == "login_ok"
    ).scalar() or 0
    login_fail = session.query(func.count(AuthEventLogORM.event_id)).filter(
        AuthEventLogORM.event_type == "login_fail"
    ).scalar() or 0
    admin_total = session.query(func.count(AdminActionLogORM.action_id)).scalar() or 0
    kb_total = session.query(func.count(KbRetrievalLogORM.log_id)).scalar() or 0

    # Intent breakdown
    intent_rows = (
        session.query(KbRetrievalLogORM.intent, func.count(KbRetrievalLogORM.log_id))
        .group_by(KbRetrievalLogORM.intent)
        .all()
    )
    by_intent = {(i or "unknown"): int(n) for i, n in intent_rows}

    # Top admin actions
    action_rows = (
        session.query(AdminActionLogORM.action, func.count(AdminActionLogORM.action_id))
        .group_by(AdminActionLogORM.action)
        .order_by(func.count(AdminActionLogORM.action_id).desc())
        .limit(10)
        .all()
    )
    top_actions = [{"action": a, "count": int(n)} for a, n in action_rows]

    return {
        "auth": {
            "total": int(auth_total),
            "login_ok": int(login_ok),
            "login_fail": int(login_fail),
            "fail_rate_pct": round((login_fail / (login_ok + login_fail) * 100), 1)
            if (login_ok + login_fail) > 0 else None,
        },
        "admin_actions": {
            "total": int(admin_total),
            "top": top_actions,
        },
        "kb_retrievals": {
            "total": int(kb_total),
            "by_intent": by_intent,
        },
    }
