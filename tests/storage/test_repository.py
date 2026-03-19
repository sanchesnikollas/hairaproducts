# tests/storage/test_repository.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.orm_models import Base, IngredientORM, ProductIngredientORM, ValidationComparisonORM, ReviewQueueORM
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


class TestUpdateProductLabels:
    def test_update_product_labels(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        product_id = repo.upsert_product(extraction, qa)
        db_session.flush()

        labels = {
            "detected": ["sulfate_free", "vegan"],
            "inferred": ["silicone_free"],
            "confidence": 0.9,
            "sources": ["official_text", "inci_analysis"],
            "manually_verified": False,
            "manually_overridden": False,
        }
        repo.update_product_labels(product_id, labels)
        db_session.flush()

        fetched = repo.get_product_by_id(product_id)
        assert fetched.product_labels is not None
        assert "sulfate_free" in fetched.product_labels["detected"]
        assert fetched.product_labels["confidence"] == 0.9

    def test_update_nonexistent_product(self, repo):
        """Calling with invalid ID should not raise."""
        repo.update_product_labels("nonexistent-id", {"detected": []})


class TestTaxonomyFieldsInUpsert:
    def test_composition_and_care_usage_persisted_on_insert(self, repo, db_session):
        extraction = _make_extraction(
            composition="Contains Keratin and Argan Oil",
            care_usage="Apply to wet hair, massage, rinse after 3 minutes",
        )
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        product_id = repo.upsert_product(extraction, qa)
        db_session.flush()
        product = repo.get_product_by_id(product_id)
        assert product.composition == "Contains Keratin and Argan Oil"
        assert product.care_usage == "Apply to wet hair, massage, rinse after 3 minutes"

    def test_composition_and_care_usage_persisted_on_update(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        repo.upsert_product(extraction, qa)
        db_session.commit()

        updated = _make_extraction(
            composition="New composition text",
            care_usage="New care usage text",
        )
        repo.upsert_product(updated, qa)
        db_session.commit()

        products = repo.get_products(brand_slug="amend")
        assert products[0].composition == "New composition text"
        assert products[0].care_usage == "New care usage text"

    def test_evidence_source_section_label_persisted(self, repo, db_session):
        ev = Evidence(
            field_name="composition",
            source_url="https://www.amend.com.br/shampoo-gold-black",
            evidence_locator="h2:Composição",
            raw_source_text="Contains Keratin and Argan Oil",
            extraction_method=ExtractionMethod.HTML_SELECTOR,
            source_section_label="Composição",
        )
        extraction = _make_extraction(evidence=[ev])
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        product_id = repo.upsert_product(extraction, qa)
        db_session.flush()

        from src.storage.orm_models import ProductEvidenceORM
        evidence_rows = db_session.query(ProductEvidenceORM).filter_by(product_id=product_id).all()
        assert len(evidence_rows) == 1
        assert evidence_rows[0].source_section_label == "Composição"


class TestGetProductIngredients:
    def test_get_product_ingredients_ordered_by_position(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        product_id = repo.upsert_product(extraction, qa)
        db_session.flush()

        ing1 = IngredientORM(canonical_name="Aqua")
        ing2 = IngredientORM(canonical_name="Glycerin")
        db_session.add_all([ing1, ing2])
        db_session.flush()

        pi1 = ProductIngredientORM(product_id=product_id, ingredient_id=ing1.id, position=2, raw_name="Water")
        pi2 = ProductIngredientORM(product_id=product_id, ingredient_id=ing2.id, position=1, raw_name="Glycerin")
        db_session.add_all([pi1, pi2])
        db_session.commit()

        results = repo.get_product_ingredients(product_id)
        assert len(results) == 2
        assert results[0].position == 1
        assert results[1].position == 2

    def test_get_product_ingredients_empty(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=[])
        product_id = repo.upsert_product(extraction, qa)
        db_session.commit()

        results = repo.get_product_ingredients(product_id)
        assert results == []


class TestSearchIngredients:
    def test_search_by_partial_name(self, repo, db_session):
        ing1 = IngredientORM(canonical_name="Sodium Laureth Sulfate")
        ing2 = IngredientORM(canonical_name="Aqua")
        db_session.add_all([ing1, ing2])
        db_session.commit()

        results = repo.search_ingredients("sodium")
        assert len(results) == 1
        assert results[0].canonical_name == "Sodium Laureth Sulfate"

    def test_search_case_insensitive(self, repo, db_session):
        ing = IngredientORM(canonical_name="Panthenol")
        db_session.add(ing)
        db_session.commit()

        results = repo.search_ingredients("PANTHENOL")
        assert len(results) == 1

    def test_search_no_match_returns_empty(self, repo, db_session):
        ing = IngredientORM(canonical_name="Aqua")
        db_session.add(ing)
        db_session.commit()

        results = repo.search_ingredients("nonexistent")
        assert results == []


class TestGetReviewQueue:
    def _make_product_and_comparison(self, repo, db_session, brand_slug="amend", field="inci_ingredients"):
        extraction = _make_extraction(
            brand_slug=brand_slug,
            product_url=f"https://www.{brand_slug}.com.br/product-{field}",
        )
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=[])
        product_id = repo.upsert_product(extraction, qa)
        db_session.flush()

        vc = ValidationComparisonORM(
            product_id=product_id, field_name=field,
            pass_1_value="val1", pass_2_value="val2", resolution="conflict",
        )
        db_session.add(vc)
        db_session.flush()

        rq = ReviewQueueORM(
            product_id=product_id, comparison_id=vc.id,
            field_name=field, status="pending",
        )
        db_session.add(rq)
        db_session.commit()
        return product_id, vc.id, rq.id

    def test_get_all_queue_items(self, repo, db_session):
        self._make_product_and_comparison(repo, db_session)
        results = repo.get_review_queue()
        assert len(results) == 1

    def test_filter_by_status(self, repo, db_session):
        self._make_product_and_comparison(repo, db_session)
        pending = repo.get_review_queue(status="pending")
        assert len(pending) == 1

        resolved = repo.get_review_queue(status="resolved")
        assert len(resolved) == 0

    def test_filter_by_brand_slug(self, repo, db_session):
        self._make_product_and_comparison(repo, db_session, brand_slug="amend")
        self._make_product_and_comparison(repo, db_session, brand_slug="wella", field="description")

        amend_results = repo.get_review_queue(brand_slug="amend")
        assert len(amend_results) == 1
        assert amend_results[0].field_name == "inci_ingredients"


class TestResolveReviewQueueItem:
    def test_resolve_pending_item(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=[])
        product_id = repo.upsert_product(extraction, qa)
        db_session.flush()

        vc = ValidationComparisonORM(
            product_id=product_id, field_name="description",
            pass_1_value="a", pass_2_value="b", resolution="conflict",
        )
        db_session.add(vc)
        db_session.flush()

        rq = ReviewQueueORM(
            product_id=product_id, comparison_id=vc.id,
            field_name="description", status="pending",
        )
        db_session.add(rq)
        db_session.commit()

        resolved = repo.resolve_review_queue_item(rq.id, status="approved", notes="looks good")
        assert resolved is not None
        assert resolved.status == "approved"
        assert resolved.reviewer_notes == "looks good"
        assert resolved.resolved_at is not None

    def test_resolve_nonexistent_item_returns_none(self, repo):
        result = repo.resolve_review_queue_item("nonexistent-id", status="approved")
        assert result is None


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
