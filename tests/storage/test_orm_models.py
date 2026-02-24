# tests/storage/test_orm_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.orm_models import Base, ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM
from src.storage.database import get_engine


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestProductORM:
    def test_create_product(self, db_session):
        product = ProductORM(
            brand_slug="amend",
            product_name="Shampoo Gold Black",
            product_url="https://www.amend.com.br/shampoo-gold-black",
            image_url_main="https://www.amend.com.br/img.jpg",
            verification_status="catalog_only",
            gender_target="unisex",
            hair_relevance_reason="shampoo in name",
            confidence=0.0,
        )
        db_session.add(product)
        db_session.commit()
        assert product.id is not None

    def test_unique_url_constraint(self, db_session):
        p1 = ProductORM(
            brand_slug="amend", product_name="Shampoo A",
            product_url="https://www.amend.com.br/shampoo",
            verification_status="catalog_only", gender_target="unknown",
            confidence=0.0,
        )
        p2 = ProductORM(
            brand_slug="amend", product_name="Shampoo B",
            product_url="https://www.amend.com.br/shampoo",
            verification_status="catalog_only", gender_target="unknown",
            confidence=0.0,
        )
        db_session.add(p1)
        db_session.commit()
        db_session.add(p2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_product_with_evidence(self, db_session):
        product = ProductORM(
            brand_slug="amend", product_name="Shampoo",
            product_url="https://www.amend.com.br/shampoo",
            verification_status="verified_inci", gender_target="unknown",
            confidence=0.9,
        )
        db_session.add(product)
        db_session.flush()
        evidence = ProductEvidenceORM(
            product_id=product.id,
            field_name="inci_ingredients",
            source_url="https://www.amend.com.br/shampoo",
            evidence_locator=".ingredients",
            raw_source_text="Aqua, Glycerin",
            extraction_method="html_selector",
        )
        db_session.add(evidence)
        db_session.commit()
        assert len(product.evidence) == 1


class TestBrandCoverageORM:
    def test_create(self, db_session):
        cov = BrandCoverageORM(
            brand_slug="amend",
            discovered_total=100,
            hair_total=80,
            kits_total=5,
            non_hair_total=15,
            extracted_total=80,
            verified_inci_total=60,
            verified_inci_rate=0.75,
            catalog_only_total=15,
            quarantined_total=5,
            status="active",
            blueprint_version=1,
        )
        db_session.add(cov)
        db_session.commit()
        assert cov.id is not None
