# tests/core/test_inci_validator.py
import pytest
from src.core.inci_validator import (
    clean_inci_text,
    validate_ingredient,
    detect_concatenation,
    detect_repetition,
    validate_inci_list,
    INCIValidationResult,
)


class TestCleanInciText:
    def test_cuts_at_modo_de_uso(self):
        raw = "Aqua, Sodium Laureth Sulfate, Glycerin. Modo de uso: aplicar nos cabelos"
        result = clean_inci_text(raw)
        assert "Modo de uso" not in result
        assert "Aqua" in result

    def test_cuts_at_how_to_use(self):
        raw = "Aqua, Cetearyl Alcohol. How to use: apply to wet hair"
        result = clean_inci_text(raw)
        assert "How to use" not in result

    def test_removes_garbage_phrases(self):
        raw = "Aqua, Glycerin, click here, Sodium Chloride, ver mais"
        result = clean_inci_text(raw)
        assert "click here" not in result
        assert "ver mais" not in result

    def test_removes_como_usar(self):
        raw = "Aqua, Glycerin, Parfum. Como usar: massageie"
        result = clean_inci_text(raw)
        assert "Como usar" not in result

    def test_cuts_at_beneficios(self):
        raw = "Aqua, Glycerin, Parfum. Benefícios: hidratação intensa"
        result = clean_inci_text(raw)
        assert "Benefícios" not in result


class TestValidateIngredient:
    def test_valid_ingredient(self):
        assert validate_ingredient("Sodium Laureth Sulfate") is True

    def test_too_short(self):
        assert validate_ingredient("A") is False

    def test_too_long(self):
        assert validate_ingredient("A" * 81) is False

    def test_contains_url(self):
        assert validate_ingredient("https://example.com") is False

    def test_contains_verb_instruction(self):
        assert validate_ingredient("Aplique nos cabelos molhados") is False

    def test_too_many_words(self):
        assert validate_ingredient("one two three four five six seven eight nine") is False

    def test_valid_complex(self):
        assert validate_ingredient("PEG-120 Methyl Glucose Trioleate") is True


class TestDetectConcatenation:
    def test_multiple_aqua(self):
        ingredients = [
            "Aqua", "Glycerin", "Parfum",
            "Aqua", "Cetearyl Alcohol", "Dimethicone",
        ]
        assert detect_concatenation(ingredients) is True

    def test_product_headings(self):
        ingredients = [
            "Shampoo:", "Aqua", "Glycerin",
            "Condicionador:", "Aqua", "Cetearyl Alcohol",
        ]
        assert detect_concatenation(ingredients) is True

    def test_clean_list(self):
        ingredients = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride"]
        assert detect_concatenation(ingredients) is False


class TestDetectRepetition:
    def test_repeated_block(self):
        block = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid"]
        ingredients = block + block
        assert detect_repetition(ingredients) is True

    def test_no_repetition(self):
        ingredients = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid"]
        assert detect_repetition(ingredients) is False

    def test_triple_repetition(self):
        block = ["Aqua", "Glycerin", "Parfum"]
        ingredients = block * 3
        assert detect_repetition(ingredients) is True


class TestValidateInciList:
    def test_valid_list(self):
        ingredients = [
            "Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
            "Glycerin", "Parfum", "Citric Acid",
        ]
        result = validate_inci_list(ingredients)
        assert result.valid is True
        assert len(result.cleaned) == 6

    def test_too_few_ingredients(self):
        result = validate_inci_list(["Aqua", "Glycerin"])
        assert result.valid is False
        assert "min_ingredients" in result.rejection_reason

    def test_deduplication(self):
        ingredients = [
            "Aqua", "aqua", "Glycerin", "GLYCERIN",
            "Parfum", "Sodium Chloride", "Citric Acid",
        ]
        result = validate_inci_list(ingredients)
        assert result.valid is True
        assert len(result.cleaned) == 5

    def test_concatenation_rejected(self):
        ingredients = [
            "Aqua", "Glycerin", "Parfum",
            "Aqua", "Cetearyl Alcohol", "Dimethicone",
            "Sodium Chloride",
        ]
        result = validate_inci_list(ingredients)
        assert result.valid is False
        assert "concat" in result.rejection_reason

    def test_repetition_rejected(self):
        block = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid"]
        result = validate_inci_list(block + block)
        assert result.valid is False
        assert "repetition" in result.rejection_reason
