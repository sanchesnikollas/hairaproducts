# tests/storage/test_repository.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.orm_models import Base
from src.storage.repository import ProductRepository
from src.core.models import ProductExtraction, Evidence, GenderTarget, ExtractionMethod, QAResult, QAStatus


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def repo(db_session):
    return ProductRepository(db_session)


def _make_extraction(**overrides) -> ProductExtraction:
    defaults = dict(
        brand_slug="amend",
        product_name="Shampoo Gold Black",
        product_url="https://www.amend.com.br/shampoo-gold-black",
        image_url_main="https://www.amend.com.br/img.jpg",
        gender_target=GenderTarget.UNISEX,
        hair_relevance_reason="shampoo in name",
        confidence=0.0,
    )
    defaults.update(overrides)
    return ProductExtraction(**defaults)


class TestUpsertProduct:
    def test_insert_new(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        product_id = repo.upsert_product(extraction, qa)
        assert product_id is not None
        db_session.flush()

    def test_upsert_existing(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        id1 = repo.upsert_product(extraction, qa)
        db_session.commit()

        extraction2 = _make_extraction(product_name="Shampoo Gold Black V2")
        id2 = repo.upsert_product(extraction2, qa)
        db_session.commit()
        assert id1 == id2


class TestGetProducts:
    def test_get_verified_only(self, repo, db_session):
        e1 = _make_extraction(
            product_url="https://www.amend.com.br/p1",
            inci_ingredients=["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid", "Panthenol"],
            confidence=0.9,
        )
        qa1 = QAResult(status=QAStatus.VERIFIED_INCI, passed=True, checks_passed=[])
        repo.upsert_product(e1, qa1)

        e2 = _make_extraction(product_url="https://www.amend.com.br/p2")
        qa2 = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=[])
        repo.upsert_product(e2, qa2)
        db_session.commit()

        verified = repo.get_products(verified_only=True)
        assert len(verified) == 1
        assert verified[0].product_name == "Shampoo Gold Black"


class TestBrandStats:
    def test_upsert_coverage(self, repo, db_session):
        stats = {
            "brand_slug": "amend",
            "discovered_total": 100,
            "hair_total": 80,
            "kits_total": 5,
            "non_hair_total": 15,
            "extracted_total": 80,
            "verified_inci_total": 60,
            "verified_inci_rate": 0.75,
            "catalog_only_total": 15,
            "quarantined_total": 5,
            "status": "done",
            "blueprint_version": 1,
        }
        repo.upsert_brand_coverage(stats)
        db_session.commit()

        cov = repo.get_brand_coverage("amend")
        assert cov is not None
        assert cov.verified_inci_rate == 0.75
