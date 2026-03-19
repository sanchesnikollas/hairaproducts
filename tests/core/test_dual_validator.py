from __future__ import annotations

import pytest
from src.core.dual_validator import compare_fields, normalize_text, compare_inci_lists


class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_collapses_spaces(self):
        assert normalize_text("hello   world") == "hello world"

    def test_lowercases(self):
        assert normalize_text("Hello World") == "hello world"

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""


class TestCompareInciLists:
    def test_identical_lists_match(self):
        a = ["Water", "Glycerin", "Dimethicone"]
        b = ["Water", "Glycerin", "Dimethicone"]
        result = compare_inci_lists(a, b)
        assert result.matches is True

    def test_case_difference_matches(self):
        a = ["Water", "GLYCERIN"]
        b = ["water", "Glycerin"]
        result = compare_inci_lists(a, b)
        assert result.matches is True

    def test_different_order_diverges(self):
        a = ["Water", "Glycerin"]
        b = ["Glycerin", "Water"]
        result = compare_inci_lists(a, b)
        assert result.matches is False

    def test_different_length_diverges(self):
        a = ["Water", "Glycerin"]
        b = ["Water"]
        result = compare_inci_lists(a, b)
        assert result.matches is False


class TestCompareFields:
    def test_exact_match(self):
        result = compare_fields("product_name", "Shampoo X", "Shampoo X")
        assert result.resolution == "auto_matched"

    def test_whitespace_normalization(self):
        result = compare_fields("product_name", "Shampoo  X", "Shampoo X")
        assert result.resolution == "auto_matched"

    def test_price_within_tolerance(self):
        result = compare_fields("price", "29.90", "29.80")
        assert result.resolution == "auto_matched"

    def test_price_outside_tolerance(self):
        result = compare_fields("price", "29.90", "35.00")
        assert result.resolution == "pending"

    def test_description_similar(self):
        result = compare_fields("description", "A great shampoo for all hair types", "A great shampoo for all hair types.")
        assert result.resolution == "auto_matched"

    def test_description_different(self):
        result = compare_fields("description", "A shampoo", "A completely different conditioner product")
        assert result.resolution == "pending"

    def test_both_none_matches(self):
        result = compare_fields("product_name", None, None)
        assert result.resolution == "auto_matched"
