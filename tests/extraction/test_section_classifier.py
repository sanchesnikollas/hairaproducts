# tests/extraction/test_section_classifier.py
import pytest

from src.extraction.section_classifier import (
    PageSection,
    SectionExtractionResult,
    validate_inci_content,
    extract_sections_from_html,
)


SECTION_LABEL_MAP = {
    "description": {
        "labels": ["descricao", "sobre o produto", "detalhes do produto"],
    },
    "care_usage": {
        "labels": ["modo de uso", "como usar", "instrucoes de uso"],
    },
    "composition": {
        "labels": ["principios ativos", "ativos", "formula"],
    },
    "ingredients_inci": {
        "labels": ["ingredientes", "ingredients", "inci", "composicao completa"],
        "validators": ["has_separators", "min_length_30", "no_marketing_verbs"],
    },
}


class TestValidateInciContent:
    def test_valid_inci_list(self):
        text = "Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum"
        assert validate_inci_content(text) is True

    def test_too_short(self):
        assert validate_inci_content("Aqua, Glycerin") is False

    def test_no_separators(self):
        text = "This is a long marketing text about how great this product is for your hair"
        assert validate_inci_content(text) is False

    def test_marketing_text_rejected(self):
        text = "Descubra a nova fórmula, desenvolvida para transformar seus cabelos, com tecnologia avançada"
        assert validate_inci_content(text) is False

    def test_usage_verbs_rejected(self):
        text = "Aplique nos cabelos molhados, massageie suavemente, enxágue após 3 minutos de uso"
        assert validate_inci_content(text) is False

    def test_empty_or_none(self):
        assert validate_inci_content("") is False
        assert validate_inci_content(None) is False


class TestExtractSectionsFromHtml:
    def test_description_section(self):
        html = """
        <html><body>
            <h2>Descricao</h2>
            <p>Um shampoo nutritivo para cabelos secos e danificados.</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.description == "Um shampoo nutritivo para cabelos secos e danificados."

    def test_care_usage_section(self):
        html = """
        <html><body>
            <h2>Modo de Uso</h2>
            <p>Aplique nos cabelos molhados, massageie e enxague.</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.care_usage == "Aplique nos cabelos molhados, massageie e enxague."

    def test_label_tab_nav_rejects_short_neighbor_label(self):
        """Apice Cosmeticos pattern: Shopify FAQ uses <label> for tab nav.
        When <label>Composição</label> is followed by <label>Modo de Uso</label>,
        the next-sibling 'Modo de Uso' must NOT be accepted as ingredients_inci
        content. Real content lives in a separate panel div."""
        html = """
        <html><body>
            <div class="tab-nav">
                <label>Composição</label>
                <label>Modo de uso</label>
                <label>Sobre o produto</label>
            </div>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        # No real content was provided — must NOT pick up sibling labels
        assert result.ingredients_inci_raw is None
        assert result.care_usage is None
        assert result.description is None

    def test_tab_buttons_dont_consume_each_other(self):
        """Salesforce Commerce Cloud (Kerastase) renders tab labels as <button>
        siblings. The button 'Como usar' must not consume 'Ingredientes' (the
        next sibling button) as its content. The fallback h2 inside the panel
        is the correct source.
        """
        html = """
        <html><body>
            <div class="tabs__nav">
                <button>Descrição</button>
                <button>Benefícios</button>
                <button>Como usar</button>
                <button>Ingredientes</button>
            </div>
            <div class="tabs__panel">
                <h2>Como usar o Produto</h2>
                <p>PASSO 1: Aplique nos cabelos molhados. PASSO 2: Massageie. PASSO 3: Enxágue bem.</p>
            </div>
            <div class="tabs__panel">
                <h2>Ingredientes</h2>
                <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum.</p>
            </div>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.care_usage is not None
        assert "PASSO 1" in result.care_usage
        # Must NOT have grabbed "Ingredientes" as the care_usage content
        assert result.care_usage != "Ingredientes"

    def test_composition_section(self):
        html = """
        <html><body>
            <h2>Principios Ativos</h2>
            <p>Queratina hidrolisada, óleo de argan, pantenol.</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.composition == "Queratina hidrolisada, óleo de argan, pantenol."

    def test_ingredients_inci_section(self):
        html = """
        <html><body>
            <h2>Ingredientes</h2>
            <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.ingredients_inci_raw is not None
        assert "Aqua" in result.ingredients_inci_raw

    def test_inci_validation_reclassifies_to_composition(self):
        """If a heading matches ingredients_inci but content fails INCI validation,
        it should be reclassified to composition."""
        html = """
        <html><body>
            <h2>Ingredientes</h2>
            <p>Queratina e óleo de argan</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        # Too short for INCI, should be reclassified to composition
        assert result.ingredients_inci_raw is None
        assert result.composition == "Queratina e óleo de argan"

    def test_multiple_sections(self):
        html = """
        <html><body>
            <h2>Sobre o Produto</h2>
            <p>Shampoo nutritivo com queratina.</p>
            <h2>Modo de Uso</h2>
            <p>Aplique nos cabelos molhados e massageie.</p>
            <h2>Ingredientes</h2>
            <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.description == "Shampoo nutritivo com queratina."
        assert result.care_usage == "Aplique nos cabelos molhados e massageie."
        assert result.ingredients_inci_raw is not None

    def test_heading_startswith_matching(self):
        """Heading 'Ingredientes do produto' should match label 'ingredientes'."""
        html = """
        <html><body>
            <h2>Ingredientes do produto</h2>
            <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.ingredients_inci_raw is not None

    def test_sections_list_populated(self):
        html = """
        <html><body>
            <h2>Descricao</h2>
            <p>Product description here.</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert len(result.sections) >= 1
        assert result.sections[0].taxonomy_field == "description"
        assert result.sections[0].source_section_label == "Descricao"

    def test_no_matching_sections(self):
        html = """
        <html><body>
            <h2>Avaliacoes</h2>
            <p>5 estrelas - ótimo produto!</p>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.description is None
        assert result.care_usage is None
        assert result.composition is None
        assert result.ingredients_inci_raw is None
        assert result.sections == []

    def test_button_and_strong_elements(self):
        """Section labels in button or strong elements should also be found."""
        html = """
        <html><body>
            <div>
                <strong>Modo de Uso</strong>
                <p>Aplique nos cabelos e massageie gentilmente.</p>
            </div>
        </body></html>
        """
        result = extract_sections_from_html(html, SECTION_LABEL_MAP)
        assert result.care_usage == "Aplique nos cabelos e massageie gentilmente."

    def test_composition_with_verbs_promoted_via_anchors(self):
        """Composition section that FAILS validate_inci_content (has marketing verbs)
        but HAS anchor INCI ingredients should still be promoted to ingredients_inci."""
        html = """<html><body>
        <h2>Composicao</h2>
        <p>Descubra a formula: Aqua, Sodium Laureth Sulfate, Glycerin, Parfum, Dimethicone, Cetearyl Alcohol</p>
        </body></html>"""
        section_map = {
            "composition": {"labels": ["composicao"]},
        }
        result = extract_sections_from_html(html, section_map)
        assert result.ingredients_inci_raw is not None
        assert "Aqua" in result.ingredients_inci_raw
