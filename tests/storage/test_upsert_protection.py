from __future__ import annotations
import pytest
from unittest.mock import MagicMock


def test_upsert_preserves_external_inci_when_new_has_none(tmp_path):
    """When existing product has external INCI and new extraction has no INCI,
    the external INCI should be preserved."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.storage.orm_models import Base, ProductORM
    from src.storage.repository import ProductRepository
    from src.core.models import ProductExtraction, QAResult, QAStatus, GenderTarget

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = ProductRepository(session)

        # Create product with external enrichment INCI
        product = ProductORM(
            id="test-123",
            brand_slug="bio-extratus",
            product_name="Shampoo Test",
            product_url="https://example.com/test",
            verification_status="verified_inci",
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate"],
            extraction_method="external_enrichment",
            confidence=0.85,
            gender_target="all",
        )
        session.add(product)
        session.commit()

        # Simulate re-scrape with no INCI
        extraction = ProductExtraction(
            brand_slug="bio-extratus",
            product_name="Shampoo Test Updated",
            product_url="https://example.com/test",
            inci_ingredients=None,
            confidence=0.30,
            extraction_method="jsonld",
        )
        qa = MagicMock()
        qa.status = QAStatus.CATALOG_ONLY

        repo.upsert_product(extraction, qa)
        session.commit()

        refreshed = session.query(ProductORM).filter_by(id="test-123").first()
        # INCI preserved
        assert refreshed.inci_ingredients == ["Aqua", "Sodium Laureth Sulfate"]
        assert refreshed.verification_status == "verified_inci"
        assert refreshed.extraction_method == "external_enrichment"
        assert refreshed.confidence == 0.85
        # Non-INCI fields updated
        assert refreshed.product_name == "Shampoo Test Updated"


def test_upsert_overwrites_inci_when_new_extraction_has_inci(tmp_path):
    """When existing product has external INCI and new extraction also has INCI,
    the new INCI should replace the old one."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.storage.orm_models import Base, ProductORM
    from src.storage.repository import ProductRepository
    from src.core.models import ProductExtraction, QAStatus

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = ProductRepository(session)

        product = ProductORM(
            id="test-456",
            brand_slug="bio-extratus",
            product_name="Condicionador Test",
            product_url="https://example.com/condicionador",
            verification_status="verified_inci",
            inci_ingredients=["Aqua", "Cetyl Alcohol"],
            extraction_method="external_enrichment",
            confidence=0.85,
            gender_target="all",
        )
        session.add(product)
        session.commit()

        extraction = ProductExtraction(
            brand_slug="bio-extratus",
            product_name="Condicionador Test Updated",
            product_url="https://example.com/condicionador",
            inci_ingredients=["Aqua", "Cetyl Alcohol", "Dimethicone"],
            confidence=0.90,
            extraction_method="jsonld",
        )
        qa = MagicMock()
        qa.status = QAStatus.VERIFIED_INCI

        repo.upsert_product(extraction, qa)
        session.commit()

        refreshed = session.query(ProductORM).filter_by(id="test-456").first()
        # New INCI takes over
        assert refreshed.inci_ingredients == ["Aqua", "Cetyl Alcohol", "Dimethicone"]
        assert refreshed.confidence == 0.90
        assert refreshed.extraction_method == "jsonld"


def test_upsert_preserves_any_verified_inci_when_new_has_none(tmp_path):
    """When existing product has verified INCI (from any source) and new extraction
    has no INCI, the existing INCI should be preserved. Never downgrade."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.storage.orm_models import Base, ProductORM
    from src.storage.repository import ProductRepository
    from src.core.models import ProductExtraction, QAStatus

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = ProductRepository(session)

        product = ProductORM(
            id="test-789",
            brand_slug="bio-extratus",
            product_name="Mascara Test",
            product_url="https://example.com/mascara",
            verification_status="verified_inci",
            inci_ingredients=["Aqua", "Glycerin"],
            extraction_method="jsonld",
            confidence=0.90,
            gender_target="all",
        )
        session.add(product)
        session.commit()

        extraction = ProductExtraction(
            brand_slug="bio-extratus",
            product_name="Mascara Test Updated",
            product_url="https://example.com/mascara",
            inci_ingredients=None,
            confidence=0.30,
            extraction_method="jsonld",
        )
        qa = MagicMock()
        qa.status = QAStatus.CATALOG_ONLY

        repo.upsert_product(extraction, qa)
        session.commit()

        refreshed = session.query(ProductORM).filter_by(id="test-789").first()
        # INCI PRESERVED — never downgrade verified_inci to catalog_only
        assert refreshed.inci_ingredients == ["Aqua", "Glycerin"]
        assert refreshed.verification_status == "verified_inci"
        assert refreshed.confidence == 0.90
        # Non-INCI fields still update
        assert refreshed.product_name == "Mascara Test Updated"
