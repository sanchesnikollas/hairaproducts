# Smart Labels Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a post-processing label engine that detects product quality seals (sulfate_free, vegan, etc.) via text keyword matching and INCI ingredient inference, starting with brand Amend.

**Architecture:** CLI command `haira labels` loads YAML reference lists from `config/labels/`, runs a LabelEngine against stored products, and writes results as a JSON column on `products` + evidence rows in `product_evidence`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, Click, PyYAML, pytest

---

### Task 1: Create YAML Reference Lists

**Files:**
- Create: `config/labels/seals.yaml`
- Create: `config/labels/silicones.yaml`
- Create: `config/labels/surfactants.yaml`

**Step 1: Create config/labels directory**

Run: `mkdir -p config/labels`

**Step 2: Create seals.yaml with multilingual keywords**

```yaml
# config/labels/seals.yaml
# Seal definitions with multilingual keyword matching.
# Keywords are case-insensitive. Match in: description, product_name, benefits_claims, usage_instructions.

seals:
  sulfate_free:
    keywords:
      - "sem sulfato"
      - "sem sulfatos"
      - "livre de sulfato"
      - "livre de sulfatos"
      - "sulfate free"
      - "sulfate-free"
      - "no sulfate"
      - "no sulfates"
      - "sin sulfato"
      - "sin sulfatos"

  paraben_free:
    keywords:
      - "sem parabeno"
      - "sem parabenos"
      - "livre de parabeno"
      - "livre de parabenos"
      - "paraben free"
      - "paraben-free"
      - "no paraben"
      - "no parabens"
      - "sin parabenos"

  silicone_free:
    keywords:
      - "sem silicone"
      - "sem silicones"
      - "livre de silicone"
      - "livre de silicones"
      - "silicone free"
      - "silicone-free"
      - "no silicone"
      - "no silicones"
      - "sin siliconas"

  fragrance_free:
    keywords:
      - "sem fragrância"
      - "sem fragância"
      - "sem perfume"
      - "livre de fragrância"
      - "fragrance free"
      - "fragrance-free"
      - "no fragrance"
      - "unscented"
      - "sem cheiro"

  vegan:
    keywords:
      - "vegano"
      - "vegana"
      - "produto vegano"
      - "produto vegana"
      - "vegan"
      - "100% vegano"
      - "100% vegan"

  cruelty_free:
    keywords:
      - "cruelty free"
      - "cruelty-free"
      - "não testado em animais"
      - "nao testado em animais"
      - "livre de crueldade"
      - "livre de crueldade animal"
      - "not tested on animals"

  organic:
    keywords:
      - "orgânico"
      - "orgânica"
      - "organic"
      - "100% orgânico"
      - "certificado orgânico"
      - "certified organic"

  natural:
    keywords:
      - "natural"
      - "100% natural"
      - "ingredientes naturais"
      - "natural ingredients"
      - "produto natural"

  hypoallergenic:
    keywords:
      - "hipoalergênico"
      - "hipoalergênica"
      - "hipoalergenico"
      - "hipoalergenica"
      - "hypoallergenic"
      - "hypo-allergenic"

  dermatologically_tested:
    keywords:
      - "dermatologicamente testado"
      - "dermatologicamente testada"
      - "testado dermatologicamente"
      - "testada dermatologicamente"
      - "dermatologically tested"
      - "aprovado por dermatologistas"

  ophthalmologically_tested:
    keywords:
      - "oftalmologicamente testado"
      - "oftalmologicamente testada"
      - "testado oftalmologicamente"
      - "ophthalmologically tested"

  uv_protection:
    keywords:
      - "proteção uv"
      - "protecao uv"
      - "filtro uv"
      - "uv protection"
      - "uv filter"
      - "proteção solar"
      - "protecao solar"

  thermal_protection:
    keywords:
      - "proteção térmica"
      - "protecao termica"
      - "protetor térmico"
      - "protetor termico"
      - "thermal protection"
      - "heat protection"
      - "heat protectant"

  low_poo:
    keywords:
      - "low poo"
      - "low-poo"
      - "lowpoo"

  no_poo:
    keywords:
      - "no poo"
      - "no-poo"
      - "nopoo"
```

