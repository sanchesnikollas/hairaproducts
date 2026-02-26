# tests/core/test_label_engine.py
import pytest
import yaml
from src.core.label_engine import (
    LabelEngine,
    LabelResult,
    LabelEvidence,
    load_seal_keywords,
    load_prohibited_list,
    extract_seal_image_texts,
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
            "organic": {
                "keywords": ["organico", "organic", "certified organic", "bio certificado"],
            },
            "natural": {
                "keywords": ["natural", "100% natural", "ingredientes naturais"],
            },
            "low_poo": {
                "keywords": ["low poo", "low-poo"],
            },
            "no_poo": {
                "keywords": ["no poo", "no-poo"],
            },
            "cruelty_free": {
                "keywords": ["cruelty free", "cruelty-free"],
            },
            "petrolatum_free": {
                "keywords": ["sem petrolato", "petrolatum free"],
            },
            "dye_free": {
                "keywords": ["sem corante", "dye free"],
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
# TestWordBoundary — prevents false positives from substring matching
# ---------------------------------------------------------------------------

class TestWordBoundary:
    def test_bio_does_not_match_biofilm(self, engine):
        """'bio certificado' should NOT match 'probiotic biofilm'."""
        result = engine.detect(description="Protects against probiotic biofilm buildup")
        assert "organic" not in result.detected

    def test_bio_does_not_match_probiotic(self, engine):
        result = engine.detect(
            description="Contains Pro-Biofilm complex for scalp care"
        )
        assert "organic" not in result.detected

    def test_organic_does_not_match_organically(self, engine):
        """'organic' keyword should not match 'organically' as standalone."""
        result = engine.detect(description="This is organically derived")
        assert "organic" not in result.detected

    def test_natural_does_not_match_naturally(self, engine):
        """'natural' keyword should not match 'naturally'."""
        result = engine.detect(description="Hair that moves naturally")
        assert "natural" not in result.detected

    def test_natural_matches_as_standalone_word(self, engine):
        """'natural' should match when it's a standalone word."""
        result = engine.detect(description="A product with natural ingredients")
        assert "natural" in result.detected

    def test_vegan_does_not_match_in_url(self, engine):
        """'vegan' should not match inside 'veganuary' or similar."""
        result = engine.detect(description="Join veganuary this year")
        assert "vegan" not in result.detected

    def test_vegan_matches_standalone(self, engine):
        result = engine.detect(description="This is a vegan product")
        assert "vegan" in result.detected

    def test_sulfate_free_is_multi_word_boundary(self, engine):
        """Multi-word 'sulfate free' with word boundaries."""
        result = engine.detect(description="Our sulfate free formula")
        assert "sulfate_free" in result.detected

    def test_sem_sulfato_with_accented_context(self, engine):
        """Portuguese keyword with word boundaries."""
        result = engine.detect(description="Fórmula sem sulfato para cabelos cacheados")
        assert "sulfate_free" in result.detected

    def test_no_partial_word_match(self, engine):
        """Ensure keywords don't match partial words."""
        result = engine.detect(description="The organics line features supernatural cleaning")
        # "organics" should not match "organic" (no boundary after "organic" before "s")
        # "supernatural" should not match "natural" (no boundary before "natural")
        assert "organic" not in result.detected
        assert "natural" not in result.detected


# ---------------------------------------------------------------------------
# TestImageElementScanning
# ---------------------------------------------------------------------------

class TestImageElementScanning:
    def test_detects_seal_from_image_alt(self, engine):
        result = engine.detect(image_texts=["selo cruelty free certificado"])
        assert "cruelty_free" in result.detected
        assert "html_img_element" in result.sources

    def test_detects_seal_from_image_filename(self, engine):
        result = engine.detect(image_texts=["selo vegan certificado peta"])
        assert "vegan" in result.detected

    def test_no_false_positive_from_unrelated_image(self, engine):
        result = engine.detect(image_texts=["product hero banner", "shampoo 300ml"])
        assert result.detected == []

    def test_image_does_not_duplicate_text_detection(self, engine):
        """If seal already detected via text, image should not add duplicate."""
        result = engine.detect(
            description="This is a vegan product",
            image_texts=["selo vegan"],
        )
        assert result.detected.count("vegan") == 1

    def test_image_evidence_method(self, engine):
        result = engine.detect(image_texts=["selo cruelty free"])
        entries = result.evidence_entries()
        assert len(entries) == 1
        assert entries[0]["extraction_method"] == "html_img_element"
        assert entries[0]["evidence_locator"] == "img_alt_title_filename"


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

    def test_infers_sulfate_free_from_inci(self, engine):
        """When no harsh sulfates in INCI, sulfate_free should be inferred."""
        result = engine.detect(
            inci_ingredients=["Aqua", "Cocamidopropyl Betaine", "Glycerin"]
        )
        assert "sulfate_free" in result.inferred

    def test_does_not_infer_sulfate_free_with_sulfate(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Sodium Lauryl Sulfate", "Glycerin"]
        )
        assert "sulfate_free" not in result.inferred

    def test_infers_paraben_free_from_inci(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol"]
        )
        assert "paraben_free" in result.inferred

    def test_does_not_infer_paraben_free_with_paraben(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Methylparaben", "Propylparaben"]
        )
        assert "paraben_free" not in result.inferred

    def test_infers_petrolatum_free_from_inci(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol"]
        )
        assert "petrolatum_free" in result.inferred

    def test_does_not_infer_petrolatum_free_with_mineral_oil(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Mineral Oil", "Glycerin"]
        )
        assert "petrolatum_free" not in result.inferred

    def test_infers_dye_free_from_inci(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "Cetearyl Alcohol"]
        )
        assert "dye_free" in result.inferred

    def test_does_not_infer_dye_free_with_ci_number(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "Glycerin", "CI 19140", "CI 77891"]
        )
        assert "dye_free" not in result.inferred

    def test_does_not_infer_dye_free_with_fd_c(self, engine):
        result = engine.detect(
            inci_ingredients=["Aqua", "FD&C Yellow No. 5"]
        )
        assert "dye_free" not in result.inferred


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


