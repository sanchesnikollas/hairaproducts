# tests/extraction/test_deterministic.py
import pytest
from pathlib import Path
from src.extraction.deterministic import extract_jsonld, extract_by_selectors, extract_product_deterministic


@pytest.fixture
def sample_html():
    return (Path(__file__).parent.parent / "fixtures" / "sample_product_page.html").read_text()


class TestExtractJsonLD:
    def test_extracts_product_name(self, sample_html):
        data = extract_jsonld(sample_html)
        assert data is not None
        assert data["name"] == "Shampoo Gold Black Reparador"

    def test_extracts_price(self, sample_html):
        data = extract_jsonld(sample_html)
        assert data["offers"]["price"] == "29.90"

    def test_returns_none_for_no_jsonld(self):
        data = extract_jsonld("<html><body>No JSON-LD</body></html>")
        assert data is None


class TestExtractBySelectors:
    def test_extracts_ingredients(self, sample_html):
        result = extract_by_selectors(sample_html, inci_selectors=[".product-ingredients p"])
        assert result["inci_raw"] is not None
        assert "Aqua" in result["inci_raw"]

    def test_extracts_name(self, sample_html):
        result = extract_by_selectors(sample_html, name_selectors=[".product-name", "h1"])
        assert result["name"] == "Shampoo Gold Black Reparador"


class TestExtractProductDeterministic:
    def test_full_extraction(self, sample_html):
        result = extract_product_deterministic(
            html=sample_html,
            url="https://www.amend.com.br/shampoo-gold-black",
            inci_selectors=[".product-ingredients p"],
        )
        assert result["product_name"] == "Shampoo Gold Black Reparador"
        assert result["inci_raw"] is not None
        assert "Aqua" in result["inci_raw"]
        assert result["image_url_main"] is not None
        assert len(result["evidence"]) > 0