**Step 3: Create silicones.yaml with prohibited ingredients**

```yaml
# config/labels/silicones.yaml
# Silicones commonly found in hair products.
# If NONE of these are present in INCI → infer silicone_free.
# Source: cosmetic chemistry references.

silicones:
  - dimethicone
  - dimethiconol
  - amodimethicone
  - cyclomethicone
  - cyclopentasiloxane
  - cyclohexasiloxane
  - cyclotetrasiloxane
  - trimethylsilylamodimethicone
  - phenyl trimethicone
  - cetyl dimethicone
  - cetearyl methicone
  - stearyl dimethicone
  - bis-aminopropyl dimethicone
  - aminopropyl dimethicone
  - peg-12 dimethicone
  - peg-8 dimethicone
  - divinyldimethicone/dimethicone copolymer
  - dimethicone crosspolymer
  - dimethicone copolyol
  - polysilicone-15
  - trimethicone
  - methicone
  - simethicone
  - trisiloxane
  - silicone quaternium-8
  - silicone quaternium-16
  - silicone quaternium-18
  - vinyl dimethicone
  - stearoxy dimethicone
  - behenoxy dimethicone
```

**Step 4: Create surfactants.yaml with prohibited ingredients for low/no poo**

```yaml
# config/labels/surfactants.yaml
# Harsh surfactants prohibited under low_poo / no_poo methodology.
# If NONE of the low_poo list are in INCI + INCI verified → infer low_poo.
# If NONE of the no_poo list are in INCI + INCI verified → infer no_poo.

# Low poo: no harsh sulfates (gentle surfactants OK)
low_poo_prohibited:
  - sodium lauryl sulfate
  - sodium laureth sulfate
  - ammonium lauryl sulfate
  - ammonium laureth sulfate
  - sodium myreth sulfate
  - sodium coco sulfate
  - sodium c14-16 olefin sulfonate
  - sodium cocoyl isethionate  # debated, but commonly excluded in strict low poo
  - tea lauryl sulfate
  - tea laureth sulfate
  - mea lauryl sulfate
  - mea laureth sulfate

# No poo: no sulfates AND no silicones (requires silicone_free too)
# Uses same list as low_poo_prohibited + silicones list
no_poo_prohibited:
  - sodium lauryl sulfate
  - sodium laureth sulfate
  - ammonium lauryl sulfate
  - ammonium laureth sulfate
  - sodium myreth sulfate
  - sodium coco sulfate
  - sodium c14-16 olefin sulfonate
  - sodium cocoyl isethionate
  - tea lauryl sulfate
  - tea laureth sulfate
  - mea lauryl sulfate
  - mea laureth sulfate
```

**Step 5: Commit**

```bash
git add config/labels/seals.yaml config/labels/silicones.yaml config/labels/surfactants.yaml
git commit -m "feat: add YAML reference lists for smart label detection

Seal keywords (multilingual), silicone list (~30), surfactant lists (low/no poo)."
```

---

### Task 2: Create LabelEngine with Tests

