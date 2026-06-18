from src.enrichment.ocr_matcher import match_ocr

GOOD_INCI = ["Aqua", "Sodium Laureth Sulfate", "Glycerin", "Parfum", "Citric Acid"]


def _cand(**kw):
    base = dict(id="p1", product_name="Shampoo Hidratante 300ml", ean=None,
                size_volume="300ml", inci_ingredients=list(GOOD_INCI),
                gold_status="gold", brand_slug="acme")
    base.update(kw)
    return base


class TestMatchOcr:
    def test_ean_exact_match(self):
        cands = [_cand(id="x", ean="7891234567890")]
        r = match_ocr(candidates=cands, ean="789 1234 567890", product_name_text="qualquer coisa")
        assert r["match"]["match_method"] == "ean"
        assert r["match"]["match_confidence"] == 1.0
        assert r["match"]["product_id"] == "x"

    def test_name_fuzzy_auto_match(self):
        cands = [_cand(id="p1", product_name="Shampoo Hidratante Intenso 300ml")]
        r = match_ocr(candidates=cands, brand_text="Acme",
                      product_name_text="Shampoo Hidratante Intenso 300ml")
        assert r["match"] is not None
        assert r["match"]["match_method"] == "name_fuzzy"
        assert r["match"]["match_confidence"] >= 0.9

    def test_volume_conflict_blocks_auto_match(self):
        # same name, different volume -> capped below auto -> no confident match
        cands = [_cand(id="p1", product_name="Shampoo Hidratante", size_volume="1L")]
        r = match_ocr(candidates=cands, product_name_text="Shampoo Hidratante", volume_text="300ml")
        assert r["match"] is None
        assert r["candidates"] and r["candidates"][0]["product_id"] == "p1"

    def test_ambiguous_returns_candidates(self):
        # ~0.78 ratio -> review band (>=0.75, <0.90): no auto match, but a candidate
        cands = [_cand(id="p1", product_name="Shampoo Hidratante 300ml", size_volume="300ml")]
        r = match_ocr(candidates=cands, product_name_text="Shampoo Hidratante Reparador")
        assert r["match"] is None
        assert any(c["product_id"] == "p1" for c in r["candidates"])

    def test_not_in_base(self):
        r = match_ocr(candidates=[_cand(product_name="Condicionador X")],
                      product_name_text="Produto Totalmente Diferente Zzz")
        assert r["match"] is None
        assert r["not_in_base"] is True

    def test_inci_verification_confirmed(self):
        cands = [_cand(id="p1", product_name="Shampoo Hidratante 300ml", inci_ingredients=list(GOOD_INCI))]
        r = match_ocr(candidates=cands, brand_text="Acme",
                      product_name_text="Shampoo Hidratante 300ml",
                      back_label_inci=GOOD_INCI)
        assert r["match"]["inci_verification"]["verdict"] == "confirmed"

    def test_inci_verification_mismatch(self):
        cands = [_cand(id="p1", product_name="Shampoo Hidratante 300ml", inci_ingredients=list(GOOD_INCI))]
        r = match_ocr(candidates=cands, brand_text="Acme",
                      product_name_text="Shampoo Hidratante 300ml",
                      back_label_inci=["Totally", "Different", "Stuff", "Here", "Now"])
        assert r["match"]["inci_verification"]["verdict"] == "mismatch"

    def test_non_gold_match_reports_not_gold(self):
        cands = [_cand(id="p1", product_name="Shampoo Hidratante 300ml", gold_status="catalog")]
        r = match_ocr(candidates=cands, brand_text="Acme", product_name_text="Shampoo Hidratante 300ml")
        assert r["match"] is not None
        assert r["match"]["is_gold"] is False
        assert r["is_gold"] is False
