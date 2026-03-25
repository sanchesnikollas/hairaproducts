# tests/core/test_qa_gate.py
import pytest
from src.core.models import ProductExtraction, GenderTarget, QAStatus
from src.core.qa_gate import run_product_qa, QAConfig

VALID_DOMAINS = ["www.amend.com.br"]


def _make_product(**overrides) -> ProductExtraction:
    defaults = dict(
        brand_slug="amend",
        product_name="Shampoo Gold Black",
        product_url="https://www.amend.com.br/shampoo-gold-black",
        image_url_main="https://www.amend.com.br/img/shampoo.jpg",
        gender_target=GenderTarget.UNISEX,
        hair_relevance_reason="shampoo in name",
    )
    defaults.update(overrides)
    return ProductExtraction(**defaults)


class TestCatalogOnlyQA:
    def test_valid_catalog_only(self):
        product = _make_product()
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.CATALOG_ONLY
        assert result.passed is True

    def test_garbage_name_fails(self):
        product = _make_product(product_name="404")
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_not_found_name_fails(self):
        product = _make_product(product_name="Página não encontrada")
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_no_image_fails(self):
        product = _make_product(image_url_main=None)
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_unofficial_domain_fails(self):
        product = _make_product(
            product_url="https://www.incidecoder.com/products/amend-shampoo"
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_no_hair_relevance_fails(self):
        product = _make_product(hair_relevance_reason="")
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False


class TestCompositionCrossContamination:
    def test_composition_with_inci_content_adds_soft_check(self):
        """If composition looks like INCI, a soft warning check should be recorded."""
        product = _make_product(
            composition="Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid",
        )
        result = run_product_qa(product, VALID_DOMAINS)
        # Should still pass (soft check), but check should be recorded
        assert result.passed is True
        assert "composition_looks_like_inci" in result.checks_passed or "composition_looks_like_inci" in result.checks_failed

    def test_composition_without_inci_content_no_warning(self):
        """Normal composition text should not trigger the check."""
        product = _make_product(
            composition="Queratina hidrolisada e oleo de argan",
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is True
        assert "composition_looks_like_inci" not in result.checks_passed
        assert "composition_looks_like_inci" not in result.checks_failed


class TestVerifiedInciQA:
    def test_valid_verified(self):
        product = _make_product(
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
                              "Glycerin", "Parfum", "Citric Acid"],
            product_type_normalized="shampoo",
            confidence=0.90,
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.VERIFIED_INCI
        assert result.passed is True

    def test_low_confidence_quarantined(self):
        product = _make_product(
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
                              "Glycerin", "Parfum"],
            product_type_normalized="shampoo",
            confidence=0.50,
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.QUARANTINED

    def test_too_few_inci_quarantined(self):
        product = _make_product(
            inci_ingredients=["Aqua", "Glycerin"],
            product_type_normalized="shampoo",
            confidence=0.90,
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.QUARANTINED


class TestSectionContext:
    def test_3_ingredient_product_passes_with_section_context(self):
        """Product with 3 INCI ingredients should pass QA when has_section_context=True."""
        product = ProductExtraction(
            brand_slug="test",
            product_name="Test Shampoo",
            product_url="https://www.amend.com.br/test",
            image_url_main="https://www.amend.com.br/img/test.jpg",
            hair_relevance_reason="shampoo in name",
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Glycerin"],
            confidence=0.90,
            extraction_method="deterministic",
        )
        result = run_product_qa(
            product,
            allowed_domains=VALID_DOMAINS,
            has_section_context=True,
        )
        assert result.status.value == "verified_inci"

    def test_3_ingredient_product_fails_without_section_context(self):
        """Product with 3 INCI ingredients should fail QA without section context."""
        product = ProductExtraction(
            brand_slug="test",
            product_name="Test Shampoo",
            product_url="https://www.amend.com.br/test",
            image_url_main="https://www.amend.com.br/img/test.jpg",
            hair_relevance_reason="shampoo in name",
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Glycerin"],
            confidence=0.90,
            extraction_method="deterministic",
        )
        result = run_product_qa(
            product,
            allowed_domains=VALID_DOMAINS,
            has_section_context=False,
        )
        assert result.status.value == "quarantined"