**Files:**
- Create: `src/core/label_engine.py`
- Create: `tests/core/test_label_engine.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_label_engine.py
import pytest
from src.core.label_engine import (
    LabelEngine,
    LabelResult,
    SealName,
    load_seal_keywords,
    load_prohibited_list,
)


@pytest.fixture
def engine(tmp_path):
    """Create a LabelEngine with minimal test config."""
    seals_yaml = tmp_path / "seals.yaml"
    seals_yaml.write_text("""
seals:
  sulfate_free:
    keywords:
      - "sem sulfato"
      - "sulfate free"
  vegan:
    keywords:
      - "vegano"
      - "vegan"
  cruelty_free:
    keywords:
      - "cruelty free"
      - "cruelty-free"
  silicone_free:
    keywords:
      - "sem silicone"
      - "silicone free"
  low_poo:
    keywords:
      - "low poo"
  no_poo:
    keywords:
      - "no poo"
""")
    silicones_yaml = tmp_path / "silicones.yaml"
    silicones_yaml.write_text("""
silicones:
  - dimethicone
  - amodimethicone
  - cyclopentasiloxane
""")
    surfactants_yaml = tmp_path / "surfactants.yaml"
    surfactants_yaml.write_text("""
low_poo_prohibited:
  - sodium lauryl sulfate
  - sodium laureth sulfate
no_poo_prohibited:
  - sodium lauryl sulfate
  - sodium laureth sulfate
""")
    return LabelEngine(
        seals_path=str(seals_yaml),
        silicones_path=str(silicones_yaml),
        surfactants_path=str(surfactants_yaml),
    )


class TestLoadConfig:
    def test_load_seal_keywords(self, tmp_path):
        p = tmp_path / "seals.yaml"
        p.write_text("""
seals:
  vegan:
    keywords:
      - "vegano"
      - "vegan"
""")
        result = load_seal_keywords(str(p))
        assert "vegan" in result
        assert "vegano" in result["vegan"]
        assert "vegan" in result["vegan"]

    def test_load_prohibited_list(self, tmp_path):
        p = tmp_path / "silicones.yaml"
        p.write_text("""
silicones:
  - dimethicone
  - Amodimethicone
""")
        result = load_prohibited_list(str(p), "silicones")
        assert "dimethicone" in result
        assert "amodimethicone" in result  # lowercased


class TestKeywordDetection:
    def test_detects_sulfate_free_in_description(self, engine):
        result = engine.detect(
            description="Shampoo sem sulfato para cabelos cacheados",
            product_name="Shampoo Cachos",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert "sulfate_free" in result.detected
        assert "official_text" in result.sources

    def test_detects_vegan_in_product_name(self, engine):
        result = engine.detect(
            description=None,
            product_name="Condicionador Vegano 300ml",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert "vegan" in result.detected

    def test_detects_in_benefits_claims(self, engine):
        result = engine.detect(
            description=None,
            product_name="Shampoo Liso",
            benefits_claims=["Hidratação intensa", "Cruelty free"],
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert "cruelty_free" in result.detected

    def test_no_false_positives(self, engine):
        result = engine.detect(
            description="Shampoo hidratante para cabelos secos",
            product_name="Shampoo Hidra",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert result.detected == []
        assert result.inferred == []

    def test_case_insensitive(self, engine):
        result = engine.detect(
            description="Produto SULFATE FREE para todos os tipos",
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert "sulfate_free" in result.detected


class TestINCIInference:
    def test_infers_silicone_free(self, engine):
        result = engine.detect(
            description=None,
            product_name="Shampoo Cachos",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Sodium Chloride", "Glycerin", "Parfum", "Citric Acid"],
        )
        assert "silicone_free" in result.inferred
        assert "inci_analysis" in result.sources

    def test_does_not_infer_silicone_free_when_silicone_present(self, engine):
        result = engine.detect(
            description=None,
            product_name="Shampoo Liso",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Dimethicone", "Glycerin", "Parfum", "Citric Acid"],
        )
        assert "silicone_free" not in result.inferred

    def test_infers_low_poo(self, engine):
        result = engine.detect(
            description=None,
            product_name="Shampoo Suave",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Cocamidopropyl Betaine", "Glycerin", "Parfum", "Citric Acid"],
        )
        assert "low_poo" in result.inferred

    def test_does_not_infer_low_poo_with_harsh_sulfate(self, engine):
        result = engine.detect(
            description=None,
            product_name="Shampoo Forte",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Glycerin", "Parfum", "Citric Acid"],
        )
        assert "low_poo" not in result.inferred

    def test_infers_no_poo_when_no_sulfates_no_silicones(self, engine):
        result = engine.detect(
            description=None,
            product_name="Co-wash Natural",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Cetearyl Alcohol", "Glycerin", "Parfum", "Citric Acid"],
        )
        assert "no_poo" in result.inferred

    def test_does_not_infer_no_poo_with_silicone(self, engine):
        result = engine.detect(
            description=None,
            product_name="Co-wash",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Cetearyl Alcohol", "Dimethicone", "Parfum", "Citric Acid"],
        )
        assert "no_poo" not in result.inferred

    def test_no_inference_without_inci(self, engine):
        result = engine.detect(
            description="Shampoo top",
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert result.inferred == []


class TestConfidenceScoring:
    def test_no_seals_zero_confidence(self, engine):
        result = engine.detect(
            description="Shampoo hidratante",
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert result.confidence == 0.0

    def test_only_inferred_half_confidence(self, engine):
        result = engine.detect(
            description=None,
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Glycerin", "Parfum", "Citric Acid", "Sodium Chloride"],
        )
        # Has inferred seals but no detected seals
        assert result.confidence == 0.5

    def test_only_detected_high_confidence(self, engine):
        result = engine.detect(
            description="Shampoo vegano para cabelos",
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=None,
        )
        assert result.confidence == 0.8

    def test_detected_and_inferred_highest_confidence(self, engine):
        result = engine.detect(
            description="Shampoo sem silicone para cabelos",
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Glycerin", "Parfum", "Citric Acid", "Sodium Chloride"],
        )
        # silicone_free is both detected (text) and inferred (INCI)
        assert result.confidence == 0.9


class TestLabelResult:
    def test_to_dict(self, engine):
        result = engine.detect(
            description="Shampoo vegano sem sulfato",
            product_name="Shampoo Vegano",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Glycerin", "Parfum", "Citric Acid", "Sodium Chloride"],
        )
        d = result.to_dict()
        assert isinstance(d["detected"], list)
        assert isinstance(d["inferred"], list)
        assert isinstance(d["confidence"], float)
        assert isinstance(d["sources"], list)
        assert d["manually_verified"] is False
        assert d["manually_overridden"] is False

    def test_evidence_entries(self, engine):
        result = engine.detect(
            description="Shampoo sem sulfato",
            product_name="Shampoo",
            benefits_claims=None,
            usage_instructions=None,
            inci_ingredients=["Aqua", "Glycerin", "Parfum", "Citric Acid", "Sodium Chloride"],
        )
        entries = result.evidence_entries()
        assert len(entries) > 0
        for entry in entries:
            assert entry["field_name"].startswith("label:")
            assert entry["extraction_method"] in ("text_keyword", "inci_inference")
            assert entry["raw_source_text"] != ""
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/core/test_label_engine.py -v`
Expected: FAIL — ImportError (module does not exist)

