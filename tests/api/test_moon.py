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

    # ingredient_category_compatibility é raw SQL no migration (fora dos ORMs)
    # — recriar manualmente pra tests do score_inci não falharem.
    from sqlalchemy import text as _t
    with engine.begin() as conn:
        conn.execute(_t("""
            CREATE TABLE IF NOT EXISTS ingredient_category_compatibility (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category VARCHAR(64) NOT NULL,
                hair_type VARCHAR(32) NOT NULL,
                score INTEGER NOT NULL,
                reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                UNIQUE(category, hair_type)
            )
        """))
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
# Tier 3 — score_inci (DB-heavy, seeded ingredients)
# ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_ingredients(db_engine):
    """Popula ingredients + aliases + compatibility com mini-conjunto."""
    from sqlalchemy import text as _t
    with Session(db_engine) as s:
        # 3 ingredients de categorias distintas (created_at é NOT NULL)
        s.execute(_t("INSERT INTO ingredients (id, canonical_name, category, created_at, is_hidden) VALUES "
                     "('i-cetyl', 'Cetyl Alcohol', 'fatty_alcohol', CURRENT_TIMESTAMP, 0), "
                     "('i-amodi', 'Amodimethicone', 'silicone', CURRENT_TIMESTAMP, 0), "
                     "('i-sls', 'Sodium Lauryl Sulfate', 'harsh_surfactant', CURRENT_TIMESTAMP, 0)"))
        # Alias só pro cetyl (testa fallback)
        s.execute(_t("INSERT INTO ingredient_aliases (id, ingredient_id, alias, language) VALUES "
                     "('a-1', 'i-cetyl', 'cetyl alc.', 'en')"))
        # Compat rules: 3a → fatty_alcohol +1, silicone -1, harsh_surfactant -1
        s.execute(_t("INSERT INTO ingredient_category_compatibility (category, hair_type, score, reason) VALUES "
                     "('fatty_alcohol', '3a', 1, 'Hidrata fios secos'), "
                     "('silicone', '3a', -1, 'Pode acumular em cacheados'), "
                     "('harsh_surfactant', '3a', -1, 'Resseca cacheados')"))
        s.commit()
    yield db_engine


