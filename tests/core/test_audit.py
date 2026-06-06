# tests/core/test_audit.py
"""Bateria de testes para src/core/audit.py — fire-and-forget audit helpers.

Cobertura crítica:
- log_auth_event: cada event_type vira row, user_agent truncado em 500
- log_kb_retrieval: query crua NUNCA persiste — só sha256
- log_admin_action: before/after JSON aceitos como dict E list
- Resiliência: DB caindo NÃO derruba a chamada (fire-and-forget)
"""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def audit_db():
    """In-memory SQLite com só as tabelas de audit."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from src.storage.audit_models import AuditBase
    AuditBase.metadata.create_all(engine)

    # Patch get_audit_session pra usar essa DB
    from src.api import dependencies as deps

    def _override():
        with Session(engine) as session:
            yield session

    original = getattr(deps, "_audit_engine", None)
    deps.set_audit_engine(engine)
    yield engine
    deps.set_audit_engine(original)


# ───────────────────────────────────────────────────────────────────────
# log_auth_event
# ───────────────────────────────────────────────────────────────────────


class TestLogAuthEvent:
    """6 event_types: login_ok, login_fail, logout, admin_reset_ok, admin_reset_fail,
    + qualquer outro custom."""

    def test_persists_basic_login_ok(self, audit_db):
        from src.core.audit import log_auth_event
        from src.storage.audit_models import AuthEventLogORM

        log_auth_event(
            event_type="login_ok",
            email="user@haira.app",
            user_id="user-123",
            ip_address="10.0.0.1",
        )

        with Session(audit_db) as s:
            row = s.query(AuthEventLogORM).first()
            assert row is not None
            assert row.event_type == "login_ok"
            assert row.email == "user@haira.app"
            assert row.user_id == "user-123"
            assert row.ip_address == "10.0.0.1"

    def test_login_fail_with_detail(self, audit_db):
        from src.core.audit import log_auth_event
        from src.storage.audit_models import AuthEventLogORM

        log_auth_event(
            event_type="login_fail",
            email="bad@haira.app",
            ip_address="10.0.0.1",
            detail="bad password",
        )

        with Session(audit_db) as s:
            row = s.query(AuthEventLogORM).first()
            assert row.event_type == "login_fail"
            assert row.detail == "bad password"
            assert row.user_id is None  # não logou

    def test_user_agent_truncated_at_500(self, audit_db):
        """UA longuíssimo (bot, etc.) NÃO estoura a coluna."""
        from src.core.audit import log_auth_event
        from src.storage.audit_models import AuthEventLogORM

        huge_ua = "X" * 2000
        log_auth_event(event_type="login_ok", email="u@x.com", user_agent=huge_ua)

        with Session(audit_db) as s:
            row = s.query(AuthEventLogORM).first()
            assert len(row.user_agent) == 500

    def test_none_user_agent_becomes_empty_str(self, audit_db):
        from src.core.audit import log_auth_event
        from src.storage.audit_models import AuthEventLogORM

        log_auth_event(event_type="logout", user_id="u1", user_agent=None)
        with Session(audit_db) as s:
            row = s.query(AuthEventLogORM).first()
            assert row.user_agent == ""

    def test_db_failure_does_not_propagate(self):
        """Audit DB caindo NÃO propaga exception pro caller (fire-and-forget)."""
        from src.core.audit import log_auth_event
        with patch("src.api.dependencies.get_audit_session", side_effect=RuntimeError("DB down")):
            # Não deve levantar — falha silenciosa com log warning
            log_auth_event(event_type="login_ok", email="u@x.com")


# ───────────────────────────────────────────────────────────────────────
# log_kb_retrieval — PRIVACIDADE CRÍTICA
# ───────────────────────────────────────────────────────────────────────


class TestLogKbRetrieval:
    """O sha256(query) sai certo, query crua NUNCA é persistida."""

    def test_query_text_not_persisted_raw(self, audit_db):
        """Verifica que a pergunta crua NÃO aparece no DB — só hash."""
        from src.core.audit import log_kb_retrieval
        from src.storage.audit_models import KbRetrievalLogORM

        secret_query = "como cuidar do meu cabelo crespo descolorido"
        log_kb_retrieval(
            user_id="u1", conversation_id="c1",
            query_text=secret_query,
            intent="rotina_cuidado", kb_sources=["compendio.md"], chunk_count=3,
        )

        with Session(audit_db) as s:
            row = s.query(KbRetrievalLogORM).first()
            assert row is not None
            # Pergunta crua não aparece em CAMPO ALGUM
            for col_value in [row.query_hash, row.intent, str(row.kb_sources)]:
                assert secret_query.lower() not in (col_value or "").lower()
            # Mas hash bate
            expected = hashlib.sha256(secret_query.strip().lower().encode("utf-8")).hexdigest()
            assert row.query_hash == expected

    def test_query_normalized_before_hashing(self, audit_db):
        """Lower + strip antes do sha256 (detecta dúvidas recorrentes apesar de variação)."""
        from src.core.audit import log_kb_retrieval
        from src.storage.audit_models import KbRetrievalLogORM

        # Mesma pergunta, variando case e whitespace
        log_kb_retrieval(user_id="u1", conversation_id="c1",
                        query_text="  Como cuidar?  ",
                        intent="geral", kb_sources=[])
        log_kb_retrieval(user_id="u2", conversation_id="c2",
                        query_text="como cuidar?",
                        intent="geral", kb_sources=[])

        with Session(audit_db) as s:
            rows = s.query(KbRetrievalLogORM).all()
            assert len(rows) == 2
            # Mesmo hash em ambas
            assert rows[0].query_hash == rows[1].query_hash

    def test_empty_query_still_hashed(self, audit_db):
        """Edge: query vazia ainda produz hash (sha256("") consistente)."""
        from src.core.audit import log_kb_retrieval
        from src.storage.audit_models import KbRetrievalLogORM

        log_kb_retrieval(user_id="u1", conversation_id="c1",
                        query_text="", intent="geral", kb_sources=[])

        with Session(audit_db) as s:
            row = s.query(KbRetrievalLogORM).first()
            assert row.query_hash == hashlib.sha256(b"").hexdigest()

    def test_kb_sources_default_to_empty_list(self, audit_db):
        from src.core.audit import log_kb_retrieval
        from src.storage.audit_models import KbRetrievalLogORM

        log_kb_retrieval(user_id="u1", conversation_id=None,
                        query_text="hello", intent=None, kb_sources=[])

        with Session(audit_db) as s:
            row = s.query(KbRetrievalLogORM).first()
            assert row.kb_sources == []

    def test_db_failure_silent(self):
        """Falha de DB no audit NÃO impacta chat()."""
        from src.core.audit import log_kb_retrieval
        with patch("src.api.dependencies.get_audit_session", side_effect=RuntimeError("DB down")):
            log_kb_retrieval(user_id="u1", conversation_id="c1",
                            query_text="hello", intent=None, kb_sources=[])


# ───────────────────────────────────────────────────────────────────────
# log_admin_action
# ───────────────────────────────────────────────────────────────────────


class TestLogAdminAction:

    def test_persists_action_with_diff(self, audit_db):
        from src.core.audit import log_admin_action
        from src.storage.audit_models import AdminActionLogORM

        log_admin_action(
            actor_id="admin-1", actor_email="admin@haira.com",
            action="brand.update", target_type="brand", target_id="lola",
            before={"name": "old name"}, after={"name": "new name"},
            ip_address="10.0.0.1",
        )

        with Session(audit_db) as s:
            row = s.query(AdminActionLogORM).first()
            assert row.action == "brand.update"
            assert row.target_type == "brand"
            assert row.target_id == "lola"
            assert row.before == {"name": "old name"}
            assert row.after == {"name": "new name"}

    def test_action_name_truncated_at_64(self, audit_db):
        from src.core.audit import log_admin_action
        from src.storage.audit_models import AdminActionLogORM

        huge_action = "x" * 200
        log_admin_action(
            actor_id="admin-1", actor_email=None,
            action=huge_action, target_type=None, target_id=None,
        )
        with Session(audit_db) as s:
            row = s.query(AdminActionLogORM).first()
            assert len(row.action) == 64

    def test_target_id_truncated_at_255(self, audit_db):
        from src.core.audit import log_admin_action
        from src.storage.audit_models import AdminActionLogORM

        huge_id = "y" * 500
        log_admin_action(
            actor_id="admin-1", actor_email=None,
            action="x", target_type=None, target_id=huge_id,
        )
        with Session(audit_db) as s:
            row = s.query(AdminActionLogORM).first()
            assert len(row.target_id) == 255

    def test_before_after_can_be_list(self, audit_db):
        """before/after aceita list além de dict (audit de operações em batch)."""
        from src.core.audit import log_admin_action
        from src.storage.audit_models import AdminActionLogORM

        log_admin_action(
            actor_id="admin-1", actor_email="a@h",
            action="bulk.delete",
            before=[{"id": "p1"}, {"id": "p2"}], after=[],
        )

        with Session(audit_db) as s:
            row = s.query(AdminActionLogORM).first()
            assert isinstance(row.before, list)
            assert len(row.before) == 2

    def test_db_failure_silent(self):
        """DB caindo não propaga exception."""
        from src.core.audit import log_admin_action
        with patch("src.api.dependencies.get_audit_session", side_effect=RuntimeError("DB down")):
            log_admin_action(
                actor_id="admin-1", actor_email="a@h", action="test",
            )