**Step 3: Write the LabelEngine implementation**

```python
# src/core/label_engine.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


def load_seal_keywords(path: str) -> dict[str, list[str]]:
    """Load seal name → keyword list mapping from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    result: dict[str, list[str]] = {}
    for seal_name, config in data.get("seals", {}).items():
        result[seal_name] = [kw.lower() for kw in config.get("keywords", [])]
    return result


def load_prohibited_list(path: str, key: str) -> list[str]:
    """Load a flat list of prohibited ingredients from YAML, lowercased."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return [item.lower() for item in data.get(key, [])]


# Valid seal names
SealName = str  # One of the keys in seals.yaml


@dataclass
class LabelEvidence:
    field_name: str           # "label:sulfate_free"
    extraction_method: str    # "text_keyword" or "inci_inference"
    raw_source_text: str      # matched text or analysis summary
    evidence_locator: str     # field where evidence was found


@dataclass
class LabelResult:
    detected: list[str] = field(default_factory=list)
    inferred: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    manually_verified: bool = False
    manually_overridden: bool = False
    _evidence: list[LabelEvidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "detected": sorted(self.detected),
            "inferred": sorted(self.inferred),
            "confidence": self.confidence,
            "sources": sorted(set(self.sources)),
            "manually_verified": self.manually_verified,
            "manually_overridden": self.manually_overridden,
        }

    def evidence_entries(self) -> list[dict]:
        return [
            {
                "field_name": ev.field_name,
                "extraction_method": ev.extraction_method,
                "raw_source_text": ev.raw_source_text,
                "evidence_locator": ev.evidence_locator,
            }
            for ev in self._evidence
        ]


class LabelEngine:
    def __init__(
        self,
        seals_path: str | None = None,
        silicones_path: str | None = None,
        surfactants_path: str | None = None,
    ):
        base = Path("config/labels")
        self._seal_keywords = load_seal_keywords(seals_path or str(base / "seals.yaml"))
        self._silicones = load_prohibited_list(
            silicones_path or str(base / "silicones.yaml"), "silicones"
        )
        self._low_poo_prohibited = load_prohibited_list(
            surfactants_path or str(base / "surfactants.yaml"), "low_poo_prohibited"
        )
        self._no_poo_prohibited = load_prohibited_list(
            surfactants_path or str(base / "surfactants.yaml"), "no_poo_prohibited"
        )

    def detect(
        self,
        description: str | None,
        product_name: str | None,
        benefits_claims: list[str] | None,
        usage_instructions: str | None,
        inci_ingredients: list[str] | None,
    ) -> LabelResult:
        result = LabelResult()

        # --- Method 1: Keyword detection from text ---
        self._detect_keywords(result, description, product_name, benefits_claims, usage_instructions)

        # --- Method 2: INCI inference ---
        if inci_ingredients:
            self._infer_from_inci(result, inci_ingredients)

        # --- Confidence scoring ---
        result.confidence = self._score_confidence(result)

        return result

    def _detect_keywords(
        self,
        result: LabelResult,
        description: str | None,
        product_name: str | None,
        benefits_claims: list[str] | None,
        usage_instructions: str | None,
    ) -> None:
        """Scan text fields for seal keywords."""
        text_fields: list[tuple[str, str]] = []
        if description:
            text_fields.append(("description", description))
        if product_name:
            text_fields.append(("product_name", product_name))
        if benefits_claims:
            text_fields.append(("benefits_claims", " ".join(benefits_claims)))
        if usage_instructions:
            text_fields.append(("usage_instructions", usage_instructions))

        for seal_name, keywords in self._seal_keywords.items():
            for field_name, text in text_fields:
                text_lower = text.lower()
                for keyword in keywords:
                    if keyword in text_lower:
                        if seal_name not in result.detected:
                            result.detected.append(seal_name)
                            result.sources.append("official_text")
                            result._evidence.append(LabelEvidence(
                                field_name=f"label:{seal_name}",
                                extraction_method="text_keyword",
                                raw_source_text=f'Keyword "{keyword}" found in {field_name}',
                                evidence_locator=field_name,
                            ))
                        break  # stop checking other keywords for this seal+field
                else:
                    continue
                break  # stop checking other fields for this seal

    def _infer_from_inci(self, result: LabelResult, inci: list[str]) -> None:
        """Infer seals by analyzing INCI ingredient list."""
        inci_lower = [i.lower().strip() for i in inci]

        # Silicone free: no silicones in INCI
        has_silicone = any(
            silicone in ingredient
            for ingredient in inci_lower
            for silicone in self._silicones
        )
        if not has_silicone:
            if "silicone_free" not in result.detected:
                result.inferred.append("silicone_free")
                result.sources.append("inci_analysis")
                result._evidence.append(LabelEvidence(
                    field_name="label:silicone_free",
                    extraction_method="inci_inference",
                    raw_source_text=f"No silicones found in INCI ({len(self._silicones)} checked)",
                    evidence_locator="inci_ingredients",
                ))

        # Low poo: no harsh sulfates in INCI
        has_harsh_sulfate = any(
            surfactant in ingredient
            for ingredient in inci_lower
            for surfactant in self._low_poo_prohibited
        )
        if not has_harsh_sulfate:
            if "low_poo" not in result.detected:
                result.inferred.append("low_poo")
                result.sources.append("inci_analysis")
                result._evidence.append(LabelEvidence(
                    field_name="label:low_poo",
                    extraction_method="inci_inference",
                    raw_source_text=f"No harsh sulfates found in INCI ({len(self._low_poo_prohibited)} checked)",
                    evidence_locator="inci_ingredients",
                ))

        # No poo: no harsh sulfates AND no silicones
        if not has_harsh_sulfate and not has_silicone:
            if "no_poo" not in result.detected:
                result.inferred.append("no_poo")
                result.sources.append("inci_analysis")
                result._evidence.append(LabelEvidence(
                    field_name="label:no_poo",
                    extraction_method="inci_inference",
                    raw_source_text=f"No harsh sulfates or silicones in INCI",
                    evidence_locator="inci_ingredients",
                ))

    def _score_confidence(self, result: LabelResult) -> float:
        """Calculate confidence score based on detection sources."""
        has_detected = len(result.detected) > 0
        has_inferred = len(result.inferred) > 0

        if not has_detected and not has_inferred:
            return 0.0

        # Check if any seal appears in both detected and inferred
        overlap = set(result.detected) & set(result.inferred)
        if overlap:
            return 0.9
        if has_detected:
            return 0.8
        # only inferred
        return 0.5
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/core/test_label_engine.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/core/label_engine.py tests/core/test_label_engine.py
git commit -m "feat: add LabelEngine with keyword detection and INCI inference

Detects 15 seal types via text keywords and infers silicone_free/low_poo/no_poo from INCI."
```

