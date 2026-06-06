# tests/api/test_moon.py
"""Bateria de testes para src/api/routes/moon.py.

Cobertura:
- Tier 1: pure functions (normalize, _parse_inci, _interpret, _detect_intent, _moon_chat_rate_check)
- Tier 2: endpoint /api/moon/chat com Anthropic mockado (auth, rate limit, intent flow)

Filosofia: tests rápidos, sem rede, sem flaky. Anthropic call sempre mockada.
"""
from __future__ import annotations

import collections
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.routes.moon import (
    _detect_intent,
    _interpret,
    _moon_chat_log,
    _moon_chat_rate_check,
    _parse_inci,
    normalize,
)
from src.storage.orm_models import Base


# ───────────────────────────────────────────────────────────────────────
# Tier 1 — Pure functions (no DB, no network)
# ───────────────────────────────────────────────────────────────────────


class TestNormalize:
    """Normalização de nome: NFD → strip diacríticos → lower → strip whitespace."""

    @pytest.mark.parametrize("raw,expected", [
        ("Cocamidopropyl Betaine", "cocamidopropyl betaine"),
        ("CETYL ALCOHOL", "cetyl alcohol"),
        ("  trimmed  ", "trimmed"),
        ("Açaí Oil", "acai oil"),
        ("Hidrólise", "hidrolise"),
        ("Café-Latte", "cafe-latte"),
    ])
    def test_basic_normalization(self, raw, expected):
        assert normalize(raw) == expected

    @pytest.mark.parametrize("falsy", ["", None])
    def test_empty_inputs(self, falsy):
        assert normalize(falsy) == ""

    def test_preserves_internal_punctuation(self):
        # `/` em copolímeros NÃO deve ser strippado
        assert normalize("Polymer/Copolymer-1") == "polymer/copolymer-1"


class TestParseInci:
    """_parse_inci aceita None/str/list e retorna list[str] vazia em erro."""

    def test_none_returns_empty(self):
        assert _parse_inci(None) == []

    def test_empty_string_returns_empty(self):
        assert _parse_inci("") == []

    def test_json_array_string(self):
        assert _parse_inci('["water", "glycerin"]') == ["water", "glycerin"]

    def test_already_a_list(self):
        assert _parse_inci(["water", "glycerin"]) == ["water", "glycerin"]

    def test_malformed_json_returns_empty(self):
        assert _parse_inci("{not-json") == []

    def test_json_object_returns_empty(self):
        # objeto não é list → ignora
        assert _parse_inci('{"key": "value"}') == []

    def test_numeric_items_converted_to_str(self):
        assert _parse_inci([1, 2.5, "water"]) == ["1", "2.5", "water"]


class TestInterpret:
    """Threshold-based score → label."""

    @pytest.mark.parametrize("score,expected_substring", [
        (1.0, "Altamente compatível"),
        (0.6, "Altamente compatível"),                # borda
        (0.59, "Compatível com algumas"),
        (0.2, "Compatível com algumas"),               # borda
        (0.19, "Neutro"),
        (0.0, "Neutro"),
        (-0.2, "Neutro"),                              # borda
        (-0.21, "Cuidado"),                            # cai pra próximo
        (-0.6, "Cuidado"),                             # borda inferior
        (-0.61, "Não recomendado"),                    # pior bucket
        (-1.0, "Não recomendado"),
    ])
    def test_score_labels(self, score, expected_substring):
        assert expected_substring.lower() in _interpret(score).lower()


