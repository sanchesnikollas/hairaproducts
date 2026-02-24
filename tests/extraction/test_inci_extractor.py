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