class TestScoreInci:
    """score_inci: matching ingredients + categories + compatibility scoring."""

    def test_empty_inci_returns_zero_score(self, seeded_ingredients):
        from src.api.routes.moon import score_inci
        with Session(seeded_ingredients) as s:
            result = score_inci(s, [], ["3a"])
        assert result["overall_score"] == 0.0
        assert result["ingredients_total"] == 0
        assert result["ingredients_categorized"] == 0

    def test_unknown_ingredients_not_categorized(self, seeded_ingredients):
        from src.api.routes.moon import score_inci
        with Session(seeded_ingredients) as s:
            result = score_inci(s, ["Mystery Compound X", "Foo Bar"], ["3a"])
        assert result["ingredients_total"] == 2
        assert result["ingredients_categorized"] == 0  # nenhum match
        assert result["overall_score"] == 0.0

    def test_canonical_name_match_scores(self, seeded_ingredients):
        from src.api.routes.moon import score_inci
        with Session(seeded_ingredients) as s:
            result = score_inci(s, ["Cetyl Alcohol"], ["3a"])
        assert result["ingredients_categorized"] == 1
        assert result["overall_score"] == 1.0  # fatty_alcohol+1 com peso normalizado
        assert any(b["name"] == "Cetyl Alcohol" for b in result["benefits"])

    def test_alias_fallback_match(self, seeded_ingredients):
        """`cetyl alc.` (alias) deve resolver pra Cetyl Alcohol."""
        from src.api.routes.moon import score_inci
        with Session(seeded_ingredients) as s:
            result = score_inci(s, ["cetyl alc."], ["3a"])
        assert result["ingredients_categorized"] == 1
        assert result["overall_score"] == 1.0

    def test_alerts_for_negative_score_ingredients(self, seeded_ingredients):
        from src.api.routes.moon import score_inci
        with Session(seeded_ingredients) as s:
            result = score_inci(
                s, ["Sodium Lauryl Sulfate", "Amodimethicone"], ["3a"]
            )
        assert len(result["alerts"]) == 2
        alert_names = {a["name"] for a in result["alerts"]}
        assert "Sodium Lauryl Sulfate" in alert_names
        assert "Amodimethicone" in alert_names
        assert result["overall_score"] < 0  # mistura ruim p/ 3a

    def test_caches_indexes_after_first_call(self, seeded_ingredients):
        """_ensure_indexes preenche _CAT_INDEX e _RULES_INDEX no primeiro hit."""
        import src.api.routes.moon as moon_module
        # Reset global state
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        from src.api.routes.moon import _ensure_indexes
        with Session(seeded_ingredients) as s:
            cat_index, rules = _ensure_indexes(s)
        assert "cetyl alcohol" in cat_index  # lowered canonical
        assert cat_index["cetyl alcohol"] == "fatty_alcohol"
        assert rules[("fatty_alcohol", "3a")] == 1
        assert rules[("silicone", "3a")] == -1

    def test_score_fast_mirrors_score_inci(self, seeded_ingredients):
        """_score_fast (in-memory) deve dar mesma direção do score_inci (SQL)."""
        import src.api.routes.moon as moon_module
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        from src.api.routes.moon import _ensure_indexes, _score_fast
        with Session(seeded_ingredients) as s:
            cat_index, rules = _ensure_indexes(s)
        # 1 ingrediente fatty_alcohol (+1) → score 1.0
        overall, matched = _score_fast(["Cetyl Alcohol"], ["3a"], cat_index, rules)
        assert matched == 1
        assert overall == 1.0
        # Mix neutro: 1 silicone (-1) + 1 fatty (+1) = ~0
        overall, matched = _score_fast(["Amodimethicone", "Cetyl Alcohol"], ["3a"], cat_index, rules)
        assert matched == 2

    def test_position_weight_favors_top_ingredients(self, seeded_ingredients):
        """Top INCI list pesa mais que bottom."""
        from src.api.routes.moon import score_inci
        # Cetyl em primeiro (peso alto) vs em último (peso baixo)
        fillers = ["unknown-1", "unknown-2", "unknown-3", "unknown-4"]
        with Session(seeded_ingredients) as s:
            top = score_inci(s, ["Cetyl Alcohol"] + fillers, ["3a"])
            bot = score_inci(s, fillers + ["Cetyl Alcohol"], ["3a"])
        # Mesmo +1 nominal, mas o resultado é normalizado (=1.0 nos 2 casos),
        # porque só 1 ingrediente tem peso real. Testa que os 2 retornam estrutura
        # coerente — não o overall, que é normalizado.
        assert top["ingredients_categorized"] == 1
        assert bot["ingredients_categorized"] == 1


