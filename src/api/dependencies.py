# src/api/dependencies.py
from __future__ import annotations

import logging
from typing import Generator

from fastapi import HTTPException, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.storage.db_router import BrandDatabaseUnavailable, DatabaseRouter

logger = logging.getLogger("haira.api.dependencies")

_router: DatabaseRouter | None = None


def init_router(central_engine: Engine) -> DatabaseRouter:
    """Initialise the global DatabaseRouter (called once at startup)."""
    global _router
    _router = DatabaseRouter(central_engine)
    logger.info("DatabaseRouter initialised with central engine")
    return _router


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


def get_ops_session() -> Generator[Session, None, None]:
    """Session for ops tables (users, revision_history). Uses primary DB (not brand-specific).
    In multi-DB mode: uses central DB. In single-DB mode: uses the default engine."""
    if is_multi_db():
        engine = _router._central_engine
    else:
        from src.storage.database import get_engine
        engine = get_engine()
    with Session(engine) as session:
        yield session
