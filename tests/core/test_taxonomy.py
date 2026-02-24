# tests/core/test_taxonomy.py
import pytest
from src.core.taxonomy import (
    HAIR_PRODUCT_TYPES,
    HAIR_KEYWORDS,
    EXCLUDE_KEYWORDS,
    KIT_PATTERNS,
    MALE_TARGETING_KEYWORDS,
    normalize_product_type,
    detect_gender_target,
    is_hair_relevant_by_keywords,
    is_kit_url,
)


class TestHairProductTypes:
    def test_shampoo_in_types(self):
        assert "shampoo" in HAIR_PRODUCT_TYPES

    def test_conditioner_in_types(self):
        assert "conditioner" in HAIR_PRODUCT_TYPES

    def test_body_lotion_not_in_types(self):
        assert "body_lotion" not in HAIR_PRODUCT_TYPES


class TestNormalizeProductType:
    def test_shampoo(self):
        assert normalize_product_type("Shampoo Reparador") == "shampoo"

    def test_condicionador(self):
        assert normalize_product_type("Condicionador Hidratante") == "conditioner"

    def test_mascara(self):
        assert normalize_product_type("Máscara Capilar") == "mask"

    def test_leave_in(self):
        assert normalize_product_type("Leave-in Protetor") == "leave_in"

    def test_oleo(self):
        assert normalize_product_type("Óleo Capilar Reparador") == "oil_serum"

    def test_pomada(self):
        assert normalize_product_type("Pomada Modeladora") == "pomade"

    def test_gel(self):
        assert normalize_product_type("Gel Fixador Forte") == "gel"

    def test_unknown(self):
        assert normalize_product_type("Produto Especial XYZ") is None

    def test_tonico(self):
        assert normalize_product_type("Tônico Capilar Antiqueda") == "tonic"


class TestDetectGenderTarget:
    def test_masculino(self):
        assert detect_gender_target("Shampoo Masculino Antiqueda", "https://example.com/masculino/shampoo") == "men"

    def test_for_men(self):
        assert detect_gender_target("Shampoo For Men", "https://example.com/produto") == "men"

    def test_kids(self):
        assert detect_gender_target("Shampoo Kids Cabelo Crespo", "https://example.com/kids") == "kids"

    def test_infantil(self):
        assert detect_gender_target("Shampoo Infantil", "https://example.com/produto") == "kids"

    def test_unisex(self):
        assert detect_gender_target("Shampoo Unissex", "https://example.com/produto") == "unisex"

    def test_unknown_default(self):
        assert detect_gender_target("Shampoo Reparador", "https://example.com/produto") == "unknown"


class TestIsHairRelevant:
    def test_shampoo_relevant(self):
        relevant, reason = is_hair_relevant_by_keywords(
            "Shampoo Reparador", "https://example.com/cabelo/shampoo", "Shampoo para cabelos danificados"
        )
        assert relevant is True
        assert reason != ""

    def test_body_not_relevant(self):
        relevant, reason = is_hair_relevant_by_keywords(
            "Hidratante Corporal", "https://example.com/corpo/hidratante", "Hidratante para o corpo"
        )
        assert relevant is False

    def test_scalp_relevant(self):
        relevant, reason = is_hair_relevant_by_keywords(
            "Tônico Capilar", "https://example.com/couro-cabeludo/tonico", "Tratamento para couro cabeludo"
        )
        assert relevant is True


class TestIsKitUrl:
    def test_kit_url(self):
        assert is_kit_url("https://example.com/kit-shampoo-condicionador") is True

    def test_combo_url(self):
        assert is_kit_url("https://example.com/combo-tratamento") is True

    def test_normal_url(self):
        assert is_kit_url("https://example.com/shampoo-reparador") is False

    def test_bundle_url(self):
        assert is_kit_url("https://example.com/bundle-cabelo") is True
