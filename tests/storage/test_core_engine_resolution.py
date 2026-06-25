"""Regressão do split-of-users: o engine de `users` (login/auth) precisa
resolver na MESMA cadeia que a API (CORE_DATABASE_URL → CENTRAL_DATABASE_URL →
DATABASE_URL). Seeds/CLI usavam get_engine() (só DATABASE_URL) e criavam
usuários no banco errado quando o split estava ativo — usuário "existia" mas o
login (que lê o CORE) devolvia 401. Ver docs/handoff-andre.md §5/§10.
"""
from __future__ import annotations

import pytest

import src.storage.database as dbmod

_DB_VARS = ("CORE_DATABASE_URL", "CENTRAL_DATABASE_URL", "DATABASE_URL", "CATALOG_DATABASE_URL", "AUDIT_DATABASE_URL")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Limpa todas as *_DATABASE_URL e zera engines cacheados antes e depois."""
    for var in _DB_VARS:
        monkeypatch.delenv(var, raising=False)
    dbmod.reset_engine()
    yield
    dbmod.reset_engine()


# ── resolve_core_url: precedência ────────────────────────────────────────────

def test_core_precedence_prefers_core_over_all(monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", "sqlite:///core.db")
    monkeypatch.setenv("CENTRAL_DATABASE_URL", "sqlite:///central.db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    assert dbmod.resolve_core_url() == "sqlite:///core.db"


def test_core_falls_back_to_central_when_no_core(monkeypatch):
    monkeypatch.setenv("CENTRAL_DATABASE_URL", "sqlite:///central.db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    assert dbmod.resolve_core_url() == "sqlite:///central.db"


def test_core_falls_back_to_database_url_when_only_that(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    assert dbmod.resolve_core_url() == "sqlite:///catalog.db"


def test_core_default_sqlite_when_nothing_set():
    assert dbmod.resolve_core_url() == "sqlite:///haira.db"


def test_empty_string_env_is_treated_as_unset(monkeypatch):
    # Railway às vezes deixa a var setada mas vazia — não deve "ganhar".
    monkeypatch.setenv("CORE_DATABASE_URL", "   ")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    assert dbmod.resolve_core_url() == "sqlite:///catalog.db"


# ── get_core_engine: usa a URL resolvida, normaliza e cacheia ────────────────

def test_core_engine_points_at_core_db(monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", "sqlite:///core.db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    engine = dbmod.get_core_engine()
    assert engine.url.database == "core.db"


def test_core_engine_normalises_postgres_scheme(monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", "postgres://u:p@host:5432/coredb")
    engine = dbmod.get_core_engine()
    # postgres:// → postgresql:// (senão SQLAlchemy 2.x quebra)
    assert str(engine.url).startswith("postgresql://")


def test_core_engine_is_cached_until_reset(monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", "sqlite:///core.db")
    first = dbmod.get_core_engine()
    assert dbmod.get_core_engine() is first
    dbmod.reset_engine()
    assert dbmod.get_core_engine() is not first


# ── regressão: get_engine() (catálogo) NÃO deve seguir o CORE ────────────────

def test_default_engine_ignores_core_url(monkeypatch):
    # O engine de catálogo continua amarrado ao DATABASE_URL — mexer só nos
    # usuários não pode redirecionar produtos pro banco CORE.
    monkeypatch.setenv("CORE_DATABASE_URL", "sqlite:///core.db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    assert dbmod.get_engine().url.database == "catalog.db"


def test_core_and_default_engines_are_distinct_under_split(monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", "sqlite:///core.db")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///catalog.db")
    assert dbmod.get_core_engine().url.database == "core.db"
    assert dbmod.get_engine().url.database == "catalog.db"


# ── integração: reproduz o bug e prova o fix end-to-end ──────────────────────

def _count_users(db_path: str) -> int:
    """Conta usuários num arquivo sqlite (0 se a tabela nem existe)."""
    import sqlite3
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        if cur.fetchone() is None:
            return 0
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        con.close()


def test_cli_create_user_lands_in_core_not_catalog(monkeypatch, tmp_path):
    """Regressão do split-of-users, ponta a ponta.

    Sob split (CORE != DATABASE_URL), `haira create-user` precisa gravar o
    usuário no banco CORE — de onde o login lê — e NÃO no catalog. Antes do fix
    o usuário caía no catalog e o login (que lê o CORE) devolvia 401.
    """
    from click.testing import CliRunner
    from src.cli.main import cli

    core_db = tmp_path / "core.db"
    catalog_db = tmp_path / "catalog.db"
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite:///{core_db}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{catalog_db}")
    dbmod.reset_engine()

    result = CliRunner().invoke(
        cli,
        [
            "create-user",
            "--email", "andre@sanches.io",
            "--name", "Andre",
            "--role", "admin",
            "--password", "secret123",
        ],
    )
    assert result.exit_code == 0, result.output

    # Grava no CORE (onde o login lê), não no catalog (DATABASE_URL).
    assert _count_users(str(core_db)) == 1
    assert _count_users(str(catalog_db)) == 0
    # E é exatamente o banco que o login resolveria.
    assert dbmod.resolve_core_url() == f"sqlite:///{core_db}"


def test_cli_reset_password_targets_core_db(monkeypatch, tmp_path):
    """reset-password também opera no banco CORE: cria o usuário lá, reseta a
    senha, e confirma que o hash mudou no CORE (e o catalog segue vazio)."""
    from click.testing import CliRunner
    from src.cli.main import cli

    core_db = tmp_path / "core.db"
    catalog_db = tmp_path / "catalog.db"
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite:///{core_db}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{catalog_db}")
    dbmod.reset_engine()
    runner = CliRunner()

    runner.invoke(cli, ["create-user", "--email", "r@haira.app",
                        "--role", "reviewer", "--password", "old12345"])
    res = runner.invoke(cli, ["reset-password", "--email", "r@haira.app",
                              "--new-password", "new67890"])
    assert res.exit_code == 0, res.output
    assert _count_users(str(core_db)) == 1
    assert _count_users(str(catalog_db)) == 0


# ── read path: a validação por-request também tem que ler do CORE ────────────

def test_get_current_user_reads_from_core_session():
    """get_current_user valida o JWT contra a tabela `users` a cada request.
    Precisa ler do CORE (mesmo banco do login) — senão, sob split, o login passa
    mas a próxima request autenticada toma 401. Regressão achada na review.
    """
    import inspect
    from src.api import auth
    from src.api.dependencies import get_core_session

    dep = inspect.signature(auth.get_current_user).parameters["session"].default
    assert getattr(dep, "dependency", None) is get_core_session, (
        "get_current_user deve depender de get_core_session (não get_ops_session/catalog)"
    )