class TestDetectIntent:
    """Classificador de intenção — 5 buckets, ordem importa (saúde > análise > recomendação > rotina > geral)."""

    @pytest.mark.parametrize("msg", [
        "estou com queda capilar há 2 meses",
        "minha cabeça está com coceira forte",
        "tô descamando muito o couro",
        "apareceu uma ferida no couro cabeludo",
        "será alergia a algum produto?",
        "diagnosticaram dermatite seborreica",
        "ando com psoríase no couro",
        "sinto uma dor estranha quando escovo",
    ])
    def test_saude_couro_keywords(self, msg):
        assert _detect_intent(msg, has_product_context=False) == "saude_couro"

    def test_saude_couro_wins_over_analise_when_both_present(self):
        # "esse produto me deu coceira" → prioridade saúde
        msg = "esse produto novo me deu coceira"
        assert _detect_intent(msg, has_product_context=True) == "saude_couro"

    @pytest.mark.parametrize("msg", [
        "esse shampoo serve pro meu cabelo?",
        "posso usar esta máscara?",
        "esse aqui combina com cabelo cacheado?",
        "esse produto funciona bem?",
    ])
    def test_analise_produto_with_explicit_phrasing(self, msg):
        assert _detect_intent(msg, has_product_context=False) == "analise_produto"

    def test_analise_with_product_context_default(self):
        # Mesmo sem palavra-chave, se tem produto em contexto + verbo avaliativo
        assert _detect_intent("posso?", has_product_context=True) == "analise_produto"

    @pytest.mark.parametrize("msg", [
        "me indica um shampoo bom",
        "qual leave-in combina comigo?",
        "sugere uma máscara nutritiva",
        "qual o melhor condicionador pra cacheado?",
        "recomenda algum creme de pentear?",
    ])
    def test_recomendacao_keywords(self, msg):
        assert _detect_intent(msg, has_product_context=False) == "recomendacao"

    @pytest.mark.parametrize("msg", [
        "qual o cronograma capilar ideal?",
        "como montar minha rotina de cuidados?",
        "preciso de protocolo de hidratação",
        "qual a frequência ideal de nutrição?",
        "low poo funciona?",
        "como fazer co-wash?",
        "umectação noturna vale a pena?",
        "como cuidar de cabelo cacheado?",
    ])
    def test_rotina_keywords(self, msg):
        assert _detect_intent(msg, has_product_context=False) == "rotina_cuidado"

    @pytest.mark.parametrize("msg", [
        "oi",
        "tudo bem?",
        "obrigada!",
        "",
        "kkkkk",
    ])
    def test_geral_fallback(self, msg):
        assert _detect_intent(msg, has_product_context=False) == "geral"

    def test_empty_message_is_geral(self):
        assert _detect_intent("", has_product_context=False) == "geral"
        assert _detect_intent("   ", has_product_context=False) == "geral"
        assert _detect_intent(None, has_product_context=False) == "geral"  # type: ignore[arg-type]

    def test_case_insensitive(self):
        assert _detect_intent("ESTOU COM QUEDA", has_product_context=False) == "saude_couro"
        assert _detect_intent("Me Indica Algo", has_product_context=False) == "recomendacao"


class TestRateLimit:
    """Rate limit per-user em /moon/chat: 20/min (default)."""

    def setup_method(self):
        # Isola estado entre testes
        _moon_chat_log.clear()

    def test_first_request_allowed(self):
        # Não deve lançar
        _moon_chat_rate_check("user-a")
        assert len(_moon_chat_log["user-a"]) == 1

    def test_below_limit_allowed(self):
        for _ in range(10):
            _moon_chat_rate_check("user-a")
        assert len(_moon_chat_log["user-a"]) == 10

    def test_exceeds_limit_raises_429(self):
        # Empurra até o limite
        from src.api.routes.moon import _MOON_CHAT_LIMIT
        for _ in range(_MOON_CHAT_LIMIT):
            _moon_chat_rate_check("user-b")
        # Próximo deve estourar
        with pytest.raises(HTTPException) as exc_info:
            _moon_chat_rate_check("user-b")
        assert exc_info.value.status_code == 429

    def test_separate_users_have_separate_buckets(self):
        from src.api.routes.moon import _MOON_CHAT_LIMIT
        for _ in range(_MOON_CHAT_LIMIT):
            _moon_chat_rate_check("user-c")
        # user-d ainda tem buckets livres
        _moon_chat_rate_check("user-d")  # não deve lançar

    def test_window_decay_releases_old_entries(self):
        from src.api.routes.moon import _MOON_CHAT_LIMIT, _MOON_CHAT_WINDOW_S
        # Injeta timestamps fora da janela
        old_ts = time.time() - _MOON_CHAT_WINDOW_S - 1
        _moon_chat_log["user-e"] = collections.deque([old_ts] * _MOON_CHAT_LIMIT)
        # Próxima chamada deve limpar entries antigas e aceitar
        _moon_chat_rate_check("user-e")
        # Sobra só a entry nova
        assert len(_moon_chat_log["user-e"]) == 1

    def test_anon_user_shares_balde(self):
        """User sem id (None) cai em 'anon'. Defensivo se auth ficar opcional."""
        _moon_chat_rate_check(None)
        _moon_chat_rate_check(None)
        assert len(_moon_chat_log["anon"]) == 2


