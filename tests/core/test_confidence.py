from __future__ import annotations
import pytest
from src.core.confidence import calculate_confidence


class TestConfidenceScore:
    def test_fully_complete_verified_product(self):
        score, factors = calculate_confidence(
            fields={"product_name": "X", "product_category": "hair_care", "brand_slug": "test",
                    "description": "desc", "inci_ingredients": "Water, Glycerin", "image_url_main": "http://img.jpg"},
            validated_ingredient_count=10,
            total_ingredient_count=10,
            status_editorial="aprovado",
        )
        assert score == 100.0
        assert factors["completude"] == 1.0
        assert factors["parsing"] == 1.0
        assert factors["validacao_humana"] == 1.0

    def test_empty_product(self):
        score, factors = calculate_confidence(
            fields={"product_name": None, "product_category": None, "brand_slug": None,
                    "description": None, "inci_ingredients": None, "image_url_main": None},
            validated_ingredient_count=0,
            total_ingredient_count=0,
            status_editorial="pendente",
        )
        assert score == 0.0

    def test_partial_product(self):
        score, factors = calculate_confidence(
            fields={"product_name": "Shampoo", "product_category": "hair_care", "brand_slug": "test",
                    "description": None, "inci_ingredients": "Water", "image_url_main": None},
            validated_ingredient_count=5,
            total_ingredient_count=10,
            status_editorial="em_revisao",
        )
        # completude: 4/6 = 0.667, parsing: 5/10 = 0.5, validacao: 0.5
        assert 40 < score < 60
        assert factors["completude"] == pytest.approx(4 / 6, rel=0.01)
        assert factors["parsing"] == 0.5
        assert factors["validacao_humana"] == 0.5

    def test_no_inci_gives_zero_parsing(self):
        score, factors = calculate_confidence(
            fields={"product_name": "X", "product_category": "Y", "brand_slug": "Z",
                    "description": "D", "inci_ingredients": None, "image_url_main": "I"},
            validated_ingredient_count=0,
            total_ingredient_count=0,
            status_editorial="aprovado",
        )
        assert factors["parsing"] == 0.0