---

### Task 3: Alembic Migration for product_labels Column

**Files:**
- Modify: `src/storage/orm_models.py:25-55` (add column to ProductORM)
- Create: new migration file via alembic

**Step 1: Add product_labels column to ORM model**

In `src/storage/orm_models.py`, add after the `variants` column (line 47):

```python
    product_labels = Column(JSON, nullable=True, default=None)
```

**Step 2: Generate Alembic migration**

Run: `cd /Users/nikollasanches/Documents/hairaproducts && alembic revision --autogenerate -m "add product_labels column"`
Expected: New migration file created in `src/storage/migrations/versions/`

**Step 3: Run the migration**

Run: `alembic upgrade head`
Expected: Migration applied successfully

**Step 4: Verify column exists**

Run: `python -c "from src.storage.database import get_engine; e = get_engine(); print([c.name for c in e.execute(__import__('sqlalchemy').text('PRAGMA table_info(products)')).fetchall()])"`
Expected: `product_labels` in the list

**Step 5: Commit**

```bash
git add src/storage/orm_models.py src/storage/migrations/versions/
git commit -m "feat: add product_labels JSON column to products table

Alembic migration for storing smart label detection results."
```

---

### Task 4: Add Repository Methods for Labels

**Files:**
- Modify: `src/storage/repository.py` (add methods)
- Modify: `tests/storage/test_repository.py` (add tests)

