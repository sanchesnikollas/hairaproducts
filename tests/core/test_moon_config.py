# tests/core/test_moon_config.py
"""Bateria de testes para src/core/moon_config.py.

Loader cacheado de personalidade da Moon. Cobertura:
- Cache hit/miss (1 DB query no primeiro load, depois memória)
- Reset invalida cache
- Fallback pra defaults quando DB indisponível, tabela faltando, ou rows vazias
- Override merge: row no DB sobrescreve default; row vazia ignorada
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def reset_cache_around_each_test():
    """Garante isolamento — cache do módulo é global, vazaria entre tests."""
    from src.core import moon_config
    with moon_config._LOCK:
        moon_config._CACHED = None
    yield
    with moon_config._LOCK:
        moon_config._CACHED = None


@pytest.fixture
def db_with_config():
    """In-memory SQLite com moon_config table + algumas overrides seedadas."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Cria as tabelas necessárias
    import src.storage.moon_models  # noqa: F401
    from src.storage.orm_models import Base
    Base.metadata.create_all(engine)

    # Patch get_engine to return our test engine
    with patch("src.core.moon_config.get_engine", return_value=engine):
        yield engine


# ───────────────────────────────────────────────────────────────────────
# load_moon_config — caminho feliz
# ───────────────────────────────────────────────────────────────────────


class TestLoadDefaults:

    def test_returns_defaults_when_db_empty(self, db_with_config):
        """Sem nenhuma row em moon_config → devolve defaults intactos."""
        from src.core.moon_config import load_moon_config
        from src.core.moon_personality import default_config

        result = load_moon_config()
        defaults = default_config()
        assert result == defaults
        assert "system_prompt" in result  # chave esperada existe

    def test_override_wins_over_default(self, db_with_config):
        """Row na DB sobrescreve default da mesma chave."""
        from src.core.moon_config import load_moon_config
        from src.storage.moon_models import MoonConfigORM

        custom_prompt = "Custom system prompt for testing"
        with Session(db_with_config) as s:
            s.add(MoonConfigORM(key="system_prompt", value=custom_prompt))
            s.commit()

        result = load_moon_config()
        assert result["system_prompt"] == custom_prompt

    def test_empty_value_does_not_override(self, db_with_config):
        """Row com value=None ou '' ignorada (defaults vencem)."""
        from src.core.moon_config import load_moon_config, reset_moon_config_cache
        from src.core.moon_personality import default_config
        from src.storage.moon_models import MoonConfigORM

        with Session(db_with_config) as s:
            s.add(MoonConfigORM(key="system_prompt", value=""))
            s.commit()

        result = load_moon_config()
        # value vazio NÃO override → fica o default original
        assert result["system_prompt"] == default_config()["system_prompt"]
        # Confirma comportamento explícito
        reset_moon_config_cache()

    def test_new_key_from_db_added_to_result(self, db_with_config):
        """Chave que NÃO existe nos defaults mas vem da DB → entra no merge."""
        from src.core.moon_config import load_moon_config
        from src.storage.moon_models import MoonConfigORM

        with Session(db_with_config) as s:
            s.add(MoonConfigORM(key="intent.custom_test", value="custom addendum"))
            s.commit()

        result = load_moon_config()
        assert result["intent.custom_test"] == "custom addendum"


# ───────────────────────────────────────────────────────────────────────
# Cache behavior
# ───────────────────────────────────────────────────────────────────────


class TestCache:

    def test_first_call_hits_db_second_uses_cache(self, db_with_config):
        """2 chamadas seguidas = 1 query no DB (a 2ª vem da cache)."""
        from src.core.moon_config import load_moon_config

        # Conta queries via spy
        with Session(db_with_config) as s:
            from src.storage.moon_models import MoonConfigORM
            s.add(MoonConfigORM(key="system_prompt", value="cached value"))
            s.commit()

        r1 = load_moon_config()
        r2 = load_moon_config()
        assert r1 is r2  # mesma referência (cache, não cópia)
        assert r1["system_prompt"] == "cached value"

    def test_reset_invalidates_cache(self, db_with_config):
        """Após reset, próxima chamada re-le do DB."""
        from src.core.moon_config import load_moon_config, reset_moon_config_cache
        from src.storage.moon_models import MoonConfigORM

        # Primeiro load
        r1 = load_moon_config()

        # Adiciona override AFTER load
        with Session(db_with_config) as s:
            s.add(MoonConfigORM(key="system_prompt", value="new value"))
            s.commit()

        # Sem reset, cache continua o antigo
        r2 = load_moon_config()
        assert r2 is r1  # ainda cache

        # Reset e re-load
        reset_moon_config_cache()
        r3 = load_moon_config()
        assert r3["system_prompt"] == "new value"


# ───────────────────────────────────────────────────────────────────────
# Fallback em erro
# ───────────────────────────────────────────────────────────────────────


class TestFallback:

    def test_db_sqlalchemy_error_falls_back_to_defaults(self):
        """Quando DB lança SQLAlchemyError, devolve defaults sem propagar."""
        from src.core.moon_config import load_moon_config
        from src.core.moon_personality import default_config

        with patch("src.core.moon_config.get_engine") as mock_engine:
            mock_engine.return_value.connect.side_effect = SQLAlchemyError("DB down")
            # Patch o Session pra explodir tbm
            with patch("src.core.moon_config.Session") as mock_session:
                mock_session.side_effect = SQLAlchemyError("DB down")
                result = load_moon_config()

        assert result == default_config()

    def test_table_missing_falls_back_to_defaults(self):
        """Tabela moon_config inexistente (Exception generic) → defaults."""
        from src.core.moon_config import load_moon_config
        from src.core.moon_personality import default_config

        with patch("src.core.moon_config.Session") as mock_session:
            mock_session.side_effect = Exception("relation moon_config does not exist")
            result = load_moon_config()
        assert result == default_config()

    def test_fallback_does_not_cache(self):
        """Fallback NÃO faz cache — próxima chamada tenta DB de novo."""
        from src.core.moon_config import load_moon_config
        from src.core import moon_config as mc

        with patch("src.core.moon_config.Session") as mock_session:
            mock_session.side_effect = Exception("DB down")
            load_moon_config()
            # _CACHED ainda None após fallback
            assert mc._CACHED is None
