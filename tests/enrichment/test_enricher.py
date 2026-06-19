from __future__ import annotations

from types import SimpleNamespace

from src.enrichment.enricher import _has_inci, pick_usage


class TestPickUsage:
    def test_returns_first_valid_usage(self):
        assert pick_usage(
            ["Aplique o produto no cabelo úmido, massageie e enxágue."]
        ) == "Aplique o produto no cabelo úmido, massageie e enxágue."

    def test_skips_invalid_until_a_valid_one(self):
        # too short, then a description with no action verb, then a real one
        result = pick_usage([
            "Aplicar.",
            "Produto indicado para cabelos oleosos e mistos do dia a dia.",
            "Massageie nos fios molhados e deixe agir por 3 minutos antes de enxaguar.",
        ])
        assert result == "Massageie nos fios molhados e deixe agir por 3 minutos antes de enxaguar."

    def test_strips_whitespace(self):
        assert pick_usage(["  Aplique nos cabelos e massageie suavemente até espumar.  "]) \
            == "Aplique nos cabelos e massageie suavemente até espumar."

    def test_none_when_no_valid_candidate(self):
        assert pick_usage([None, "", "Shampoo", "Como usar"]) is None

    def test_empty_list(self):
        assert pick_usage([]) is None


class TestHasInci:
    def test_true_for_real_list(self):
        assert _has_inci(SimpleNamespace(inci_ingredients=["Aqua", "Sodium Laureth Sulfate"])) is True

    def test_false_for_none(self):
        assert _has_inci(SimpleNamespace(inci_ingredients=None)) is False

    def test_false_for_empty_list(self):
        assert _has_inci(SimpleNamespace(inci_ingredients=[])) is False

    def test_false_for_empty_string_markers(self):
        assert _has_inci(SimpleNamespace(inci_ingredients="[]")) is False
        assert _has_inci(SimpleNamespace(inci_ingredients="null")) is False
