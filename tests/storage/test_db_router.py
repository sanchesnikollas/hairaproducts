# tests/storage/test_db_router.py
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_models import CentralBase, BrandDatabaseORM
from src.storage.db_router import DatabaseRouter, BrandDatabaseUnavailable


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def central_engine():
    """In-memory SQLite engine for the central registry."""
    engine = create_engine("sqlite:///:memory:")
    CentralBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def populated_router(central_engine):
    """DatabaseRouter with two brands: one active, one inactive."""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=central_engine)
    with SessionLocal() as session:
        session.add(
            BrandDatabaseORM(
                brand_slug="active-brand",
                brand_name="Active Brand",
                database_url="sqlite:///:memory:",
                is_active=True,
            )
        )
        session.add(
            BrandDatabaseORM(
                brand_slug="inactive-brand",
                brand_name="Inactive Brand",
                database_url="sqlite:///:memory:",
                is_active=False,
            )
        )
        session.commit()

    router = DatabaseRouter(central_engine)
    yield router
    router.close_all()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSession:
    def test_returns_valid_session_for_active_brand(self, populated_router):
        session = populated_router.get_session("active-brand")
        assert isinstance(session, Session)
        session.close()

    def test_raises_for_unknown_brand(self, populated_router):
        with pytest.raises(BrandDatabaseUnavailable, match="not registered"):
            populated_router.get_session("nonexistent-brand")

    def test_raises_for_inactive_brand(self, populated_router):
        with pytest.raises(BrandDatabaseUnavailable, match="not active"):
            populated_router.get_session("inactive-brand")


class TestListBrands:
    def test_returns_only_active_brands(self, populated_router):
        brands = populated_router.list_brands()
        assert len(brands) == 1
        assert brands[0].brand_slug == "active-brand"

    def test_returns_empty_when_no_active_brands(self, central_engine):
        from sqlalchemy.orm import sessionmaker

        SessionLocal = sessionmaker(bind=central_engine)
        with SessionLocal() as session:
            session.add(
                BrandDatabaseORM(
                    brand_slug="only-inactive",
                    brand_name="Only Inactive",
                    database_url="sqlite:///:memory:",
                    is_active=False,
                )
            )
            session.commit()

        router = DatabaseRouter(central_engine)
        try:
            assert router.list_brands() == []
        finally:
            router.close_all()


class TestEngineCaching:
    def test_same_engine_reused_for_same_brand(self, populated_router):
        # Access twice; the cached engine should be the same object.
        populated_router.get_session("active-brand").close()
        populated_router.get_session("active-brand").close()

        assert len(populated_router._engines) == 1
        engine1 = populated_router._engines["active-brand"]

        # Third call should not add a new entry.
        populated_router.get_session("active-brand").close()
        engine2 = populated_router._engines["active-brand"]

        assert engine1 is engine2


class TestGetCentralSession:
    def test_central_session_is_usable(self, populated_router):
        session = populated_router.get_central_session()
        assert isinstance(session, Session)
        # Verify we can actually query through it.
        count = session.query(BrandDatabaseORM).count()
        assert count == 2  # one active + one inactive
        session.close()


class TestCloseAll:
    def test_close_all_clears_cache(self, populated_router):
        populated_router.get_session("active-brand").close()
        assert len(populated_router._engines) == 1

        populated_router.close_all()
        assert len(populated_router._engines) == 0
