# tests/extraction/test_deterministic.py
import pytest
from pathlib import Path
from src.extraction.deterministic import (
    extract_jsonld, extract_by_selectors, extract_product_deterministic,
    _extract_inci_by_tab_labels, _get_soup,
)


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


class TestInciTabLabels:
    """Tests for _extract_inci_by_tab_labels with various real-world DOM patterns."""

    def test_kerastase_style_heading_with_sibling_p(self):
        """Kérastase: h3 heading followed by <p> with bullet-separated INCI."""
        html = """
        <div class="product-detail">
          <div class="key-ingredients">
            <h3>Key Ingredients</h3>
            <p>ÁCIDO LÁTICO: Ingrediente ativo que ajuda a fortalecer os cabelos.</p>
            <p>CENTELHA ASIÁTICA: Ingrediente natural para hidratação.</p>
          </div>
          <div class="full-ingredients">
            <h3>Lista Completa De Ingredientes</h3>
            <p>AQUA / WATER / EAU • SODIUM C14-16 OLEFIN SULFONATE • COCAMIDOPROPYL BETAINE • SODIUM CHLORIDE • GLYCERIN • PARFUM</p>
          </div>
        </div>
        """
        soup = _get_soup(html)
        content, selector = _extract_inci_by_tab_labels(soup)
        assert content is not None
        assert "AQUA / WATER / EAU" in content
        assert "SODIUM C14-16" in content
        # Must NOT contain marketing text
        assert "ÁCIDO LÁTICO" not in content
        assert "fortalecer" not in content

    def test_kerastase_style_wrapper_div_with_heading_and_p(self):
        """Kérastase: wrapper div contains both heading and INCI <p>."""
        html = """
        <div class="pdp-section">
          <div class="ingredients-section">
            <span>Ingredientes</span>
            <div class="marketing">
              <p>ÁCIDO LÁTICO: Ingrediente ativo, ajuda a fortalecer os cabelos.</p>
            </div>
          </div>
          <div class="full-inci-section">
            <h3>Lista completa de ingredientes</h3>
            <div class="inci-content">
              <p>AQUA / WATER / EAU • SODIUM LAURETH SULFATE • COCAMIDOPROPYL BETAINE • GLYCOL DISTEARATE</p>
            </div>
          </div>
        </div>
        """
        soup = _get_soup(html)
        content, selector = _extract_inci_by_tab_labels(soup)
        assert content is not None
        assert "AQUA / WATER / EAU" in content
        assert "ÁCIDO LÁTICO" not in content

    def test_priority_prefers_specific_label(self):
        """More specific labels win even if generic match appears first in DOM."""
        html = """
        <div>
          <button>Ingredientes</button>
          <div>ÁCIDO LÁTICO: fortalecer, CENTELHA ASIÁTICA: hidratar, VITAMINA E: proteger</div>
          <button>Lista completa de ingredientes</button>
          <div>AQUA, SODIUM LAURETH SULFATE, COCAMIDOPROPYL BETAINE, GLYCERIN, PARFUM, CITRIC ACID</div>
        </div>
        """
        soup = _get_soup(html)
        content, selector = _extract_inci_by_tab_labels(soup)
        assert content is not None
        assert "AQUA" in content
        assert "SODIUM LAURETH SULFATE" in content

    def test_heading_find_next_p(self):
        """h3 heading where INCI <p> is nested deeper (not direct sibling)."""
        html = """
        <section>
          <h3>Composição</h3>
          <div class="inner">
            <p>Aqua, Cetearyl Alcohol, Glycerin, Behentrimonium Chloride, Parfum, Citric Acid</p>
          </div>
        </section>
        """
        soup = _get_soup(html)
        content, selector = _extract_inci_by_tab_labels(soup)
        assert content is not None
        assert "Aqua" in content
        assert "Cetearyl Alcohol" in content

    def test_collapse_content_strategy(self):
        """Amend-style: .collapse__content next to button with label."""
        html = """
        <div>
          <button class="collapse__button">Composição</button>
          <div class="collapse__content">
            Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum
          </div>
        </div>
        """
        soup = _get_soup(html)
        content, selector = _extract_inci_by_tab_labels(soup)
        assert content is not None
        assert "Aqua" in content

    def test_og_image_fallback(self):
        """Products with og:image but no JSON-LD image get the og:image."""
        html = """
        <html>
        <head>
          <meta property="og:image" content="https://cdn.example.com/product.jpg" />
          <script type="application/ld+json">
          {"@context": "https://schema.org", "@type": "Product", "name": "Test Product"}
          </script>
        </head>
        <body><h1>Test Product</h1></body>
        </html>
        """
        result = extract_product_deterministic(html, "https://example.com/p/test")
        assert result["image_url_main"] == "https://cdn.example.com/product.jpg"
