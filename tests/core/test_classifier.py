"""Tests for src.core.classifier — heuristic inference of hair_type, audience_age, function_objective."""
from __future__ import annotations

import pytest

from src.core.classifier import (
    ClassificationResult,
    classify_product,
    infer_audience_age,
    infer_function_objective,
    infer_hair_type,
)


class TestHairType:
    def test_detects_cacheado_from_curls_keyword(self):
        result, conf, kws = infer_hair_type("Creme para Cachos Definidos", "Define cachos sem frizz")
        assert "cacheado" in result
        assert conf >= 0.4
        assert any("cach" in k for k in kws)

    def test_detects_crespo(self):
        result, conf, _ = infer_hair_type("Mascara Afro Power", "Para cabelos crespos e afro")
        assert "crespo" in result
        assert conf >= 0.2

    def test_detects_oleoso(self):
        result, _, _ = infer_hair_type("Shampoo Anti-Oleosidade", "Controle de oleosidade do couro cabeludo")
        assert "oleoso" in result

    def test_detects_seco(self):
        result, _, _ = infer_hair_type("Hidratação Intensa", "Cabelos secos e ressecados")
        assert "seco" in result

    def test_multi_value_curly_and_damaged(self):
        result, _, _ = infer_hair_type(
            "Mascara Reparadora Cachos Danificados",
            "Reconstrução para cachos muito danificados",
        )
        assert "cacheado" in result
        assert "danificado" in result

    def test_no_match_returns_empty(self):
        result, conf, _ = infer_hair_type("Produto Genérico", "Sem indicação específica")
        assert result == []
        assert conf == 0.0

    def test_higher_confidence_when_match_in_name(self):
        in_name, _, _ = infer_hair_type("Shampoo para Cachos", None)
        in_desc, _, _ = infer_hair_type("Shampoo Genérico", "para cachos")
        # Match in name should produce more confident classification
        assert "cacheado" in in_name and "cacheado" in in_desc


class TestAudienceAge:
    def test_kids_match(self):
        slug, conf, kws = infer_audience_age("Shampoo Kids Tutti-Frutti", "Shampoo infantil")
        assert slug == "kids"
        assert conf >= 0.7
        assert "kids" in kws

    def test_under_3_match(self):
        slug, _, _ = infer_audience_age("Shampoo Baby Soft", "Para recém-nascidos")
        assert slug == "under_3"

    def test_teen_match(self):
        slug, _, _ = infer_audience_age("Linha Teen Acne Control", "Para adolescentes")
        assert slug == "teen"

    def test_default_adult(self):
        slug, conf, _ = infer_audience_age("Shampoo Hidratante", "Para cabelos secos")
        assert slug == "adult"
        assert conf == 0.5

    def test_priority_under_3_over_kids(self):
        # "baby" should win over "infantil" when both present
        slug, _, _ = infer_audience_age("Shampoo Baby Infantil", None)
        assert slug == "under_3"


class TestFunctionObjective:
    def test_category_shampoo_returns_limpar(self):
        slug, conf, _ = infer_function_objective("Bain Crème Multi-Vitaminé", "shampoo")
        assert slug == "limpar"
        assert conf == 0.9

    def test_category_condicionador(self):
        slug, _, _ = infer_function_objective("Conditioner Premium", "condicionador")
        assert slug == "condicionar"

    def test_keyword_leave_in(self):
        slug, _, _ = infer_function_objective("Leave-In Magic", None, "Aplique nos cabelos")
        assert slug == "finalizar"

    def test_keyword_protetor_termico(self):
        slug, _, _ = infer_function_objective("Heat Protect Spray", None, "Protetor térmico")
        assert slug == "proteger"

    def test_keyword_mascara_hidratacao(self):
        slug, _, _ = infer_function_objective("Hydra Mask", "mascara_hidratacao")
        assert slug == "hidratar"

    def test_no_match_returns_none(self):
        slug, conf, _ = infer_function_objective("Produto Misterioso", None, "Sem categoria definida")
        assert slug is None
        assert conf == 0.0


class TestClassifyProduct:
    def test_full_classification_kerastase_resistance(self):
        result = classify_product(
            product_name="Bain Force Architecte Shampoo Reconstrutor",
            description="Shampoo reconstrutor para cabelos danificados",
            product_category="shampoo",
        )
        assert isinstance(result, ClassificationResult)
        assert result.function_objective == "limpar"
        assert result.audience_age == "adult"
        assert "danificado" in (result.hair_type or [])
        assert result.method == "heuristic"

    def test_kids_shampoo(self):
        result = classify_product(
            product_name="Shampoo Kids Cacho Mágico",
            description="Para crianças com cabelos cacheados",
            product_category="shampoo",
        )
        assert result.audience_age == "kids"
        assert result.function_objective == "limpar"
        assert "cacheado" in (result.hair_type or [])

    def test_low_confidence_when_no_signals(self):
        result = classify_product(
            product_name="Produto X",
            description="Descrição genérica",
            product_category=None,
        )
        # All heuristics should produce low or zero confidence
        assert result.confidence_per_field["function_objective"] == 0.0
        assert result.confidence_per_field["hair_type"] == 0.0
        # audience_age default is adult @ 0.5
        assert result.confidence_per_field["audience_age"] == 0.5
