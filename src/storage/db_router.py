# src/storage/db_router.py
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.storage.central_models import BrandDatabaseORM

if TYPE_CHECKING:
    pass


class BrandDatabaseUnavailable(Exception):
    """Raised when a brand database cannot be resolved (not found or inactive)."""


def _make_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with appropriate pool settings."""
    # Normalise postgres:// → postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    kwargs: dict = {}
    if database_url.startswith("postgresql"):
        kwargs["pool_size"] = 3
        kwargs["max_overflow"] = 2
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 300

    return create_engine(database_url, **kwargs)


class DatabaseRouter:
    """Maps brand_slug → SQLAlchemy Session, with engine caching."""

    def __init__(self, central_engine: Engine) -> None:
        self._central_engine = central_engine
        self._central_session_factory = sessionmaker(bind=central_engine)
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Central DB helpers
    # ------------------------------------------------------------------

    def get_central_session(self) -> Session:
        """Return a session bound to the central (registry) database."""
        return self._central_session_factory()

    def list_brands(self) -> list[BrandDatabaseORM]:
        """Return all active brands registered in the central DB."""
        with self.get_central_session() as session:
            return (
                session.query(BrandDatabaseORM)
                .filter(BrandDatabaseORM.is_active.is_(True))
                .all()
            )

    # ------------------------------------------------------------------
    # Brand DB helpers
    # ------------------------------------------------------------------

    def get_session(self, brand_slug: str) -> Session:
        """Return a session for *brand_slug*'s database.

        Raises
        ------
        BrandDatabaseUnavailable
            If the brand is not registered or ``is_active`` is ``False``.
        """
        engine = self._resolve_engine(brand_slug)
        factory = sessionmaker(bind=engine)
        return factory()

    def _resolve_engine(self, brand_slug: str) -> Engine:
        # Fast path: already cached
        with self._lock:
            if brand_slug in self._engines:
                return self._engines[brand_slug]

        # Slow path: look up in central DB
        with self.get_central_session() as session:
            brand: BrandDatabaseORM | None = (
                session.query(BrandDatabaseORM)
                .filter(BrandDatabaseORM.brand_slug == brand_slug)
                .first()
            )

        if brand is None:
            raise BrandDatabaseUnavailable(
                f"Brand '{brand_slug}' is not registered in the central database."
            )
        if not brand.is_active:
            raise BrandDatabaseUnavailable(
                f"Brand '{brand_slug}' exists but is not active."
            )

        engine = _make_engine(brand.database_url)

        with self._lock:
            # Another thread may have raced us; prefer the cached engine.
            if brand_slug not in self._engines:
                self._engines[brand_slug] = engine
            else:
                engine.dispose()
                engine = self._engines[brand_slug]

        return engine

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_all(self) -> None:
        """Dispose every cached brand engine."""
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