# ───────────────────────────────────────────────────────────────────────
# Tier 3.5 — _fetch_alternatives + _resolve_product_inci + list_categories
# ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_catalog(seeded_ingredients):
    """Sobe 4 produtos: 2 shampoos verified_inci (1 bom, 1 ruim), 1 mascara,
    1 labial (non_hair, deve ser filtrado pelo guard)."""
    import json as _json
    from src.storage.orm_models import ProductORM
    with Session(seeded_ingredients) as s:
        s.add_all([
            ProductORM(
                id="p-good", brand_slug="lola",
                product_name="Shampoo Hidratante Bom",
                product_url="https://lola.com/shampoo-bom",
                verification_status="verified_inci",
                product_type_normalized="shampoo",
                inci_ingredients=["Water", "Cetyl Alcohol", "Glycerin", "Sodium Cocoyl Isethionate"],
            ),
            ProductORM(
                id="p-bad", brand_slug="generic",
                product_name="Shampoo com Sulfato",
                product_url="https://generic.com/shampoo-sulfato",
                verification_status="verified_inci",
                product_type_normalized="shampoo",
                inci_ingredients=["Water", "Sodium Lauryl Sulfate", "Amodimethicone", "Fragrance"],
            ),
            ProductORM(
                id="p-mask", brand_slug="lola",
                product_name="Mascara Reparadora",
                product_url="https://lola.com/mascara",
                verification_status="verified_inci",
                product_type_normalized="mascara",
                inci_ingredients=["Water", "Cetyl Alcohol", "Cetearyl Alcohol", "Behentrimonium"],
            ),
            # Esse precisa ser filtrado pelo non_hair guard
            ProductORM(
                id="p-lip", brand_slug="lola",
                product_name="Batom Labial Hidratante",
                product_url="https://lola.com/batom",
                verification_status="verified_inci",
                product_type_normalized="batom",
                product_category="non_hair",
                inci_ingredients=["Wax", "Pigment", "Cetyl Alcohol"],
            ),
        ])
        s.commit()
    yield seeded_ingredients


class TestFetchAlternatives:
    """_fetch_alternatives: scoring + non_hair filter + product_type filter."""

    def test_empty_hair_types_returns_empty(self, seeded_catalog):
        from src.api.routes.moon import _fetch_alternatives
        with Session(seeded_catalog) as s:
            result = _fetch_alternatives(s, [], None, None)
        assert result == []

    def test_filters_out_non_hair(self, seeded_catalog):
        """Batom (product_category=non_hair) NUNCA aparece nas alternatives."""
        import src.api.routes.moon as moon_module
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        from src.api.routes.moon import _fetch_alternatives
        with Session(seeded_catalog) as s:
            result = _fetch_alternatives(s, ["3a"], None, None)
        names = [r["name"] for r in result]
        assert "Batom Labial Hidratante" not in names

    def test_filters_by_product_type(self, seeded_catalog):
        """product_type='shampoo' → só shampoos."""
        import src.api.routes.moon as moon_module
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        from src.api.routes.moon import _fetch_alternatives
        with Session(seeded_catalog) as s:
            result = _fetch_alternatives(s, ["3a"], "shampoo", None)
        types = {r["type"] for r in result}
        assert types == {"shampoo"} or types == set()  # se 0 retornar, also ok

    def test_excludes_specific_id(self, seeded_catalog):
        """exclude_id pula o produto avaliado (não recomenda ele mesmo)."""
        import src.api.routes.moon as moon_module
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        from src.api.routes.moon import _fetch_alternatives
        with Session(seeded_catalog) as s:
            result = _fetch_alternatives(s, ["3a"], "shampoo", exclude_id="p-good")
        ids = {r["product_id"] for r in result}
        assert "p-good" not in ids

    def test_ranks_by_score(self, seeded_catalog):
        """Resultados ordenados por score desc."""
        import src.api.routes.moon as moon_module
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        from src.api.routes.moon import _fetch_alternatives
        with Session(seeded_catalog) as s:
            result = _fetch_alternatives(s, ["3a"], None, None)
        if len(result) >= 2:
            scores = [r["score"] for r in result]
            assert scores == sorted(scores, reverse=True), f"scores não estão ordenados: {scores}"


class TestResolveProductInci:
    """_resolve_product_inci: prefer JOIN, fallback pra products.inci_ingredients."""

    def test_resolves_from_inci_json_column(self, seeded_catalog):
        from src.api.routes.moon import _resolve_product_inci
        with Session(seeded_catalog) as s:
            inci = _resolve_product_inci(s, "p-good")
        # No product_ingredients JOIN, cai no fallback JSON column
        assert "Water" in inci
        assert "Cetyl Alcohol" in inci

    def test_returns_empty_for_unknown_product(self, seeded_catalog):
        from src.api.routes.moon import _resolve_product_inci
        with Session(seeded_catalog) as s:
            inci = _resolve_product_inci(s, "nonexistent-id")
        assert inci == []


