# tests/extraction/test_inci_extractor.py
import pytest
from src.extraction.inci_extractor import extract_and_validate_inci


class TestExtractAndValidateInci:
    def test_clean_inci_from_raw(self):
        raw = "Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid"
        result = extract_and_validate_inci(raw)
        assert result.valid is True
        assert len(result.cleaned) == 6

    def test_inci_with_cut_marker(self):
        raw = "Aqua, Sodium Laureth Sulfate, Glycerin, Parfum, Citric Acid, Panthenol. Modo de uso: aplique nos cabelos"
        result = extract_and_validate_inci(raw)
        assert result.valid is True
        assert "Modo de uso" not in " ".join(result.cleaned)

    def test_inci_with_garbage(self):
        raw = "Aqua, Sodium Laureth Sulfate, click here, Glycerin, Parfum, ver mais, Citric Acid"
        result = extract_and_validate_inci(raw)
        assert result.valid is True
        assert all("click" not in i for i in result.cleaned)

    def test_concatenated_inci_rejected(self):
        raw = "Shampoo: Aqua, Glycerin, Parfum. Condicionador: Aqua, Cetearyl Alcohol, Dimethicone"
        result = extract_and_validate_inci(raw)
        assert result.valid is False

    def test_too_few_rejected(self):
        raw = "Aqua, Glycerin"
        result = extract_and_validate_inci(raw)
        assert result.valid is False

    def test_none_input(self):
        result = extract_and_validate_inci(None)
        assert result.valid is False


class TestNewlineSeparator:
    def test_newline_separated_inci(self):
        """INCI list separated by newlines should be split correctly."""
        raw = "Aqua\nSodium Laureth Sulfate\nCocamidopropyl Betaine\nGlycerin\nParfum"
        result = extract_and_validate_inci(raw, has_section_context=True)
        assert result.valid
        assert len(result.cleaned) >= 5

    def test_bullet_with_wrap_newlines(self):
        """Real Kerastase case: bullet-separated list with newlines wrapping
        a single ingredient name across two lines (e.g. 'Cetearyl\\nAlcohol'
        is ONE ingredient, not two)."""
        raw = (
            "Aqua / Water•Cetearyl\n"
            "                Alcohol•Amodimethicone•Hydroxypropyl Starch Phosphate\n"
            "                Behentrimonium Chloride•Phenoxyethanol"
        )
        result = extract_and_validate_inci(raw, has_section_context=True)
        assert result.valid
        # Cetearyl Alcohol must remain a single ingredient
        joined = " | ".join(result.cleaned).lower()
        assert "cetearyl alcohol" in joined
        assert len(result.cleaned) >= 5


class TestBilingualParenthetical:
    def test_bilingual_parenthetical_stripped(self):
        """Parenthetical translations should be stripped before validation."""
        raw = "Aqua (Agua Purificada), Sodium Laureth Sulfate (Sulfato de Sodio), Glycerin (Glicerina Natural), Cocamidopropyl Betaine, Parfum"
        result = extract_and_validate_inci(raw, has_section_context=True)
        assert result.valid
        assert "Aqua" in result.cleaned

    def test_bilingual_preserves_short_parens(self):
        """Short parentheticals like (and) should NOT be stripped."""
        raw = "PEG-40 Hydrogenated Castor Oil (and) Polysorbate 20, Aqua, Glycerin, Parfum, Sodium Chloride"
        result = extract_and_validate_inci(raw, has_section_context=True)
        # (and) should be preserved in the ingredients
        assert any("and" in ing.lower() for ing in result.cleaned)

    def test_bilingual_preserves_inci_standard_parens(self):
        """INCI-standard parentheticals like (CI 77891), (Vitamin E) should be preserved."""
        raw = "Aqua, Titanium Dioxide (CI 77891), Tocopherol (Vitamin E), Glycerin, Parfum"
        result = extract_and_validate_inci(raw, has_section_context=True)
        assert result.valid
        assert any("CI 77891" in ing for ing in result.cleaned)
