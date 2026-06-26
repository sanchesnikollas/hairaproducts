# src/api/dependencies.py
from __future__ import annotations

import logging
from typing import Generator

from fastapi import HTTPException, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.storage.db_router import BrandDatabaseUnavailable, DatabaseRouter

logger = logging.getLogger("haira.api.dependencies")

# ─────────────────────────────────────────────────────────────────────────────
# 3-DB ARQUITETURA (haira_core / haira_catalog / haira_audit)
#
# Cada engine é setado por `main.py:_init_databases()` em startup. Durante a
# transição (Fase A→D), nem todas as envs estão setadas em prod e os engines
# caem em fallback chain pro DATABASE_URL/CENTRAL_DATABASE_URL atuais.
#
# Fallback order (cada session.get_X dependency tenta na ordem):
#   get_core_session()    : CORE_DATABASE_URL    → CENTRAL_DATABASE_URL → DATABASE_URL
#   get_catalog_session() : CATALOG_DATABASE_URL → CENTRAL_DATABASE_URL → DATABASE_URL
#   get_audit_session()   : AUDIT_DATABASE_URL   → CENTRAL_DATABASE_URL → DATABASE_URL
#
# As 3 compartilham o MESMO tail (`_resolve_default_engine`): se a env própria
# da classe não estiver setada, caem no engine central (CENTRAL_DATABASE_URL) e,
# sem ele, no DATABASE_URL. Não há fallback cruzado entre classes — audit NÃO
# cai em CORE, catalog NÃO cai em CORE. Isso garante que em prod single-DB hoje
# as 3 deps caiam no mesmo engine. Cutover acontece quando as envs
# *_DATABASE_URL são setadas individualmente.
# ─────────────────────────────────────────────────────────────────────────────

_router: DatabaseRouter | None = None

# Engines explícitos por sensibilidade (resolved at startup)
_core_engine: Engine | None = None
_catalog_engine: Engine | None = None
_audit_engine: Engine | None = None


def init_router(central_engine: Engine) -> DatabaseRouter:
    """Initialise the global DatabaseRouter (called once at startup)."""
    global _router
    _router = DatabaseRouter(central_engine)
    logger.info("DatabaseRouter initialised with central engine")
    return _router


def set_core_engine(engine: Engine | None) -> None:
    global _core_engine
    _core_engine = engine
    if engine is not None:
        logger.info("Core engine set")


def set_catalog_engine(engine: Engine | None) -> None:
    global _catalog_engine
    _catalog_engine = engine
    if engine is not None:
        logger.info("Catalog engine set")


def set_audit_engine(engine: Engine | None) -> None:
    global _audit_engine
    _audit_engine = engine
    if engine is not None:
        logger.info("Audit engine set")


def get_router() -> DatabaseRouter:
    """Return the global DatabaseRouter instance.

    Raises RuntimeError if ``init_router`` has not been called.
    """
    if _router is None:
        raise RuntimeError(
            "DatabaseRouter not initialised. "
            "Set CENTRAL_DATABASE_URL and restart the server."
        )
    return _router


def is_multi_db() -> bool:
    """Return True when multi-database mode is active."""
    return _router is not None


def is_split_db() -> bool:
    """True quando o split 3-DB tem pelo menos 2 engines distintos.

    Útil pra rotas decidirem se vão escrever audit log em DB separada (split=True)
    ou se vão simplesmente skipar/inlinar (split=False — modo monolítico legado).
    """
    engines = {id(_core_engine), id(_catalog_engine), id(_audit_engine)}
    engines.discard(id(None))
    return len(engines) >= 2


def get_brand_db_from_path(request: Request) -> Generator[Session, None, None]:
    """Yield a brand-specific DB session using the ``slug`` path parameter.

    Falls back to the default single-DB session when multi-DB is not active.
    """
    slug: str = request.path_params.get("slug", "")
    if not slug:
        raise HTTPException(status_code=400, detail="Missing brand slug in path")

    if not is_multi_db():
        # Single-DB fallback
        from src.storage.database import get_engine
        engine = get_engine()
        session = Session(bind=engine)
        try:
            yield session
        finally:
            session.close()
        return

    router = get_router()
    session: Session | None = None
    try:
        session = router.get_session(slug)
        yield session
    except BrandDatabaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    finally:
        if session is not None:
            session.close()


def get_brand_db_from_query(brand: str) -> Generator[Session, None, None]:
    """Yield a brand-specific DB session using a query parameter value."""
    if not brand:
        raise HTTPException(status_code=400, detail="Missing brand query parameter")

    router = get_router()
    session: Session | None = None
    try:
        session = router.get_session(brand)
        yield session
    except BrandDatabaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    finally:
        if session is not None:
            session.close()


def get_central_db() -> Generator[Session, None, None]:
    """Yield a session to the central (registry) database."""
    router = get_router()
    session: Session | None = None
    try:
        session = router.get_central_session()
        yield session
    finally:
        if session is not None:
            session.close()


from src.storage.ops_models import UserORM  # noqa: ensure tables are created


def _resolve_default_engine() -> Engine:
    """Engine fallback: usado por todas as get_X_session quando o engine
    específico de sua classe ainda não foi setado.
    """
    if _router is not None:
        return _router._central_engine
    from src.storage.database import get_engine
    return get_engine()


def get_core_session() -> Generator[Session, None, None]:
    """Session para haira_core: users, hair_profiles, moon_*, knowledge_chunks,
    brand_databases.

    Sensibilidade ALTA — KB encriptada + PII.
    Fallback: CORE_DATABASE_URL → central (CENTRAL_DATABASE_URL) → DATABASE_URL.
    Seeds/CLI devem espelhar esta cadeia via database.resolve_core_url().
    """
    engine = _core_engine if _core_engine is not None else _resolve_default_engine()
    with Session(engine) as session:
        yield session


def get_catalog_session() -> Generator[Session, None, None]:
    """Session para haira_catalog: products, ingredients, brand_registry,
    brand_coverage, claims, review_queue.

    Sensibilidade MÉDIA — dado público em sua maioria. Pool maior porque
    /api/brands lê muito.
    Fallback: CATALOG_DATABASE_URL → central (CENTRAL_DATABASE_URL) → DATABASE_URL.
    """
    engine = _catalog_engine if _catalog_engine is not None else _resolve_default_engine()
    with Session(engine) as session:
        yield session


def get_audit_session() -> Generator[Session, None, None]:
    """Session para haira_audit: revision_history, kb_retrieval_log,
    admin_action_log, auth_event_log.

    Append-only. Sempre persistente. Falha aqui NÃO deve derrubar a request
    principal (callers usam try/except).
    Fallback: AUDIT_DATABASE_URL → central (CENTRAL_DATABASE_URL) → DATABASE_URL.
    (NÃO cai em CORE_DATABASE_URL — sem AUDIT/CENTRAL, audit log vai pro DATABASE_URL.)
    """
    engine = _audit_engine if _audit_engine is not None else _resolve_default_engine()
    with Session(engine) as session:
        yield session


def get_ops_session() -> Generator[Session, None, None]:
    """DEPRECATED: use get_core_session() ou get_catalog_session() explicitamente.

    Mantido durante a transição pra não quebrar rotas existentes. Agora
    aponta pro catalog porque a maioria das rotas OPS lê/escreve ProductORM
    (produtos vivem no CATALOG_DATABASE_URL ou DATABASE_URL via fallback).
    Rotas que precisam de tabelas core (users, revisões) devem usar
    get_core_session() explicitamente.
    """
    yield from get_catalog_session()