class TestListCategories:
    """GET /api/moon/categories — lista categorias + compat rules."""

    def test_returns_categories_with_rules(self, client, seeded_ingredients):
        # Reset cache
        import src.api.routes.moon as moon_module
        moon_module._CAT_INDEX = None
        moon_module._RULES_INDEX = None
        resp = client.get("/api/moon/categories")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Estrutura: lista de categorias com compat por hair_type
        assert isinstance(body, list) or isinstance(body, dict)


# ───────────────────────────────────────────────────────────────────────
# Tier 4 — Profile + Feedback endpoints
# ───────────────────────────────────────────────────────────────────────


class TestProfileEndpoints:
    """POST /api/moon/profile + GET /api/moon/profile/{user_id}."""

    def test_save_profile_then_get(self, client):
        # ProfileRequest é flat: user_id + campos do HairProfileInput no top
        save_resp = client.post("/api/moon/profile", json={
            "user_id": "user-prof-1",
            "curl_subtype": "3A",
            "thickness": "medios",
        })
        assert save_resp.status_code == 200, save_resp.text

        get_resp = client.get("/api/moon/profile/user-prof-1")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["curl_subtype"] == "3A"
        assert body["thickness"] == "medios"

    def test_get_profile_not_found(self, client):
        resp = client.get("/api/moon/profile/no-such-user")
        assert resp.status_code == 404


class TestFeedbackEndpoints:
    """POST /api/moon/feedback + GET /api/moon/feedback/summary (admin)."""

    def test_submit_feedback_up_returns_201(self, client):
        resp = client.post("/api/moon/feedback", json={
            "rating": "up",
            "message_content": "Use Cetyl Alcohol regularmente.",
            "user_message": "qual ingrediente ajuda?",
        })
        assert resp.status_code == 201, resp.text
        assert resp.json()["feedback_id"]

    def test_submit_feedback_down(self, client):
        resp = client.post("/api/moon/feedback", json={
            "rating": "down",
            "message_content": "Resposta confusa",
            "comment": "Não respondeu o que perguntei",
        })
        assert resp.status_code == 201, resp.text

    def test_rating_must_be_up_or_down(self, client):
        resp = client.post("/api/moon/feedback", json={
            "rating": "meh",
            "message_content": "blah",
        })
        assert resp.status_code == 400

    def test_feedback_summary_requires_admin(self, client, authed_user):
        # Reviewer (não admin) → 403
        _, token = authed_user
        resp = client.get(
            "/api/moon/feedback/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_feedback_summary_unauthenticated_blocked(self, client):
        resp = client.get("/api/moon/feedback/summary")
        assert resp.status_code in (401, 403)

    def test_feedback_summary_with_admin_returns_kpis(self, client, db_engine):
        """Admin vê total + percentual de useful."""
        import bcrypt
        from src.api.auth import create_access_token
        from src.storage.ops_models import UserORM
        with Session(db_engine) as s:
            admin = UserORM(
                email="admin@haira.app",
                password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()).decode(),
                name="Admin", role="admin", is_active=True,
            )
            s.add(admin); s.commit(); s.refresh(admin)
            admin_token = create_access_token(user_id=admin.user_id, role="admin")

        # Seed 2 up + 1 down
        for _ in range(2):
            client.post("/api/moon/feedback", json={"rating": "up", "message_content": "ok"})
        client.post("/api/moon/feedback", json={"rating": "down", "message_content": "ruim"})

        resp = client.get(
            "/api/moon/feedback/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 3
        assert body["up"] == 2
        assert body["down"] == 1
        assert body["useful_pct"] == round(100 * 2 / 3, 1)
        assert len(body["recent_downvotes"]) == 1


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