**Step 1: Write failing tests**

Add to `tests/storage/test_repository.py`:

```python
class TestLabelMethods:
    def test_update_product_labels(self, session):
        """Test saving product_labels JSON to a product."""
        from src.storage.orm_models import ProductORM
        from src.storage.repository import ProductRepository

        # Create a product first
        product = ProductORM(
            brand_slug="amend",
            product_name="Shampoo Teste",
            product_url="https://amend.com/shampoo-teste",
            verification_status="verified_inci",
        )
        session.add(product)
        session.flush()

        repo = ProductRepository(session)
        labels = {
            "detected": ["sulfate_free", "vegan"],
            "inferred": ["silicone_free"],
            "confidence": 0.9,
            "sources": ["official_text", "inci_analysis"],
            "manually_verified": False,
            "manually_overridden": False,
        }
        repo.update_product_labels(product.id, labels)
        session.flush()

        fetched = repo.get_product_by_id(product.id)
        assert fetched.product_labels is not None
        assert "sulfate_free" in fetched.product_labels["detected"]

    def test_get_products_by_brand(self, session):
        """Test fetching all products for a brand."""
        from src.storage.orm_models import ProductORM
        from src.storage.repository import ProductRepository

        for i in range(3):
            session.add(ProductORM(
                brand_slug="amend",
                product_name=f"Product {i}",
                product_url=f"https://amend.com/product-{i}",
                verification_status="verified_inci",
            ))
        session.flush()

        repo = ProductRepository(session)
        products = repo.get_products(brand_slug="amend", limit=100)
        assert len(products) == 3
```

