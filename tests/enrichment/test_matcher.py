from __future__ import annotations
from src.enrichment.matcher import normalize_name, detect_product_type, match_products


class TestNormalizeName:
    def test_lowercase_and_strip_accents(self):
        assert normalize_name("Máscara Nutrição") == "mascara nutricao"

    def test_remove_sizes(self):
        assert normalize_name("Shampoo Hidratante 300ml") == "shampoo hidratante"
        assert normalize_name("Máscara 1kg") == "mascara"

    def test_remove_unit_suffix(self):
        assert normalize_name("Condicionador 200ml - un") == "condicionador"

    def test_collapse_whitespace(self):
        assert normalize_name("Shampoo   Extra   Liso") == "shampoo extra liso"

    def test_strip_space_separated_brand(self):
        # Brand slug is hyphenated ("bio-extratus") but marketplace names spell it
        # space-separated ("BIO EXTRATUS ..."). Both forms (and the flattened one)
        # must be stripped so surviving brand tokens don't dilute the match score.
        assert normalize_name(
            "BIO EXTRATUS Condicionador Cachos 250ml", strip_brand="bio-extratus"
        ) == "condicionador cachos"
        assert normalize_name(
            "Bio-Extratus Shampoo Neutro 250ml", strip_brand="bio-extratus"
        ) == "shampoo neutro"
        assert normalize_name(
            "BioExtratus Mascara Tutano 1kg", strip_brand="bio-extratus"
        ) == "mascara tutano"


class TestDetectProductType:
    def test_shampoo(self):
        assert detect_product_type("Shampoo Hidratante 300ml") == "shampoo"

    def test_condicionador(self):
        assert detect_product_type("Condicionador Nutrição 200ml") == "condicionador"

    def test_mascara(self):
        assert detect_product_type("Máscara de Tratamento 500g") == "mascara"

    def test_leave_in(self):
        assert detect_product_type("Leave-in Finalizador 150ml") == "leave-in"

    def test_no_type(self):
        assert detect_product_type("Produto Capilar Especial") is None


class TestMatchProducts:
    def test_exact_match_auto_apply(self):
        results = match_products(
            product_name="Shampoo Pos Quimica 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Shampoo Pós Química 350ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua", "Sodium"], "id": "ext-1", "source": "belezanaweb", "source_url": "https://example.com/1"},
            ],
        )
        assert len(results) == 1
        assert results[0]["action"] == "auto_apply"
        assert results[0]["score"] > 0.90

    def test_brand_prefixed_same_volume_auto_applies(self):
        # Real case from bio-extratus: the marketplace prefixes the brand and our
        # catalog does not, but it is the same product at the same volume. The brand
        # prefix must not block the high-confidence auto_apply.
        results = match_products(
            product_name="Condicionador Cachos 250ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "BIO EXTRATUS CONDICIONADOR CACHOS 250ML", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb", "source_url": "x"},
            ],
        )
        assert len(results) == 1
        assert results[0]["score"] > 0.90
        assert results[0]["action"] == "auto_apply"

    def test_similar_match_review(self):
        results = match_products(
            product_name="Shampoo Hidratação Bio Extratus 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Bio Extratus Shampoo Hidratação Intensa 300ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb", "source_url": "https://example.com/1"},
            ],
        )
        assert len(results) == 1
        assert results[0]["action"] == "review"

    def test_type_mismatch_goes_to_review(self):
        results = match_products(
            product_name="Bio Extratus Pos Quimica Shampoo 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Bio Extratus Pos Quimica Condicionador 350ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb", "source_url": "https://example.com/1"},
            ],
        )
        if results:
            assert results[0]["action"] == "review"

    def test_low_match_discarded(self):
        results = match_products(
            product_name="Shampoo Pos Quimica 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Oleo de Argan Leave-in 100ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb", "source_url": "https://example.com/1"},
            ],
        )
        assert len(results) == 0

    def test_no_inci_candidates_skipped(self):
        results = match_products(
            product_name="Shampoo Test",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Shampoo Test", "brand_slug": "bio-extratus",
                 "inci_ingredients": None, "id": "ext-1", "source": "belezanaweb", "source_url": "https://example.com/1"},
            ],
        )
        assert len(results) == 0

    def test_ean_exact_match_overrides_name(self):
        results = match_products(
            product_name="Nome Totalmente Diferente Zzz",
            product_brand="bio-extratus",
            product_ean="789-1234-567890",
            candidates=[
                {"product_name": "Outro Nome Qualquer", "brand_slug": "bio-extratus", "ean": "7891234567890",
                 "inci_ingredients": ["Aqua", "Sodium"], "id": "ext-1", "source": "belezanaweb", "source_url": "x"},
            ],
        )
        assert len(results) == 1
        assert results[0]["action"] == "auto_apply"
        assert results[0]["score"] == 1.0

    def test_volume_conflict_forces_review(self):
        # identical name (both normalize away the volume) but 300ml vs 1L -> review
        results = match_products(
            product_name="Shampoo Hidratante 300ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Shampoo Hidratante 1L", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb", "source_url": "x"},
            ],
        )
        assert len(results) == 1
        assert results[0]["action"] == "review"  # not auto_apply despite name match