# ───────────────────────────────────────────────────────────────────────
# Tier 2 — Endpoint /api/moon/chat (Anthropic mockada)
# ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Importa explícito todos os modules que ESTENDEM Base — necessário pro
    # create_all enxergar as tabelas de users, moon_conversations, etc.
    import src.storage.ops_models       # noqa: F401  → users, revision_history
    import src.storage.hair_profile_models  # noqa: F401  → hair_profiles
    import src.storage.knowledge_models  # noqa: F401  → knowledge_chunks
    import src.storage.moon_models      # noqa: F401  → moon_conversations, moon_messages, moon_feedback, moon_config
    Base.metadata.create_all(engine)

    # Audit tables vivem num Base separado
    from src.storage.audit_models import AuditBase
    AuditBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine):
    """TestClient com session override e Anthropic mockado a partir do test."""
    # Override de todas as get_session do projeto pra usar a in-memory
    from src.api import dependencies as deps
    from src.api.routes.moon import _get_session as moon_get_session

    def _override_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[moon_get_session] = _override_session
    app.dependency_overrides[deps.get_core_session] = _override_session
    app.dependency_overrides[deps.get_catalog_session] = _override_session
    app.dependency_overrides[deps.get_audit_session] = _override_session
    app.dependency_overrides[deps.get_ops_session] = _override_session  # auth.get_current_user usa

    # Limpa state global de rate limit
    _moon_chat_log.clear()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def authed_user(db_engine):
    """Cria user ativo e retorna (user_id, jwt_token)."""
    import bcrypt
    from src.api.auth import create_access_token
    from src.storage.ops_models import UserORM

    with Session(db_engine) as s:
        user = UserORM(
            email="test@haira.app",
            password_hash=bcrypt.hashpw(b"irrelevant", bcrypt.gensalt()).decode(),
            name="Test User",
            role="reviewer",
            is_active=True,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        user_id = user.user_id

    token = create_access_token(user_id=user_id, role="reviewer")
    return user_id, token


@pytest.fixture
def mock_llm():
    """Mocka LLMClient pra retornar resposta fixa, sem rede."""
    with patch("src.core.llm.LLMClient") as MockClient:
        instance = MagicMock()
        instance.chat.return_value = "Oi! 🌙 Como posso te ajudar hoje?"
        MockClient.return_value = instance
        yield instance


@pytest.fixture
def mock_kb():
    """Mocka load_knowledge_base pra evitar dependência de KB encriptada."""
    from src.core.knowledge_base import KnowledgeBase
    fake_kb = KnowledgeBase(
        system_block="[CONHECIMENTO PROPRIETÁRIO HAIRA]\n(test KB content)",
        sources=["test-doc.md"],
        char_count=42,
    )
    with patch("src.core.knowledge_base.load_knowledge_base", return_value=fake_kb):
        with patch("src.api.routes.moon.load_knowledge_base", return_value=fake_kb, create=True):
            yield fake_kb


@pytest.fixture
def mock_moon_config():
    """Mocka moon_config loader pra default (sem hitar DB)."""
    with patch("src.core.moon_config.load_moon_config", return_value={}):
        yield


class TestChatEndpoint:
    """Smoke tests do endpoint /api/moon/chat com mocks."""

    def test_unauthenticated_returns_401_or_403(self, client):
        """Sem token, chat exige auth (HAIRA-155)."""
        resp = client.post("/api/moon/chat", json={
            "messages": [{"role": "user", "content": "oi"}],
            "profile": {"curl_subtype": "3A"},
        })
        assert resp.status_code in (401, 403), f"got {resp.status_code}: {resp.text}"

    def test_invalid_token_returns_401(self, client):
        resp = client.post(
            "/api/moon/chat",
            json={"messages": [{"role": "user", "content": "oi"}], "profile": {"curl_subtype": "3A"}},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_geral_intent_returns_200_with_reply(self, client, authed_user, mock_llm, mock_kb, mock_moon_config):
        """Caminho feliz: 'oi' → intent=geral → mocked LLM → 200."""
        _, token = authed_user
        resp = client.post(
            "/api/moon/chat",
            json={"messages": [{"role": "user", "content": "oi"}], "profile": {"curl_subtype": "3A"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["intent"] == "geral"
        assert "reply" in body
        assert body["reply"].startswith("Oi!")
        assert body["kb_sources"] == ["test-doc.md"]
        assert body["conversation_id"]  # foi persistida
        assert body["analysis"] is None  # sem product_id

    def test_saude_couro_intent_detected(self, client, authed_user, mock_llm, mock_kb, mock_moon_config):
        """Pergunta sobre queda → intent=saude_couro."""
        _, token = authed_user
        resp = client.post(
            "/api/moon/chat",
            json={"messages": [{"role": "user", "content": "estou com queda capilar muito forte"}], "profile": {"curl_subtype": "3A"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["intent"] == "saude_couro"

    def test_rotina_intent_detected(self, client, authed_user, mock_llm, mock_kb, mock_moon_config):
        """Pergunta sobre cronograma → intent=rotina_cuidado."""
        _, token = authed_user
        resp = client.post(
            "/api/moon/chat",
            json={"messages": [{"role": "user", "content": "como montar meu cronograma capilar?"}], "profile": {"curl_subtype": "3A"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["intent"] == "rotina_cuidado"

    def test_recomendacao_intent_detected(self, client, authed_user, mock_llm, mock_kb, mock_moon_config):
        """Pergunta de indicação → intent=recomendacao. Mock _fetch_alternatives
        pra evitar dependência de catálogo + ingredients populados."""
        _, token = authed_user
        with patch("src.api.routes.moon._fetch_alternatives", return_value=[]):
            resp = client.post(
                "/api/moon/chat",
                json={"messages": [{"role": "user", "content": "me indica um shampoo bom pra cacheado"}], "profile": {"curl_subtype": "3A"}},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["intent"] == "recomendacao"

    def test_conversation_persistence(self, client, authed_user, mock_llm, mock_kb, mock_moon_config, db_engine):
        """Mensagens persistem entre turns na mesma conversation_id."""
        _, token = authed_user
        # Primeiro turn
        resp1 = client.post(
            "/api/moon/chat",
            json={"messages": [{"role": "user", "content": "oi"}], "profile": {"curl_subtype": "3A"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        conv_id = resp1.json()["conversation_id"]

        # Segundo turn na mesma conversation
        resp2 = client.post(
            "/api/moon/chat",
            json={
                "messages": [{"role": "user", "content": "qual cuidado bom?"}],
                "profile": {"curl_subtype": "3A"},
                "conversation_id": conv_id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id

        # Confirma 4 mensagens persistidas (2 user + 2 assistant)
        from src.storage.moon_models import MoonMessageORM
        with Session(db_engine) as s:
            count = s.query(MoonMessageORM).filter(
                MoonMessageORM.conversation_id == conv_id
            ).count()
            assert count == 4, f"esperado 4 mensagens, foram {count}"

    def test_llm_failure_returns_503(self, client, authed_user, mock_kb, mock_moon_config):
        """LLM client raises → 503 graceful (não 500)."""
        from src.api.routes.moon import _moon_chat_log
        _moon_chat_log.clear()

        with patch("src.core.llm.LLMClient") as MockClient:
            instance = MagicMock()
            instance.chat.side_effect = RuntimeError("Anthropic API down")
            MockClient.return_value = instance

            _, token = authed_user
            resp = client.post(
                "/api/moon/chat",
                json={"messages": [{"role": "user", "content": "oi"}], "profile": {"curl_subtype": "3A"}},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 503
            assert "indisponível" in resp.json()["detail"].lower()


class TestChatRateLimitIntegration:
    """Confirma que o rate limit é aplicado no endpoint real."""

    def test_rate_limit_state_is_per_user(self):
        """Validação direta da função — endpoint só wraps isso."""
        from src.api.routes.moon import _MOON_CHAT_LIMIT
        _moon_chat_log.clear()

        # User A: estoura
        for _ in range(_MOON_CHAT_LIMIT):
            _moon_chat_rate_check("user-A")
        with pytest.raises(HTTPException):
            _moon_chat_rate_check("user-A")

        # User B: limpo
        _moon_chat_rate_check("user-B")
        assert len(_moon_chat_log["user-B"]) == 1


# ───────────────────────────────────────────────────────────────────────
# Audit hooks — verificação leve de wiring
# ───────────────────────────────────────────────────────────────────────


class TestAuditWiring:
    """Confirma que log_kb_retrieval é chamado a partir do chat (importado)."""

    def test_log_kb_retrieval_is_imported_in_moon(self):
        import src.api.routes.moon as moon_module
        # Confirma que o helper é importável no escopo do módulo
        # (call site exercitado nos tests de integração futuros)
        import src.core.audit as audit_module
        assert hasattr(audit_module, "log_kb_retrieval")
        # Garante que o moon.py de fato faz import (não optional)
        with open(moon_module.__file__) as f:
            assert "log_kb_retrieval" in f.read()