Note: Check existing test file for the `session` fixture pattern. If it uses an in-memory SQLite fixture, follow the same pattern. If not, add:

```python
@pytest.fixture
def session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SASession
    from src.storage.orm_models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with SASession(engine) as s:
        yield s
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/storage/test_repository.py::TestLabelMethods -v`
Expected: FAIL — `update_product_labels` does not exist

**Step 3: Add update_product_labels method to ProductRepository**

In `src/storage/repository.py`, add this method to `ProductRepository`:

```python
    def update_product_labels(self, product_id: str, labels: dict) -> None:
        """Update the product_labels JSON for a product."""
        product = self.get_product_by_id(product_id)
        if product:
            product.product_labels = labels
            product.updated_at = datetime.now(timezone.utc)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/storage/test_repository.py::TestLabelMethods -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/storage/repository.py tests/storage/test_repository.py
git commit -m "feat: add update_product_labels repository method"
```

---

### Task 5: Create CLI Command

**Files:**
- Modify: `src/cli/main.py` (add `labels` command)

**Step 1: Write the `labels` CLI command**

Add to `src/cli/main.py` after the `report` command:

```python
@cli.command()
@click.option("--brand", required=True, help="Brand slug")
@click.option("--limit", type=int, default=0, help="Max products to process (0 = all)")
@click.option("--dry-run", is_flag=True, help="Show results without saving to database")
def labels(brand: str, limit: int, dry_run: bool):
    """Detect product quality seals (labels) for a brand's products."""
    from src.core.label_engine import LabelEngine, LabelResult
    from src.extraction.evidence_tracker import create_evidence
    from src.core.models import ExtractionMethod
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductEvidenceORM
    from src.storage.repository import ProductRepository
    from sqlalchemy.orm import Session as SASession

    # Initialize
    engine_db = get_engine()
    Base.metadata.create_all(engine_db)
    label_engine = LabelEngine()

    with SASession(engine_db) as session:
        repo = ProductRepository(session)
        products = repo.get_products(brand_slug=brand, limit=limit if limit > 0 else 10000)

        if not products:
            click.echo(f"No products found for '{brand}'. Run 'haira scrape --brand {brand}' first.")
            return

        click.echo(f"Processing {len(products)} products for {brand}...")
        if dry_run:
            click.echo("(DRY RUN — no changes will be saved)\n")

        # Stats
        total = len(products)
        with_detected = 0
        with_inferred = 0
        seal_counts: dict[str, int] = {}

        for product in products:
            result = label_engine.detect(
                description=product.description,
                product_name=product.product_name,
                benefits_claims=product.benefits_claims,
                usage_instructions=product.usage_instructions,
                inci_ingredients=product.inci_ingredients,
            )

            all_seals = result.detected + result.inferred
            if result.detected:
                with_detected += 1
            if result.inferred:
                with_inferred += 1
            for seal in all_seals:
                seal_counts[seal] = seal_counts.get(seal, 0) + 1

            if dry_run:
                if all_seals:
                    click.echo(f"  {product.product_name[:60]}")
                    if result.detected:
                        click.echo(f"    detected: {', '.join(result.detected)}")
                    if result.inferred:
                        click.echo(f"    inferred: {', '.join(result.inferred)}")
                    click.echo(f"    confidence: {result.confidence}")
            else:
                # Save labels JSON
                repo.update_product_labels(product.id, result.to_dict())

                # Save evidence rows
                for ev in result.evidence_entries():
                    evidence_orm = ProductEvidenceORM(
                        product_id=product.id,
                        field_name=ev["field_name"],
                        source_url=product.product_url,
                        evidence_locator=ev["evidence_locator"],
                        raw_source_text=ev["raw_source_text"],
                        extraction_method=ev["extraction_method"],
                    )
                    session.add(evidence_orm)

        if not dry_run:
            session.commit()

        # Report
        click.echo(f"\n{'='*60}")
        click.echo(f"Label Detection Report — {brand}")
        click.echo(f"{'='*60}")
        click.echo(f"Total products:       {total}")
        click.echo(f"With detected seals:  {with_detected} ({with_detected/total:.0%})")
        click.echo(f"With inferred seals:  {with_inferred} ({with_inferred/total:.0%})")
        click.echo(f"\nSeal distribution:")
        for seal, count in sorted(seal_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {seal:<30} {count:>4} ({count/total:.0%})")

        if not dry_run:
            click.echo(f"\nResults saved to database.")
        else:
            click.echo(f"\n(DRY RUN — nothing was saved)")
```

