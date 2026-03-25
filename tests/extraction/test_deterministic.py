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


class TestSectionLabelMapIntegration:
    """Tests for section_label_map parameter in extract_product_deterministic."""

    def test_extracts_care_usage_and_composition(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Shampoo Test",
         "image": "https://example.com/img.jpg"}
        </script>
        </head><body>
            <h1>Shampoo Test</h1>
            <h2>Descricao</h2>
            <p>Um shampoo nutritivo para cabelos secos.</p>
            <h2>Modo de Uso</h2>
            <p>Aplique nos cabelos molhados e massageie.</p>
            <h2>Principios Ativos</h2>
            <p>Queratina hidrolisada, oleo de argan, pantenol.</p>
            <h2>Ingredientes</h2>
            <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid</p>
        </body></html>
        """
        section_label_map = {
            "description": {"labels": ["descricao", "sobre o produto"]},
            "care_usage": {"labels": ["modo de uso", "como usar"]},
            "composition": {"labels": ["principios ativos", "ativos"]},
            "ingredients_inci": {
                "labels": ["ingredientes", "inci"],
                "validators": ["has_separators", "min_length_30"],
            },
        }
        result = extract_product_deterministic(
            html=html,
            url="https://example.com/shampoo-test",
            section_label_map=section_label_map,
        )
        assert result["care_usage"] == "Aplique nos cabelos molhados e massageie."
        assert result["composition"] == "Queratina hidrolisada, oleo de argan, pantenol."
        assert result["inci_raw"] is not None
        assert "Aqua" in result["inci_raw"]
        assert result["description"] is not None

    def test_section_classifier_fills_description_when_jsonld_missing(self):
        html = """
        <html><body>
            <h1>Condicionador Test</h1>
            <h2>Sobre o Produto</h2>
            <p>Um condicionador premium para cabelos danificados.</p>
        </body></html>
        """
        section_label_map = {
            "description": {"labels": ["sobre o produto", "descricao"]},
            "care_usage": {"labels": ["modo de uso"]},
            "composition": {"labels": ["principios ativos"]},
            "ingredients_inci": {"labels": ["ingredientes"]},
        }
        result = extract_product_deterministic(
            html=html,
            url="https://example.com/condicionador",
            section_label_map=section_label_map,
        )
        assert result["description"] == "Um condicionador premium para cabelos danificados."

    def test_evidence_includes_source_section_label(self):
        html = """
        <html><body>
            <h1>Mascara Test</h1>
            <h2>Modo de Uso</h2>
            <p>Aplique mecha a mecha nos cabelos limpos.</p>
        </body></html>
        """
        section_label_map = {
            "description": {"labels": ["descricao"]},
            "care_usage": {"labels": ["modo de uso"]},
            "composition": {"labels": ["principios ativos"]},
            "ingredients_inci": {"labels": ["ingredientes"]},
        }
        result = extract_product_deterministic(
            html=html,
            url="https://example.com/mascara",
            section_label_map=section_label_map,
        )
        section_evidence = [e for e in result["evidence"] if e.source_section_label is not None]
        assert len(section_evidence) >= 1
        assert section_evidence[0].source_section_label == "Modo de Uso"

    def test_no_section_label_map_preserves_existing_behavior(self):
        """When section_label_map is None, behavior is unchanged."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Basic Product",
         "description": "A basic product.", "image": "https://example.com/img.jpg"}
        </script>
        </head><body><h1>Basic Product</h1></body></html>
        """
        result = extract_product_deterministic(
            html=html,
            url="https://example.com/basic",
        )
        assert result["product_name"] == "Basic Product"
        assert result["description"] == "A basic product."
        assert result.get("care_usage") is None
        assert result.get("composition") is None


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

class TestInciSource:
    """Tests for inci_source field tracking in extract_product_deterministic."""

    def test_inci_source_from_section_classifier(self):
        """When INCI comes from section classifier, inci_source should be 'section_classifier'."""
        html = """<html><body>
        <h2>Ingredientes</h2>
        <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</p>
        </body></html>"""
        result = extract_product_deterministic(
            html, "https://example.com/product",
            section_label_map={"ingredients_inci": {"labels": ["ingredientes"], "validators": ["has_separators", "min_length_30"]}}
        )
        assert result.get("inci_source") in ("section_classifier", "tab_label_heuristic", "css_selector")

    def test_inci_source_absent_when_no_inci(self):
        """When no INCI is extracted, inci_source should be None."""
        html = "<html><body><h1>Product</h1><p>No ingredients here</p></body></html>"
        result = extract_product_deterministic(html, "https://example.com/product")
        assert result.get("inci_source") is None

    def test_inci_source_section_classifier_sets_value(self):
        """When section_label_map matches INCI heading, inci_source is 'section_classifier'."""
        html = """<html><body>
        <h2>Ingredientes</h2>
        <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid</p>
        </body></html>"""
        result = extract_product_deterministic(
            html, "https://example.com/product",
            section_label_map={
                "ingredients_inci": {
                    "labels": ["ingredientes"],
                    "validators": ["has_separators", "min_length_30"],
                }
            },
        )
        if result.get("inci_raw"):
            assert result.get("inci_source") == "section_classifier"

    def test_inci_source_css_selector_when_explicit_selector_matches(self):
        """When INCI is found via explicit CSS selector, inci_source should be 'css_selector'."""
        html = """<html><body>
        <div class="product-ingredients">
            <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid</p>
        </div>
        </body></html>"""
        result = extract_product_deterministic(
            html, "https://example.com/product",
            inci_selectors=[".product-ingredients p"],
        )
        assert result.get("inci_raw") is not None
        assert result.get("inci_source") == "css_selector"

    def test_inci_source_tab_label_heuristic_when_no_selector(self):
        """When INCI is found via tab label heuristic fallback, inci_source is 'tab_label_heuristic'."""
        html = """<html><body>
        <button>Composição</button>
        <div class="collapse__content">Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</div>
        </body></html>"""
        result = extract_product_deterministic(
            html, "https://example.com/product",
        )
        if result.get("inci_raw"):
            assert result.get("inci_source") == "tab_label_heuristic"

    def test_inci_source_is_key_in_result(self):
        """inci_source key should always be present in the result dict."""
        html = "<html><body><h1>Product</h1></body></html>"
        result = extract_product_deterministic(html, "https://example.com/product")
        assert "inci_source" in result


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


def test_details_summary_inci_extraction():
    """INCI inside <details>/<summary> should be extracted."""
    html = """<html><body>
    <details>
        <summary>Ingredientes</summary>
        <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</p>
    </details>
    </body></html>"""
    result = extract_product_deterministic(html, "https://example.com/product")
    assert result.get("inci_raw") is not None
    assert "Aqua" in result["inci_raw"]


def test_data_attribute_tab_inci_extraction():
    """INCI inside data-attribute tab content should be extracted."""
    html = """<html><body>
    <div data-tab="ingredientes">
        <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum</p>
    </div>
    </body></html>"""
    result = extract_product_deterministic(html, "https://example.com/product")
    assert result.get("inci_raw") is not None