# ---------------------------------------------------------------------------
# TestExtractSealImageTexts
# ---------------------------------------------------------------------------

class TestExtractSealImageTexts:
    def test_extracts_alt_text(self):
        html = '<html><body><img src="/img/selo.png" alt="Cruelty Free Certified"></body></html>'
        texts = extract_seal_image_texts(html)
        assert "Cruelty Free Certified" in texts

    def test_extracts_title_text(self):
        html = '<html><body><img src="/img/selo.png" title="Vegan Product"></body></html>'
        texts = extract_seal_image_texts(html)
        assert "Vegan Product" in texts

    def test_extracts_filename(self):
        html = '<html><body><img src="/images/selo-sulfate-free.png"></body></html>'
        texts = extract_seal_image_texts(html)
        assert any("selo sulfate free" in t.lower() for t in texts)

    def test_deduplicates(self):
        html = '''<html><body>
            <img src="/a.png" alt="Vegan">
            <img src="/b.png" alt="Vegan">
        </body></html>'''
        texts = extract_seal_image_texts(html)
        vegan_count = sum(1 for t in texts if t.lower() == "vegan")
        assert vegan_count == 1

    def test_skips_long_alt_texts(self):
        long_text = "A" * 250
        html = f'<html><body><img src="/a.png" alt="{long_text}"></body></html>'
        texts = extract_seal_image_texts(html)
        assert long_text not in texts


# ---------------------------------------------------------------------------
# TestSanitizeText (extraction module)
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def test_decodes_html_entities(self):
        from src.extraction.deterministic import sanitize_text
        assert sanitize_text("Shampoo &amp; Condicionador") == "Shampoo & Condicionador"
        assert sanitize_text("Composi&ccedil;&atilde;o") == "Composição"

    def test_strips_html_tags(self):
        from src.extraction.deterministic import sanitize_text
        assert sanitize_text("<p>Hello <b>world</b></p>") == "Hello world"
        assert sanitize_text('<img src="x" alt="y"> text') == "text"

    def test_normalizes_whitespace(self):
        from src.extraction.deterministic import sanitize_text
        assert sanitize_text("Hello   world\n\nnew line") == "Hello world new line"

    def test_returns_none_for_empty(self):
        from src.extraction.deterministic import sanitize_text
        assert sanitize_text("") is None
        assert sanitize_text(None) is None

    def test_handles_mixed_entities_and_tags(self):
        from src.extraction.deterministic import sanitize_text
        result = sanitize_text("<p>Sem sulfato &amp; sem parabenos</p>")
        assert result == "Sem sulfato & sem parabenos"
