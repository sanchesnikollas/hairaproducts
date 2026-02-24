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
