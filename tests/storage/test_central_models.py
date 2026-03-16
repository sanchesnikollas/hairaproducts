# tests/storage/test_central_models.py
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_models import CentralBase, BrandDatabaseORM


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    CentralBase.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestBrandDatabaseORM:
    def test_create_and_read_back(self, db_session):
        """Can create a BrandDatabaseORM and read it back."""
        brand = BrandDatabaseORM(
            brand_slug="amend",
            brand_name="Amend",
            database_url="postgresql://user:pass@host/amend_db",
            platform="VTEX",
        )
        db_session.add(brand)
        db_session.commit()

        loaded = db_session.get(BrandDatabaseORM, brand.id)
        assert loaded is not None
        assert loaded.brand_slug == "amend"
        assert loaded.brand_name == "Amend"
        assert loaded.database_url == "postgresql://user:pass@host/amend_db"
        assert loaded.platform == "VTEX"

    def test_defaults(self, db_session):
        """Defaults work: id generated, is_active=True, product_count=0, inci_rate=0.0, timestamps set."""
        brand = BrandDatabaseORM(
            brand_slug="wella",
            brand_name="Wella",
            database_url="postgresql://user:pass@host/wella_db",
        )
        db_session.add(brand)
        db_session.commit()

        loaded = db_session.get(BrandDatabaseORM, brand.id)
        assert loaded.id is not None
        assert len(loaded.id) == 36  # UUID format
        assert loaded.is_active is True
        assert loaded.product_count == 0
        assert loaded.inci_rate == 0.0
        assert loaded.platform is None
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

    def test_brand_slug_unique_constraint(self, db_session):
        """brand_slug unique constraint raises on duplicate."""
        b1 = BrandDatabaseORM(
            brand_slug="loreal",
            brand_name="L'Oreal",
            database_url="postgresql://user:pass@host/loreal_db",
        )
        b2 = BrandDatabaseORM(
            brand_slug="loreal",
            brand_name="L'Oreal Duplicate",
            database_url="postgresql://user:pass@host/loreal_db_2",
        )
        db_session.add(b1)
        db_session.commit()

        db_session.add(b2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_optional_platform_field(self, db_session):
        """platform field is nullable and can be set."""
        brand = BrandDatabaseORM(
            brand_slug="salon-line",
            brand_name="Salon Line",
            database_url="postgresql://user:pass@host/salonline_db",
            platform="Shopify",
        )
        db_session.add(brand)
        db_session.commit()

        loaded = db_session.get(BrandDatabaseORM, brand.id)
        assert loaded.platform == "Shopify"

    def test_is_active_can_be_set_false(self, db_session):
        """is_active can be explicitly set to False."""
        brand = BrandDatabaseORM(
            brand_slug="inactive-brand",
            brand_name="Inactive Brand",
            database_url="postgresql://user:pass@host/inactive_db",
            is_active=False,
        )
        db_session.add(brand)
        db_session.commit()

        loaded = db_session.get(BrandDatabaseORM, brand.id)
        assert loaded.is_active is False

    def test_product_count_and_inci_rate_can_be_updated(self, db_session):
        """product_count and inci_rate can be updated after creation."""
        brand = BrandDatabaseORM(
            brand_slug="kerastase",
            brand_name="Kerastase",
            database_url="postgresql://user:pass@host/kerastase_db",
        )
        db_session.add(brand)
        db_session.commit()

        brand.product_count = 150
        brand.inci_rate = 0.85
        db_session.commit()

        loaded = db_session.get(BrandDatabaseORM, brand.id)
        assert loaded.product_count == 150
        assert loaded.inci_rate == 0.85