**Step 2: Test CLI manually**

Run: `python -m src.cli.main labels --brand amend --dry-run --limit 10`
Expected: Output showing detected/inferred seals for up to 10 Amend products

**Step 3: Commit**

```bash
git add src/cli/main.py
git commit -m "feat: add 'haira labels' CLI command for seal detection

Supports --brand, --limit, --dry-run flags. Generates distribution report."
```

---

### Task 6: Run Full Amend Pipeline and Generate Report

**Step 1: Dry run on all Amend products**

Run: `haira labels --brand amend --dry-run`
Expected: Full list of Amend products with detected and inferred seals

**Step 2: Review output for accuracy**

Manually check 5-10 products against the Amend website.
Look for:
- False positives (seal detected but product doesn't claim it)
- False negatives (product claims a seal but we missed it)
- INCI inferences that seem wrong

**Step 3: Adjust YAML configs if needed**

If keywords are missing or too broad, edit `config/labels/seals.yaml`.
If silicone list needs entries, edit `config/labels/silicones.yaml`.

**Step 4: Run for real**

Run: `haira labels --brand amend`
Expected: Labels saved to database, report printed

**Step 5: Verify in database**

Run: `python -c "
from src.storage.database import get_engine
from sqlalchemy.orm import Session
from src.storage.orm_models import ProductORM
engine = get_engine()
with Session(engine) as s:
    products = s.query(ProductORM).filter_by(brand_slug='amend').all()
    labeled = [p for p in products if p.product_labels]
    print(f'Total: {len(products)}, Labeled: {len(labeled)}')
    if labeled:
        import json
        print(json.dumps(labeled[0].product_labels, indent=2))
"`
Expected: Shows labeled count and sample JSON

**Step 6: Commit final state**

```bash
git add config/labels/
git commit -m "feat: run Amend label detection pipeline — results verified"
```

---

### Summary of all files

| Action | File |
|--------|------|
| Create | `config/labels/seals.yaml` |
| Create | `config/labels/silicones.yaml` |
| Create | `config/labels/surfactants.yaml` |
| Create | `src/core/label_engine.py` |
| Create | `tests/core/test_label_engine.py` |
| Modify | `src/storage/orm_models.py` (add `product_labels` column) |
| Create | Alembic migration (auto-generated) |
| Modify | `src/storage/repository.py` (add `update_product_labels`) |
| Modify | `tests/storage/test_repository.py` (add label tests) |
| Modify | `src/cli/main.py` (add `labels` command) |
