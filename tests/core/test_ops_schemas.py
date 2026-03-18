from __future__ import annotations
import pytest
from src.core.ops_schemas import InterpretationData, ApplicationData, DecisionData


class TestInterpretationData:
    def test_valid_data(self):
        d = InterpretationData(
            formula_classification="hidratacao",
            key_actives=["pantenol", "glicerina"],
            silicone_presence=False,
        )
        assert d.formula_classification == "hidratacao"

    def test_minimal_data(self):
        d = InterpretationData()
        assert d.formula_classification is None
        assert d.key_actives == []


class TestApplicationData:
    def test_valid_data(self):
        d = ApplicationData(
            when_to_use="Apos lavagem",
            ideal_hair_types=["cacheado", "crespo"],
        )
        assert len(d.ideal_hair_types) == 2

    def test_minimal_data(self):
        d = ApplicationData()
        assert d.when_to_use is None
        assert d.ideal_hair_types == []
        assert d.cautions == []


class TestDecisionData:
    def test_ready_for_publication(self):
        d = DecisionData(
            summary="Shampoo suave para uso diario",
            ready_for_publication=True,
            requires_human_review=False,
        )
        assert d.ready_for_publication is True

    def test_defaults(self):
        d = DecisionData()
        assert d.ready_for_publication is False
        assert d.requires_human_review is True
        assert d.strengths == []
        assert d.concerns == []
