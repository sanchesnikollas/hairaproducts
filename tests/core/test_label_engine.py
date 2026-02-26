# tests/core/test_label_engine.py
import pytest
import yaml
from src.core.label_engine import (
    LabelEngine,
    LabelResult,
    LabelEvidence,
    load_seal_keywords,
    load_prohibited_list,
)


# ---------------------------------------------------------------------------
# Fixtures — minimal YAML configs written to tmp_path
# ---------------------------------------------------------------------------

@pytest.fixture
def seals_yaml(tmp_path):
    """Minimal seals config with a few seals for testing."""
    data = {
        "seals": {
            "sulfate_free": {
                "keywords": ["sulfate free", "sulfate-free", "sem sulfato"],
            },
            "vegan": {
                "keywords": ["vegan", "vegano", "vegana"],
            },
            "silicone_free": {
                "keywords": ["silicone free", "silicone-free", "sem silicone"],
            },
            "low_poo": {
                "keywords": ["low poo", "low-poo"],
            },
            "no_poo": {
                "keywords": ["no poo", "no-poo"],
            },
        }
    }
    path = tmp_path / "seals.yaml"
    path.write_text(yaml.dump(data))
    return path


@pytest.fixture
def silicones_yaml(tmp_path):
    """Minimal silicones config."""
    data = {
        "silicones": [
            "dimethicone",
            "amodimethicone",
            "cyclomethicone",
            "cyclopentasiloxane",
        ]
    }
    path = tmp_path / "silicones.yaml"
    path.write_text(yaml.dump(data))
    return path


@pytest.fixture
def surfactants_yaml(tmp_path):
    """Minimal surfactants config."""
    data = {
        "low_poo_prohibited": [
            "sodium lauryl sulfate",
            "sodium laureth sulfate",
            "ammonium lauryl sulfate",
        ],
        "no_poo_prohibited": [
            "sodium lauryl sulfate",
            "sodium laureth sulfate",
            "ammonium lauryl sulfate",
            "cocamidopropyl betaine",
            "decyl glucoside",
        ],
    }
    path = tmp_path / "surfactants.yaml"
    path.write_text(yaml.dump(data))
    return path


@pytest.fixture
def engine(seals_yaml, silicones_yaml, surfactants_yaml):
    """LabelEngine wired to minimal test YAML configs."""
    return LabelEngine(
        seals_path=seals_yaml,
        silicones_path=silicones_yaml,
        surfactants_path=surfactants_yaml,
    )


# ---------------------------------------------------------------------------
# TestLoadConfig
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_seal_keywords(self, seals_yaml):
        result = load_seal_keywords(seals_yaml)
        assert isinstance(result, dict)
        assert "sulfate_free" in result
        assert "vegan" in result
        # All keywords should be lowercased
        for seal_name, keywords in result.items():
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword not lowered: {kw}"

    def test_load_prohibited_list(self, silicones_yaml):
        result = load_prohibited_list(silicones_yaml, "silicones")
        assert isinstance(result, list)
        assert "dimethicone" in result
        assert "amodimethicone" in result
        # All entries should be lowercased
        for item in result:
            assert item == item.lower(), f"Item not lowered: {item}"


# ---------------------------------------------------------------------------
# TestKeywordDetection
# ---------------------------------------------------------------------------

class TestKeywordDetection:
    def test_detects_sulfate_free_in_description(self, engine):
        result = engine.detect(description="This shampoo is sulfate free and gentle")
        assert "sulfate_free" in result.detected
        assert "official_text" in result.sources

    def test_detects_vegan_in_product_name(self, engine):
        result = engine.detect(product_name="Super Vegan Shampoo 300ml")
        assert "vegan" in result.detected
        assert "official_text" in result.sources

    def test_detects_in_benefits_claims(self, engine):
        result = engine.detect(
            benefits_claims=["Deep hydration", "Sulfate-free formula", "For all hair types"]
        )
        assert "sulfate_free" in result.detected
        assert "official_text" in result.sources

    def test_no_false_positives(self, engine):
        result = engine.detect(
            description="A moisturizing shampoo for dry hair",
            product_name="Hydra Shampoo 250ml",
        )
        assert result.detected == []
        assert result.inferred == []

    def test_case_insensitive(self, engine):
        result = engine.detect(description="This product is SULFATE FREE and VEGAN")
        assert "sulfate_free" in result.detected
        assert "vegan" in result.detected


