from types import SimpleNamespace

from src.core.gold_gate import evaluate_gold
from src.core.models import GoldStatus

GOOD_INCI = ["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine", "Glycerin", "Parfum", "Citric Acid"]
DESC = "Shampoo de limpeza suave com glicerina e betaína para uso diário em cabelos normais a oleosos."
USAGE = "Aplique no cabelo úmido, massageie suavemente e enxágue bem."


def _product(**kw):
    base = dict(
        product_name="Shampoo Hidratante Profissional 300ml",
        image_url_main="https://acme.com/i.jpg",
        image_url_front=None,
        inci_ingredients=list(GOOD_INCI),
        description=DESC,
        usage_instructions=USAGE,
        product_category="shampoo",
        verification_status="verified_inci",
        is_hidden=False,
        hair_relevance_reason="hair_keyword:shampoo",
        extraction_method="html_selector",
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestEvaluateGold:
    def test_complete_product_is_gold(self):
        ev = evaluate_gold(_product(), session=None)
        assert ev.gold_status == GoldStatus.GOLD
        assert ev.blockers == []

    def test_missing_usage_is_catalog(self):
        ev = evaluate_gold(_product(usage_instructions=None), session=None)
        assert ev.gold_status == GoldStatus.CATALOG
        assert any(b.field == "usage_instructions" for b in ev.blockers)

    def test_usage_that_is_only_a_label_is_catalog(self):
        ev = evaluate_gold(_product(usage_instructions="Como usar"), session=None)
        assert ev.gold_status == GoldStatus.CATALOG

    def test_non_hair_is_raw(self):
        ev = evaluate_gold(_product(hair_relevance_reason="non_hair:perfume"), session=None)
        assert ev.gold_status == GoldStatus.RAW
        assert any(b.code == "non_hair" for b in ev.blockers)

    def test_quarantined_is_raw(self):
        ev = evaluate_gold(_product(verification_status="quarantined"), session=None)
        assert ev.gold_status == GoldStatus.RAW

    def test_llm_only_inci_is_candidate(self):
        ev = evaluate_gold(_product(extraction_method="llm_grounded"), session=None)
        assert ev.gold_status == GoldStatus.GOLD_CANDIDATE
        assert any(b.code == "inci_llm_only" for b in ev.blockers)

    def test_marketing_inci_is_blocked_from_gold(self):
        # Passes basic list validation but is marketing copy -> must not be Gold
        ev = evaluate_gold(_product(
            inci_ingredients=["Brilho intenso", "Cor vibrante", "Hidratação profunda",
                              "Maciez", "Suavidade", "Longa duração"],
        ), session=None)
        assert ev.gold_status == GoldStatus.CATALOG
        assert any(b.code == "inci_is_marketing" for b in ev.blockers)

    def test_pricing_garbage_inci_is_catalog(self):
        # Checkout/pricing text scraped into the INCI field -> hard error, not Gold/candidate
        ev = evaluate_gold(_product(inci_ingredients=[
            "902xdeR$29", "90sem jurosTotalR$43", "Pix5% de descontoTotal:R$43",
            "Cartões de créditoParcelas", "Aqua", "Glycerin",
        ]), session=None)
        assert ev.gold_status == GoldStatus.CATALOG
        assert any(b.code == "inci_pricing_garbage" for b in ev.blockers)

    def test_short_inci_not_gold(self):
        ev = evaluate_gold(_product(inci_ingredients=["Aqua", "Glycerin", "Parfum"]), session=None)
        assert ev.gold_status == GoldStatus.CATALOG  # < 5 terms fails strict G1

    def test_invalid_category_not_gold(self):
        ev = evaluate_gold(_product(product_category="non_hair"), session=None)
        assert ev.gold_status == GoldStatus.CATALOG
        assert any(b.field == "product_category" for b in ev.blockers)

    def test_description_too_short_not_gold(self):
        ev = evaluate_gold(_product(description="Shampoo bom."), session=None)
        assert ev.gold_status == GoldStatus.CATALOG
        assert any(b.field == "description" for b in ev.blockers)

    def test_kit_is_never_gold(self):
        ev = evaluate_gold(_product(is_kit=True), session=None)
        assert ev.gold_status == GoldStatus.CATALOG
        assert any(b.code == "is_kit" for b in ev.blockers)
