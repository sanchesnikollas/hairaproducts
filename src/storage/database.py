# src/storage/database.py
from __future__ import annotations

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_core_engine: Engine | None = None


def _build_engine(url: str) -> Engine:
    # Railway/Heroku use postgres:// but SQLAlchemy needs postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    kwargs: dict = {"echo": os.environ.get("SQL_ECHO", "").lower() == "true"}
    if url.startswith("postgresql"):
        kwargs["pool_size"] = 5
        kwargs["pool_pre_ping"] = True
    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    """Engine padrão (DATABASE_URL) — catálogo/produtos e tudo que não é `users`.

    NÃO use isto para criar/resetar usuários: em produção split o login lê do
    banco CORE, não do DATABASE_URL. Use ``get_core_engine()`` nesses casos.
    """
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "sqlite:///haira.db")
        _engine = _build_engine(url)
    return _engine


def resolve_core_url() -> str:
    """URL do banco de *users/core*, na MESMA ordem em que a API resolve em
    ``dependencies.get_core_session()``: CORE_DATABASE_URL → CENTRAL_DATABASE_URL
    → DATABASE_URL.

    Scripts standalone (seeds, CLI) NÃO passam pelo startup do FastAPI
    (``main._init_databases``), então não enxergam o ``_core_engine`` setado lá.
    Sem isto eles caem só no DATABASE_URL e criam/resetam usuários no banco
    errado quando o split está ativo — o usuário "existe" mas o login (que lê o
    CORE) devolve 401. Ver docs/handoff-andre.md §5/§10.
    """
    for var in ("CORE_DATABASE_URL", "CENTRAL_DATABASE_URL", "DATABASE_URL"):
        url = os.environ.get(var, "").strip()
        if url:
            return url
    return "sqlite:///haira.db"


def get_core_engine() -> Engine:
    """Engine para a tabela ``users`` (login/auth), espelhando a cadeia de
    fallback da API (``get_core_session``). Use isto — não ``get_engine()`` — em
    qualquer script/CLI que cria, promove ou reseta usuários, para que escreva
    no mesmo banco de onde o login lê.
    """
    global _core_engine
    if _core_engine is None:
        _core_engine = _build_engine(resolve_core_url())
    return _core_engine


def get_session() -> Session:
    factory = sessionmaker(bind=get_engine())
    return factory()


def reset_engine() -> None:
    global _engine, _core_engine
    _engine = None
    _core_engine = None