# ---------------------------------------------------------------------------
# TestINCIInference
# ---------------------------------------------------------------------------

class TestINCIInference:
    def test_infers_silicone_free(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol", "Parfum"]
        )
        assert "silicone_free" in result.inferred
        assert "inci_analysis" in result.sources

    def test_does_not_infer_silicone_free_when_silicone_present(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Dimethicone", "Parfum"]
        )
        assert "silicone_free" not in result.inferred

    def test_infers_low_poo(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Cocamidopropyl Betaine", "Glycerin", "Parfum"]
        )
        assert "low_poo" in result.inferred
        assert "inci_analysis" in result.sources

    def test_does_not_infer_low_poo_with_harsh_sulfate(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Glycerin", "Parfum"]
        )
        assert "low_poo" not in result.inferred

    def test_infers_no_poo_when_no_sulfates_no_silicones(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol", "Parfum"]
        )
        assert "no_poo" in result.inferred

    def test_does_not_infer_no_poo_with_silicone(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Amodimethicone", "Parfum"]
        )
        assert "no_poo" not in result.inferred

    def test_no_inference_without_inci(self, engine):
        result = engine.detect(
            description="A great shampoo",
            inci_ingredients=None,
        )
        assert result.inferred == []


# ---------------------------------------------------------------------------
# TestConfidenceScoring
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    def test_no_seals_zero_confidence(self, engine):
        result = engine.detect(description="A moisturizing shampoo for dry hair")
        assert result.confidence == 0.0

    def test_only_inferred_half_confidence(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol", "Parfum"]
        )
        # No keyword matches, only INCI inferences
        assert result.confidence == 0.5

    def test_only_detected_high_confidence(self, engine):
        result = engine.detect(description="This shampoo is sulfate free and vegan")
        assert result.confidence == 0.8

    def test_detected_and_inferred_highest_confidence(self, engine):
        result = engine.detect(
            description="This shampoo is sulfate free",
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol", "Parfum"],
        )
        # Has detected seals AND inferred seals
        assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# TestLabelResult
# ---------------------------------------------------------------------------

class TestLabelResult:
    def test_to_dict(self):
        evidence = LabelEvidence(
            field_name="label:sulfate_free",
            extraction_method="text_keyword",
            raw_source_text="sulfate free",
            evidence_locator="description",
        )
        result = LabelResult(
            detected=["sulfate_free"],
            inferred=["silicone_free"],
            confidence=0.9,
            sources=["official_text", "inci_analysis"],
            manually_verified=False,
            manually_overridden=False,
            _evidence=[evidence],
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["detected"] == ["sulfate_free"]
        assert d["inferred"] == ["silicone_free"]
        assert d["confidence"] == 0.9
        assert d["sources"] == ["official_text", "inci_analysis"]
        assert d["manually_verified"] is False
        assert d["manually_overridden"] is False
        # _evidence should NOT be in the public dict
        assert "_evidence" not in d

    def test_evidence_entries(self):
        evidence = LabelEvidence(
            field_name="label:sulfate_free",
            extraction_method="text_keyword",
            raw_source_text="sulfate free",
            evidence_locator="description",
        )
        result = LabelResult(
            detected=["sulfate_free"],
            inferred=[],
            confidence=0.8,
            sources=["official_text"],
            manually_verified=False,
            manually_overridden=False,
            _evidence=[evidence],
        )
        entries = result.evidence_entries()
        assert isinstance(entries, list)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["field_name"] == "label:sulfate_free"
        assert entry["extraction_method"] == "text_keyword"
        assert entry["raw_source_text"] == "sulfate free"
        assert entry["evidence_locator"] == "description"
