# tests/core/test_models.py
import pytest
from datetime import datetime, timezone
from src.core.models import (
    Brand,
    DiscoveredURL,
    ProductExtraction,
    Evidence,
    QAResult,
    VerificationStatus,
    GenderTarget,
    ExtractionMethod,
    QAStatus,
)


class TestBrand:
    def test_create_brand(self):
        brand = Brand(
            brand_name="Amend Cosméticos",
            brand_slug="amend-cosmeticos",
            official_url_root="https://www.amend.com.br",
        )
        assert brand.brand_slug == "amend-cosmeticos"
        assert brand.status == "active"
        assert brand.catalog_entrypoints == []

    def test_brand_defaults(self):
        brand = Brand(
            brand_name="Test",
            brand_slug="test",
            official_url_root="https://test.com",
        )
        assert brand.country is None
        assert brand.priority is None
        assert brand.notes is None


class TestDiscoveredURL:
    def test_create(self):
        url = DiscoveredURL(
            url="https://www.amend.com.br/produto/shampoo",
            source_type="category_crawl",
            hair_relevant=True,
            hair_relevance_reason="URL contains 'shampoo'",
        )
        assert url.hair_relevant is True

    def test_kit_detection(self):
        url = DiscoveredURL(
            url="https://example.com/kit-shampoo-condicionador",
            source_type="category_crawl",
            is_kit=True,
        )
        assert url.is_kit is True


class TestEvidence:
    def test_create(self):
        ev = Evidence(
            field_name="inci_ingredients",
            source_url="https://www.amend.com.br/produto/shampoo",
            evidence_locator=".product-ingredients",
            raw_source_text="Aqua, Sodium Laureth Sulfate",
            extraction_method=ExtractionMethod.HTML_SELECTOR,
        )
        assert ev.extraction_method == ExtractionMethod.HTML_SELECTOR


class TestProductExtraction:
    def test_catalog_only(self):
        product = ProductExtraction(
            brand_slug="amend",
            product_name="Shampoo Repair",
            product_url="https://www.amend.com.br/shampoo-repair",
            image_url_main="https://www.amend.com.br/img/shampoo.jpg",
            gender_target=GenderTarget.UNISEX,
            hair_relevance_reason="shampoo in product name",
        )
        assert product.inci_ingredients is None
        assert product.confidence == 0.0

    def test_verified_product(self):
        product = ProductExtraction(
            brand_slug="amend",
            product_name="Shampoo Repair",
            product_url="https://www.amend.com.br/shampoo-repair",
            image_url_main="https://www.amend.com.br/img/shampoo.jpg",
            gender_target=GenderTarget.UNISEX,
            hair_relevance_reason="shampoo in product name",
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
                              "Glycerin", "Parfum"],
            confidence=0.95,
        )
        assert len(product.inci_ingredients) == 5


class TestEvidenceSectionLabel:
    def test_evidence_has_source_section_label(self):
        ev = Evidence(
            field_name="ingredients_inci",
            source_url="https://example.com",
            evidence_locator="h2.section-title",
            raw_source_text="Aqua, Cetearyl Alcohol",
            extraction_method=ExtractionMethod.HTML_SELECTOR,
            source_section_label="Ingredientes",
        )
        assert ev.source_section_label == "Ingredientes"

    def test_evidence_section_label_defaults_none(self):
        ev = Evidence(
            field_name="inci_ingredients",
            source_url="https://example.com",
            evidence_locator=".selector",
            raw_source_text="text",
            extraction_method=ExtractionMethod.HTML_SELECTOR,
        )
        assert ev.source_section_label is None


class TestProductExtractionTaxonomy:
    def test_product_extraction_has_taxonomy_fields(self):
        pe = ProductExtraction(
            brand_slug="test",
            product_name="Test Product",
            product_url="https://example.com/product",
            composition="Contains Keratin and Argan Oil",
            care_usage="Apply to wet hair, massage, rinse after 3 minutes",
        )
        assert pe.composition == "Contains Keratin and Argan Oil"
        assert pe.care_usage == "Apply to wet hair, massage, rinse after 3 minutes"

    def test_taxonomy_fields_default_none(self):
        pe = ProductExtraction(
            brand_slug="test",
            product_name="Test Product",
            product_url="https://example.com/product",
        )
        assert pe.composition is None
        assert pe.care_usage is None


class TestQAResult:
    def test_pass(self):
        result = QAResult(
            status=QAStatus.VERIFIED_INCI,
            passed=True,
            checks_passed=["name_valid", "url_valid", "inci_valid"],
            checks_failed=[],
        )
        assert result.passed is True

    def test_fail(self):
        result = QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=["name_valid"],
            checks_failed=["inci_too_short"],
            rejection_reason="INCI has only 2 terms",
        )
        assert result.passed is False
        assert result.rejection_reason is not None


def test_ingredient_model():
    from src.core.models import Ingredient
    ing = Ingredient(id="abc", canonical_name="Dimethicone", category="silicone")
    assert ing.canonical_name == "Dimethicone"

def test_ingredient_with_aliases():
    from src.core.models import Ingredient
    ing = Ingredient(id="abc", canonical_name="Dimethicone", aliases=["DIMETHICONE", "Dimeticone"])
    assert len(ing.aliases) == 2

def test_claim_model():
    from src.core.models import Claim
    c = Claim(id="abc", canonical_name="sulfate_free", display_name="Sulfate Free", category="seal")
    assert c.display_name == "Sulfate Free"

def test_validation_comparison_model():
    from src.core.models import ValidationComparison
    vc = ValidationComparison(
        id="abc", product_id="xyz", field_name="product_name",
        pass_1_value="Shampoo X", pass_2_value="Shampoo X", resolution="auto_matched"
    )
    assert vc.resolution == "auto_matched"

def test_review_queue_item_model():
    from src.core.models import ReviewQueueItem
    rq = ReviewQueueItem(
        id="abc", product_id="xyz", field_name="inci_ingredients",
        status="pending",
    )
    assert rq.status == "pending"
