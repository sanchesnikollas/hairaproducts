# HAIRA v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade hair product intelligence platform that extracts verified INCI data from ~700 brands with evidence-per-field and stop-the-line quality.

**Architecture:** Sequential CLI pipeline processing brands one at a time. SQLAlchemy ORM with SQLite (dev) / Postgres (prod). Deterministic extraction first (JSON-LD, CSS selectors), LLM fallback only when needed. Three-tier output: catalog_only, verified_inci, quarantined.

**Tech Stack:** Python 3.12+, SQLAlchemy + Alembic, Playwright, Anthropic SDK, FastAPI, Click CLI, pytest, React + TS + Tailwind + Vite

---

## Phase 1: Foundation

### Task 1: Project Scaffold + Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/registry/__init__.py`
- Create: `src/discovery/__init__.py`
- Create: `src/extraction/__init__.py`
- Create: `src/pipeline/__init__.py`
- Create: `src/storage/__init__.py`
- Create: `src/api/__init__.py`
- Create: `src/cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `tests/registry/__init__.py`
- Create: `tests/fixtures/`
- Create: `config/blueprints/.gitkeep`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `alembic.ini`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "haira"
version = "2.0.0"
description = "Hair Product Intelligence Platform"
requires-python = ">=3.12"
dependencies = [
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "openpyxl>=3.1",
    "pyyaml>=6.0",
    "click>=8.1",
    "playwright>=1.40",
    "anthropic>=0.40",
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "httpx>=0.27",
    "python-slugify>=8.0",
    "psycopg2-binary>=2.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
]

[project.scripts]
haira = "src.cli.main:cli"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**Step 2: Create .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-5-20250929
DATABASE_URL=sqlite:///haira.db
LOG_LEVEL=INFO
MAX_LLM_CALLS_PER_BRAND=50
MIN_INCI_CONFIDENCE=0.80
HEADLESS=true
REQUEST_DELAY_SECONDS=3
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
haira.db
*.egg-info/
dist/
.venv/
node_modules/
.pytest_cache/
```

**Step 4: Create all __init__.py files and directory structure**

All `__init__.py` files are empty. Create `config/blueprints/.gitkeep` as empty file.

**Step 5: Initialize venv and install**

Run: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

**Step 6: Verify**

Run: `python -c "import src; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add -A && git commit -m "feat: project scaffold with dependencies and directory structure"
```

---

### Task 2: Pydantic Domain Models

**Files:**
- Create: `src/core/models.py`
- Create: `tests/core/test_models.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_models.py
import pytest
from datetime import datetime, timezone
from src.core.models import (
    Brand,
    DiscoveredURL,
    ProductExtraction,
    Evidence,
    QAResult,
    VerificationStatus,
    GenderTarget,
    ExtractionMethod,
    QAStatus,
)


class TestBrand:
    def test_create_brand(self):
        brand = Brand(
            brand_name="Amend Cosméticos",
            brand_slug="amend-cosmeticos",
            official_url_root="https://www.amend.com.br",
        )
        assert brand.brand_slug == "amend-cosmeticos"
        assert brand.status == "active"
        assert brand.catalog_entrypoints == []

    def test_brand_defaults(self):
        brand = Brand(
            brand_name="Test",
            brand_slug="test",
            official_url_root="https://test.com",
        )
        assert brand.country is None
        assert brand.priority is None
        assert brand.notes is None


class TestDiscoveredURL:
    def test_create(self):
        url = DiscoveredURL(
            url="https://www.amend.com.br/produto/shampoo",
            source_type="category_crawl",
            hair_relevant=True,
            hair_relevance_reason="URL contains 'shampoo'",
        )
        assert url.hair_relevant is True

    def test_kit_detection(self):
        url = DiscoveredURL(
            url="https://example.com/kit-shampoo-condicionador",
            source_type="category_crawl",
            is_kit=True,
        )
        assert url.is_kit is True


class TestEvidence:
    def test_create(self):
        ev = Evidence(
            field_name="inci_ingredients",
            source_url="https://www.amend.com.br/produto/shampoo",
            evidence_locator=".product-ingredients",
            raw_source_text="Aqua, Sodium Laureth Sulfate",
            extraction_method=ExtractionMethod.HTML_SELECTOR,
        )
        assert ev.extraction_method == ExtractionMethod.HTML_SELECTOR


class TestProductExtraction:
    def test_catalog_only(self):
        product = ProductExtraction(
            brand_slug="amend",
            product_name="Shampoo Repair",
            product_url="https://www.amend.com.br/shampoo-repair",
            image_url_main="https://www.amend.com.br/img/shampoo.jpg",
            gender_target=GenderTarget.UNISEX,
            hair_relevance_reason="shampoo in product name",
        )
        assert product.inci_ingredients is None
        assert product.confidence == 0.0

    def test_verified_product(self):
        product = ProductExtraction(
            brand_slug="amend",
            product_name="Shampoo Repair",
            product_url="https://www.amend.com.br/shampoo-repair",
            image_url_main="https://www.amend.com.br/img/shampoo.jpg",
            gender_target=GenderTarget.UNISEX,
            hair_relevance_reason="shampoo in product name",
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
                              "Glycerin", "Parfum"],
            confidence=0.95,
        )
        assert len(product.inci_ingredients) == 5


class TestQAResult:
    def test_pass(self):
        result = QAResult(
            status=QAStatus.VERIFIED_INCI,
            passed=True,
            checks_passed=["name_valid", "url_valid", "inci_valid"],
            checks_failed=[],
        )
        assert result.passed is True

    def test_fail(self):
        result = QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=["name_valid"],
            checks_failed=["inci_too_short"],
            rejection_reason="INCI has only 2 terms",
        )
        assert result.passed is False
        assert result.rejection_reason is not None
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/core/test_models.py -v`
Expected: FAIL (imports not found)

**Step 3: Implement models**

```python
# src/core/models.py
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, enum.Enum):
    CATALOG_ONLY = "catalog_only"
    VERIFIED_INCI = "verified_inci"
    QUARANTINED = "quarantined"


class GenderTarget(str, enum.Enum):
    MEN = "men"
    WOMEN = "women"
    UNISEX = "unisex"
    KIDS = "kids"
    UNKNOWN = "unknown"


class ExtractionMethod(str, enum.Enum):
    JSONLD = "jsonld"
    HTML_SELECTOR = "html_selector"
    JS_DOM = "js_dom"
    LLM_GROUNDED = "llm_grounded"
    MANUAL = "manual"


class QAStatus(str, enum.Enum):
    CATALOG_ONLY = "catalog_only"
    VERIFIED_INCI = "verified_inci"
    QUARANTINED = "quarantined"


class Brand(BaseModel):
    brand_name: str
    brand_slug: str
    official_url_root: str
    country: Optional[str] = None
    priority: Optional[int] = None
    catalog_entrypoints: list[str] = Field(default_factory=list)
    status: str = "active"
    notes: Optional[str] = None


class DiscoveredURL(BaseModel):
    url: str
    source_type: str
    hair_relevant: bool = False
    hair_relevance_reason: Optional[str] = None
    is_kit: bool = False


class Evidence(BaseModel):
    field_name: str
    source_url: str
    evidence_locator: str
    raw_source_text: str
    extraction_method: ExtractionMethod
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductExtraction(BaseModel):
    brand_slug: str
    product_name: str
    product_url: str
    image_url_main: Optional[str] = None
    image_urls_gallery: list[str] = Field(default_factory=list)
    gender_target: GenderTarget = GenderTarget.UNKNOWN
    hair_relevance_reason: str = ""
    product_type_raw: Optional[str] = None
    product_type_normalized: Optional[str] = None
    inci_ingredients: Optional[list[str]] = None
    description: Optional[str] = None
    usage_instructions: Optional[str] = None
    benefits_claims: Optional[list[str]] = None
    size_volume: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    line_collection: Optional[str] = None
    variants: Optional[list[dict]] = None
    confidence: float = 0.0
    extraction_method: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QAResult(BaseModel):
    status: QAStatus
    passed: bool
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
```

**Step 4: Run tests**

Run: `pytest tests/core/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/models.py tests/core/test_models.py
git commit -m "feat: add Pydantic domain models (Brand, Product, Evidence, QA)"
```

---

### Task 3: Taxonomy Module (Hair Types + Gender Rules)

**Files:**
- Create: `src/core/taxonomy.py`
- Create: `tests/core/test_taxonomy.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/core/test_taxonomy.py -v`
Expected: FAIL

**Step 3: Implement taxonomy**

```python
# src/core/taxonomy.py
from __future__ import annotations

import re

HAIR_PRODUCT_TYPES: set[str] = {
    "shampoo",
    "conditioner",
    "mask",
    "treatment",
    "leave_in",
    "oil_serum",
    "tonic",
    "exfoliant",
    "scalp_treatment",
    "gel",
    "mousse",
    "spray",
    "pomade",
    "wax",
    "clay",
    "paste",
    "texturizer",
    "finisher",
    "ampule",
    "serum",
    "cream",
}

HAIR_KEYWORDS: list[str] = [
    "shampoo", "condicionador", "conditioner", "máscara capilar", "mascara capilar",
    "hair mask", "tratamento capilar", "leave-in", "leave in", "óleo capilar",
    "oil hair", "tônico capilar", "tonico capilar", "scalp", "couro cabeludo",
    "antiqueda", "anti-queda", "queda capilar", "crescimento capilar",
    "cabelo", "cabelos", "hair", "capilar", "fios",
    "gel fixador", "mousse", "spray fixador", "pomada", "cera capilar",
    "wax", "clay", "pasta modeladora", "texturizador", "finalizador",
    "ampola", "sérum capilar", "serum capilar", "creme para pentear",
    "creme de pentear", "alisamento", "progressiva", "reconstrução",
    "hidratação capilar", "nutrição capilar", "reparação",
]

EXCLUDE_KEYWORDS: list[str] = [
    "corpo", "corporal", "body", "facial", "face", "rosto",
    "maquiagem", "makeup", "perfume", "fragrance", "fragrância",
    "unhas", "nail", "acessório", "accessory",
    "protetor solar", "sunscreen", "desodorante", "deodorant",
    "sabonete líquido", "sabonete corporal",
    "hidratante corporal", "body lotion", "body cream",
    "batom", "lipstick", "rímel", "mascara para cílios",
]

KIT_PATTERNS: list[str] = [
    r"/kit[-_]", r"/combo[-_]", r"/bundle[-_]", r"/set[-_]",
    r"/kit/", r"/combo/", r"/bundle/",
]

MALE_TARGETING_KEYWORDS: list[str] = [
    "masculino", "masculina", "men", "for men", "man",
    "barber", "barbearia",
]

KIDS_KEYWORDS: list[str] = [
    "kids", "infantil", "criança", "children", "baby",
]

_TYPE_MAP: list[tuple[list[str], str]] = [
    (["shampoo"], "shampoo"),
    (["condicionador", "conditioner"], "conditioner"),
    (["máscara", "mascara", "mask"], "mask"),
    (["leave-in", "leave in"], "leave_in"),
    (["óleo", "oleo", "oil"], "oil_serum"),
    (["sérum", "serum"], "oil_serum"),
    (["tônico", "tonico", "tonic"], "tonic"),
    (["pomada", "pomade"], "pomade"),
    (["gel"], "gel"),
    (["mousse"], "mousse"),
    (["spray"], "spray"),
    (["cera", "wax"], "wax"),
    (["argila", "clay"], "clay"),
    (["pasta", "paste"], "paste"),
    (["creme de pentear", "creme para pentear", "cream"], "cream"),
    (["ampola", "ampule"], "ampule"),
    (["finalizador", "finisher"], "finisher"),
    (["tratamento", "treatment", "reconstrução"], "treatment"),
    (["esfoliante", "exfoliant"], "exfoliant"),
    (["texturizador", "texturizer"], "texturizer"),
]


def normalize_product_type(raw_name: str) -> str | None:
    lower = raw_name.lower()
    for keywords, normalized in _TYPE_MAP:
        for kw in keywords:
            if kw in lower:
                return normalized
    return None


def detect_gender_target(product_name: str, url: str) -> str:
    combined = f"{product_name} {url}".lower()
    if "unissex" in combined or "unisex" in combined:
        return "unisex"
    for kw in KIDS_KEYWORDS:
        if kw in combined:
            return "kids"
    for kw in MALE_TARGETING_KEYWORDS:
        if kw in combined:
            return "men"
    return "unknown"


def is_hair_relevant_by_keywords(
    product_name: str, url: str, description: str = ""
) -> tuple[bool, str]:
    combined = f"{product_name} {url} {description}".lower()
    for ekw in EXCLUDE_KEYWORDS:
        if ekw in combined:
            return False, ""
    for hkw in HAIR_KEYWORDS:
        if hkw in combined:
            return True, f"keyword '{hkw}' found"
    return False, ""


def is_kit_url(url: str) -> bool:
    lower_url = url.lower()
    for pattern in KIT_PATTERNS:
        if re.search(pattern, lower_url):
            return True
    return False
```

**Step 4: Run tests**

Run: `pytest tests/core/test_taxonomy.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/taxonomy.py tests/core/test_taxonomy.py
git commit -m "feat: add taxonomy module with hair types, gender detection, keyword classification"
```

---

### Task 4: INCI Validator

**Files:**
- Create: `src/core/inci_validator.py`
- Create: `tests/core/test_inci_validator.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_inci_validator.py
import pytest
from src.core.inci_validator import (
    clean_inci_text,
    validate_ingredient,
    detect_concatenation,
    detect_repetition,
    validate_inci_list,
    INCIValidationResult,
)


class TestCleanInciText:
    def test_cuts_at_modo_de_uso(self):
        raw = "Aqua, Sodium Laureth Sulfate, Glycerin. Modo de uso: aplicar nos cabelos"
        result = clean_inci_text(raw)
        assert "Modo de uso" not in result
        assert "Aqua" in result

    def test_cuts_at_how_to_use(self):
        raw = "Aqua, Cetearyl Alcohol. How to use: apply to wet hair"
        result = clean_inci_text(raw)
        assert "How to use" not in result

    def test_removes_garbage_phrases(self):
        raw = "Aqua, Glycerin, click here, Sodium Chloride, ver mais"
        result = clean_inci_text(raw)
        assert "click here" not in result
        assert "ver mais" not in result

    def test_removes_como_usar(self):
        raw = "Aqua, Glycerin, Parfum. Como usar: massageie"
        result = clean_inci_text(raw)
        assert "Como usar" not in result

    def test_cuts_at_beneficios(self):
        raw = "Aqua, Glycerin, Parfum. Benefícios: hidratação intensa"
        result = clean_inci_text(raw)
        assert "Benefícios" not in result


class TestValidateIngredient:
    def test_valid_ingredient(self):
        assert validate_ingredient("Sodium Laureth Sulfate") is True

    def test_too_short(self):
        assert validate_ingredient("A") is False

    def test_too_long(self):
        assert validate_ingredient("A" * 81) is False

    def test_contains_url(self):
        assert validate_ingredient("https://example.com") is False

    def test_contains_verb_instruction(self):
        assert validate_ingredient("Aplique nos cabelos molhados") is False

    def test_too_many_words(self):
        assert validate_ingredient("one two three four five six seven eight nine") is False

    def test_valid_complex(self):
        assert validate_ingredient("PEG-120 Methyl Glucose Trioleate") is True


class TestDetectConcatenation:
    def test_multiple_aqua(self):
        ingredients = [
            "Aqua", "Glycerin", "Parfum",
            "Aqua", "Cetearyl Alcohol", "Dimethicone",
        ]
        assert detect_concatenation(ingredients) is True

    def test_product_headings(self):
        ingredients = [
            "Shampoo:", "Aqua", "Glycerin",
            "Condicionador:", "Aqua", "Cetearyl Alcohol",
        ]
        assert detect_concatenation(ingredients) is True

    def test_clean_list(self):
        ingredients = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride"]
        assert detect_concatenation(ingredients) is False


class TestDetectRepetition:
    def test_repeated_block(self):
        block = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid"]
        ingredients = block + block
        assert detect_repetition(ingredients) is True

    def test_no_repetition(self):
        ingredients = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid"]
        assert detect_repetition(ingredients) is False

    def test_triple_repetition(self):
        block = ["Aqua", "Glycerin", "Parfum"]
        ingredients = block * 3
        assert detect_repetition(ingredients) is True


class TestValidateInciList:
    def test_valid_list(self):
        ingredients = [
            "Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
            "Glycerin", "Parfum", "Citric Acid",
        ]
        result = validate_inci_list(ingredients)
        assert result.valid is True
        assert len(result.cleaned) == 6

    def test_too_few_ingredients(self):
        result = validate_inci_list(["Aqua", "Glycerin"])
        assert result.valid is False
        assert "min_ingredients" in result.rejection_reason

    def test_deduplication(self):
        ingredients = [
            "Aqua", "aqua", "Glycerin", "GLYCERIN",
            "Parfum", "Sodium Chloride", "Citric Acid",
        ]
        result = validate_inci_list(ingredients)
        assert result.valid is True
        assert len(result.cleaned) == 5

    def test_concatenation_rejected(self):
        ingredients = [
            "Aqua", "Glycerin", "Parfum",
            "Aqua", "Cetearyl Alcohol", "Dimethicone",
            "Sodium Chloride",
        ]
        result = validate_inci_list(ingredients)
        assert result.valid is False
        assert "concat" in result.rejection_reason

    def test_repetition_rejected(self):
        block = ["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid"]
        result = validate_inci_list(block + block)
        assert result.valid is False
        assert "repetition" in result.rejection_reason
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/core/test_inci_validator.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/core/inci_validator.py
from __future__ import annotations

import re
from dataclasses import dataclass, field

CUT_MARKERS: list[str] = [
    "modo de uso", "como usar", "how to use", "directions",
    "benefícios", "benefits", "indicação", "precauções", "warnings",
    "validade", "reg. ms", "sac:", "cnpj", "fabricante",
]

GARBAGE_PHRASES: list[str] = [
    "click here", "see more", "read more", "ver mais", "clique aqui",
    "saiba mais", "leia mais", "show more", "infamous", "known for",
    "commonly used", "is a type of", "can cause", "compare",
    "report error", "embed",
]

VERB_INDICATORS: list[str] = [
    "aplique", "aplicar", "massageie", "enxágue", "enxague",
    "use", "apply", "massage", "rinse", "wash", "lavar",
    "espalhe", "distribua", "deixe agir", "aguarde",
]

PRODUCT_HEADING_PATTERNS: list[str] = [
    r"shampoo\s*:", r"condicionador\s*:", r"conditioner\s*:",
    r"máscara\s*:", r"mascara\s*:", r"mask\s*:",
    r"creme\s*:", r"leave-in\s*:", r"óleo\s*:",
]


@dataclass
class INCIValidationResult:
    valid: bool
    cleaned: list[str] = field(default_factory=list)
    rejection_reason: str = ""
    removed: list[str] = field(default_factory=list)


def clean_inci_text(raw: str) -> str:
    text = raw
    lower = text.lower()
    for marker in CUT_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            text = text[:idx]
            lower = text.lower()
    for phrase in GARBAGE_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return text.strip()


def validate_ingredient(ingredient: str) -> bool:
    s = ingredient.strip()
    if len(s) < 2 or len(s) > 80:
        return False
    if re.search(r"https?://", s, re.IGNORECASE):
        return False
    if len(s.split()) > 8:
        return False
    lower = s.lower()
    for verb in VERB_INDICATORS:
        if verb in lower and len(s.split()) > 3:
            return False
    return True


def detect_concatenation(ingredients: list[str]) -> bool:
    lower_list = [i.lower().strip() for i in ingredients]
    aqua_count = sum(1 for i in lower_list if i in ("aqua", "water", "aqua/water"))
    if aqua_count >= 2:
        return True
    for item in lower_list:
        for pattern in PRODUCT_HEADING_PATTERNS:
            if re.match(pattern, item):
                return True
    return False


def detect_repetition(ingredients: list[str]) -> bool:
    normalized = [i.lower().strip() for i in ingredients]
    n = len(normalized)
    for block_size in range(3, n // 2 + 1):
        block = normalized[:block_size]
        next_block = normalized[block_size : block_size * 2]
        if block == next_block:
            return True
    return False


def validate_inci_list(ingredients: list[str]) -> INCIValidationResult:
    if detect_concatenation(ingredients):
        return INCIValidationResult(
            valid=False, rejection_reason="concat_detected"
        )
    if detect_repetition(ingredients):
        return INCIValidationResult(
            valid=False, rejection_reason="repetition_detected"
        )
    seen: set[str] = set()
    cleaned: list[str] = []
    removed: list[str] = []
    for ing in ingredients:
        s = ing.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            removed.append(s)
            continue
        if not validate_ingredient(s):
            removed.append(s)
            continue
        seen.add(key)
        cleaned.append(s)
    if len(cleaned) < 5:
        return INCIValidationResult(
            valid=False,
            cleaned=cleaned,
            removed=removed,
            rejection_reason="min_ingredients: only {} valid terms".format(len(cleaned)),
        )
    return INCIValidationResult(valid=True, cleaned=cleaned, removed=removed)
```

**Step 4: Run tests**

Run: `pytest tests/core/test_inci_validator.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/inci_validator.py tests/core/test_inci_validator.py
git commit -m "feat: add INCI validator with cut markers, garbage removal, concat/repeat detection"
```

---

### Task 5: QA Gate

**Files:**
- Create: `src/core/qa_gate.py`
- Create: `tests/core/test_qa_gate.py`

**Step 1: Write the failing tests**

```python
# tests/core/test_qa_gate.py
import pytest
from src.core.models import ProductExtraction, GenderTarget, QAStatus
from src.core.qa_gate import run_product_qa, QAConfig

VALID_DOMAINS = ["www.amend.com.br"]


def _make_product(**overrides) -> ProductExtraction:
    defaults = dict(
        brand_slug="amend",
        product_name="Shampoo Gold Black",
        product_url="https://www.amend.com.br/shampoo-gold-black",
        image_url_main="https://www.amend.com.br/img/shampoo.jpg",
        gender_target=GenderTarget.UNISEX,
        hair_relevance_reason="shampoo in name",
    )
    defaults.update(overrides)
    return ProductExtraction(**defaults)


class TestCatalogOnlyQA:
    def test_valid_catalog_only(self):
        product = _make_product()
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.CATALOG_ONLY
        assert result.passed is True

    def test_garbage_name_fails(self):
        product = _make_product(product_name="404")
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_not_found_name_fails(self):
        product = _make_product(product_name="Página não encontrada")
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_no_image_fails(self):
        product = _make_product(image_url_main=None)
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_unofficial_domain_fails(self):
        product = _make_product(
            product_url="https://www.incidecoder.com/products/amend-shampoo"
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False

    def test_no_hair_relevance_fails(self):
        product = _make_product(hair_relevance_reason="")
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.passed is False


class TestVerifiedInciQA:
    def test_valid_verified(self):
        product = _make_product(
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
                              "Glycerin", "Parfum", "Citric Acid"],
            product_type_normalized="shampoo",
            confidence=0.90,
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.VERIFIED_INCI
        assert result.passed is True

    def test_low_confidence_quarantined(self):
        product = _make_product(
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
                              "Glycerin", "Parfum"],
            product_type_normalized="shampoo",
            confidence=0.50,
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.QUARANTINED

    def test_too_few_inci_quarantined(self):
        product = _make_product(
            inci_ingredients=["Aqua", "Glycerin"],
            product_type_normalized="shampoo",
            confidence=0.90,
        )
        result = run_product_qa(product, VALID_DOMAINS)
        assert result.status == QAStatus.QUARANTINED
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/core/test_qa_gate.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/core/qa_gate.py
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from src.core.inci_validator import validate_inci_list
from src.core.models import ProductExtraction, QAResult, QAStatus
from src.core.taxonomy import HAIR_PRODUCT_TYPES


@dataclass
class QAConfig:
    min_inci_terms: int = 5
    min_confidence: float = 0.80


GARBAGE_NAMES: list[str] = [
    "404", "não encontrado", "não encontrada",
    "página não encontrada", "page not found",
    "produto indisponível", "product unavailable",
    "error", "erro",
]


def _check_domain(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return any(host == d or host.endswith(f".{d}") for d in allowed_domains)


def run_product_qa(
    product: ProductExtraction,
    allowed_domains: list[str],
    config: QAConfig | None = None,
) -> QAResult:
    if config is None:
        config = QAConfig()

    passed: list[str] = []
    failed: list[str] = []

    # Minimal checks (catalog_only)
    name_lower = product.product_name.strip().lower()
    if any(g in name_lower for g in GARBAGE_NAMES):
        failed.append("name_garbage")
    else:
        passed.append("name_valid")

    if _check_domain(product.product_url, allowed_domains):
        passed.append("domain_valid")
    else:
        failed.append("domain_unofficial")

    if product.image_url_main:
        passed.append("has_image")
    else:
        failed.append("no_image")

    if product.hair_relevance_reason:
        passed.append("hair_relevant")
    else:
        failed.append("no_hair_relevance")

    if failed:
        return QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=passed,
            checks_failed=failed,
            rejection_reason="; ".join(failed),
        )

    # If no INCI, it's catalog_only
    if not product.inci_ingredients:
        return QAResult(
            status=QAStatus.CATALOG_ONLY,
            passed=True,
            checks_passed=passed,
            checks_failed=[],
        )

    # Full INCI checks
    inci_result = validate_inci_list(product.inci_ingredients)
    if not inci_result.valid:
        failed.append(f"inci_invalid:{inci_result.rejection_reason}")
        return QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=passed,
            checks_failed=failed,
            rejection_reason=inci_result.rejection_reason,
        )
    passed.append("inci_valid")

    if product.confidence < config.min_confidence:
        failed.append("low_confidence")
        return QAResult(
            status=QAStatus.QUARANTINED,
            passed=False,
            checks_passed=passed,
            checks_failed=failed,
            rejection_reason=f"confidence {product.confidence} < {config.min_confidence}",
        )
    passed.append("confidence_ok")

    return QAResult(
        status=QAStatus.VERIFIED_INCI,
        passed=True,
        checks_passed=passed,
        checks_failed=[],
    )
```

**Step 4: Run tests**

Run: `pytest tests/core/test_qa_gate.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/core/qa_gate.py tests/core/test_qa_gate.py
git commit -m "feat: add QA gate with catalog_only/verified_inci/quarantine classification"
```

---

### Task 6: SQLAlchemy ORM Models + Database Setup

**Files:**
- Create: `src/storage/database.py`
- Create: `src/storage/orm_models.py`
- Create: `tests/storage/__init__.py`
- Create: `tests/storage/test_orm_models.py`

**Step 1: Write the failing tests**

```python
# tests/storage/test_orm_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.orm_models import Base, ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM
from src.storage.database import get_engine


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestProductORM:
    def test_create_product(self, db_session):
        product = ProductORM(
            brand_slug="amend",
            product_name="Shampoo Gold Black",
            product_url="https://www.amend.com.br/shampoo-gold-black",
            image_url_main="https://www.amend.com.br/img.jpg",
            verification_status="catalog_only",
            gender_target="unisex",
            hair_relevance_reason="shampoo in name",
            confidence=0.0,
        )
        db_session.add(product)
        db_session.commit()
        assert product.id is not None

    def test_unique_url_constraint(self, db_session):
        p1 = ProductORM(
            brand_slug="amend", product_name="Shampoo A",
            product_url="https://www.amend.com.br/shampoo",
            verification_status="catalog_only", gender_target="unknown",
            confidence=0.0,
        )
        p2 = ProductORM(
            brand_slug="amend", product_name="Shampoo B",
            product_url="https://www.amend.com.br/shampoo",
            verification_status="catalog_only", gender_target="unknown",
            confidence=0.0,
        )
        db_session.add(p1)
        db_session.commit()
        db_session.add(p2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_product_with_evidence(self, db_session):
        product = ProductORM(
            brand_slug="amend", product_name="Shampoo",
            product_url="https://www.amend.com.br/shampoo",
            verification_status="verified_inci", gender_target="unknown",
            confidence=0.9,
        )
        db_session.add(product)
        db_session.flush()
        evidence = ProductEvidenceORM(
            product_id=product.id,
            field_name="inci_ingredients",
            source_url="https://www.amend.com.br/shampoo",
            evidence_locator=".ingredients",
            raw_source_text="Aqua, Glycerin",
            extraction_method="html_selector",
        )
        db_session.add(evidence)
        db_session.commit()
        assert len(product.evidence) == 1


class TestBrandCoverageORM:
    def test_create(self, db_session):
        cov = BrandCoverageORM(
            brand_slug="amend",
            discovered_total=100,
            hair_total=80,
            kits_total=5,
            non_hair_total=15,
            extracted_total=80,
            verified_inci_total=60,
            verified_inci_rate=0.75,
            catalog_only_total=15,
            quarantined_total=5,
            status="active",
            blueprint_version=1,
        )
        db_session.add(cov)
        db_session.commit()
        assert cov.id is not None
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/storage/test_orm_models.py -v`
Expected: FAIL

**Step 3: Implement database.py**

```python
# src/storage/database.py
from __future__ import annotations

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "sqlite:///haira.db")
        _engine = create_engine(url, echo=os.environ.get("SQL_ECHO", "").lower() == "true")
    return _engine


def get_session() -> Session:
    factory = sessionmaker(bind=get_engine())
    return factory()


def reset_engine() -> None:
    global _engine
    _engine = None
```

**Step 4: Implement orm_models.py**

```python
# src/storage/orm_models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductORM(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=_uuid)
    brand_slug = Column(String(255), nullable=False, index=True)
    product_name = Column(String(500), nullable=False)
    product_url = Column(String(2000), nullable=False, unique=True)
    image_url_main = Column(String(2000), nullable=True)
    image_urls_gallery = Column(JSON, nullable=True)
    verification_status = Column(String(50), nullable=False, default="catalog_only")
    product_type_raw = Column(String(255), nullable=True)
    product_type_normalized = Column(String(100), nullable=True)
    gender_target = Column(String(20), nullable=False, default="unknown")
    hair_relevance_reason = Column(Text, nullable=True)
    inci_ingredients = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    usage_instructions = Column(Text, nullable=True)
    benefits_claims = Column(JSON, nullable=True)
    size_volume = Column(String(100), nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String(3), nullable=True)
    line_collection = Column(String(255), nullable=True)
    variants = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    extraction_method = Column(String(50), nullable=True)
    extracted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    evidence = relationship("ProductEvidenceORM", back_populates="product", cascade="all, delete-orphan")
    quarantine_detail = relationship("QuarantineDetailORM", back_populates="product", uselist=False, cascade="all, delete-orphan")


class ProductEvidenceORM(Base):
    __tablename__ = "product_evidence"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    source_url = Column(String(2000), nullable=False)
    evidence_locator = Column(String(500), nullable=True)
    raw_source_text = Column(Text, nullable=True)
    extraction_method = Column(String(50), nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=_utcnow)

    product = relationship("ProductORM", back_populates="evidence")


class QuarantineDetailORM(Base):
    __tablename__ = "quarantine_details"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, unique=True)
    rejection_reason = Column(Text, nullable=False)
    rejection_code = Column(String(100), nullable=True)
    review_status = Column(String(20), nullable=False, default="pending")
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    product = relationship("ProductORM", back_populates="quarantine_detail")


class BrandCoverageORM(Base):
    __tablename__ = "brand_coverage"

    id = Column(String(36), primary_key=True, default=_uuid)
    brand_slug = Column(String(255), nullable=False, unique=True)
    discovered_total = Column(Integer, nullable=False, default=0)
    hair_total = Column(Integer, nullable=False, default=0)
    kits_total = Column(Integer, nullable=False, default=0)
    non_hair_total = Column(Integer, nullable=False, default=0)
    extracted_total = Column(Integer, nullable=False, default=0)
    verified_inci_total = Column(Integer, nullable=False, default=0)
    verified_inci_rate = Column(Float, nullable=False, default=0.0)
    catalog_only_total = Column(Integer, nullable=False, default=0)
    quarantined_total = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="active")
    last_run = Column(DateTime, nullable=True)
    blueprint_version = Column(Integer, nullable=False, default=1)
    coverage_report = Column(JSON, nullable=True)
```

**Step 5: Run tests**

Run: `pytest tests/storage/test_orm_models.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/storage/database.py src/storage/orm_models.py tests/storage/__init__.py tests/storage/test_orm_models.py
git commit -m "feat: add SQLAlchemy ORM models and database setup"
```

---

### Task 7: Repository (CRUD Operations)

**Files:**
- Create: `src/storage/repository.py`
- Create: `tests/storage/test_repository.py`

**Step 1: Write the failing tests**

```python
# tests/storage/test_repository.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.orm_models import Base
from src.storage.repository import ProductRepository
from src.core.models import ProductExtraction, Evidence, GenderTarget, ExtractionMethod, QAResult, QAStatus


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def repo(db_session):
    return ProductRepository(db_session)


def _make_extraction(**overrides) -> ProductExtraction:
    defaults = dict(
        brand_slug="amend",
        product_name="Shampoo Gold Black",
        product_url="https://www.amend.com.br/shampoo-gold-black",
        image_url_main="https://www.amend.com.br/img.jpg",
        gender_target=GenderTarget.UNISEX,
        hair_relevance_reason="shampoo in name",
        confidence=0.0,
    )
    defaults.update(overrides)
    return ProductExtraction(**defaults)


class TestUpsertProduct:
    def test_insert_new(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        product_id = repo.upsert_product(extraction, qa)
        assert product_id is not None
        db_session.flush()

    def test_upsert_existing(self, repo, db_session):
        extraction = _make_extraction()
        qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=["name_valid"])
        id1 = repo.upsert_product(extraction, qa)
        db_session.commit()

        extraction2 = _make_extraction(product_name="Shampoo Gold Black V2")
        id2 = repo.upsert_product(extraction2, qa)
        db_session.commit()
        assert id1 == id2


class TestGetProducts:
    def test_get_verified_only(self, repo, db_session):
        e1 = _make_extraction(
            product_url="https://www.amend.com.br/p1",
            inci_ingredients=["Aqua", "Glycerin", "Parfum", "Sodium Chloride", "Citric Acid", "Panthenol"],
            confidence=0.9,
        )
        qa1 = QAResult(status=QAStatus.VERIFIED_INCI, passed=True, checks_passed=[])
        repo.upsert_product(e1, qa1)

        e2 = _make_extraction(product_url="https://www.amend.com.br/p2")
        qa2 = QAResult(status=QAStatus.CATALOG_ONLY, passed=True, checks_passed=[])
        repo.upsert_product(e2, qa2)
        db_session.commit()

        verified = repo.get_products(verified_only=True)
        assert len(verified) == 1
        assert verified[0].product_name == "Shampoo Gold Black"


class TestBrandStats:
    def test_upsert_coverage(self, repo, db_session):
        stats = {
            "brand_slug": "amend",
            "discovered_total": 100,
            "hair_total": 80,
            "kits_total": 5,
            "non_hair_total": 15,
            "extracted_total": 80,
            "verified_inci_total": 60,
            "verified_inci_rate": 0.75,
            "catalog_only_total": 15,
            "quarantined_total": 5,
            "status": "done",
            "blueprint_version": 1,
        }
        repo.upsert_brand_coverage(stats)
        db_session.commit()

        cov = repo.get_brand_coverage("amend")
        assert cov is not None
        assert cov.verified_inci_rate == 0.75
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/storage/test_repository.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/storage/repository.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.models import ProductExtraction, QAResult, QAStatus
from src.storage.orm_models import ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM


class ProductRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_product(self, extraction: ProductExtraction, qa: QAResult) -> str:
        existing = (
            self._session.query(ProductORM)
            .filter(ProductORM.product_url == extraction.product_url)
            .first()
        )
        if existing:
            existing.product_name = extraction.product_name
            existing.image_url_main = extraction.image_url_main
            existing.image_urls_gallery = extraction.image_urls_gallery or None
            existing.verification_status = qa.status.value
            existing.product_type_raw = extraction.product_type_raw
            existing.product_type_normalized = extraction.product_type_normalized
            existing.gender_target = extraction.gender_target.value
            existing.hair_relevance_reason = extraction.hair_relevance_reason
            existing.inci_ingredients = extraction.inci_ingredients
            existing.description = extraction.description
            existing.usage_instructions = extraction.usage_instructions
            existing.benefits_claims = extraction.benefits_claims
            existing.size_volume = extraction.size_volume
            existing.price = extraction.price
            existing.currency = extraction.currency
            existing.line_collection = extraction.line_collection
            existing.variants = extraction.variants
            existing.confidence = extraction.confidence
            existing.extraction_method = extraction.extraction_method
            existing.extracted_at = extraction.extracted_at
            existing.updated_at = datetime.now(timezone.utc)
            product_id = existing.id
        else:
            product = ProductORM(
                brand_slug=extraction.brand_slug,
                product_name=extraction.product_name,
                product_url=extraction.product_url,
                image_url_main=extraction.image_url_main,
                image_urls_gallery=extraction.image_urls_gallery or None,
                verification_status=qa.status.value,
                product_type_raw=extraction.product_type_raw,
                product_type_normalized=extraction.product_type_normalized,
                gender_target=extraction.gender_target.value,
                hair_relevance_reason=extraction.hair_relevance_reason,
                inci_ingredients=extraction.inci_ingredients,
                description=extraction.description,
                usage_instructions=extraction.usage_instructions,
                benefits_claims=extraction.benefits_claims,
                size_volume=extraction.size_volume,
                price=extraction.price,
                currency=extraction.currency,
                line_collection=extraction.line_collection,
                variants=extraction.variants,
                confidence=extraction.confidence,
                extraction_method=extraction.extraction_method,
                extracted_at=extraction.extracted_at,
            )
            self._session.add(product)
            self._session.flush()
            product_id = product.id

        # Save evidence
        for ev in extraction.evidence:
            evidence_orm = ProductEvidenceORM(
                product_id=product_id,
                field_name=ev.field_name,
                source_url=ev.source_url,
                evidence_locator=ev.evidence_locator,
                raw_source_text=ev.raw_source_text,
                extraction_method=ev.extraction_method.value,
                extracted_at=ev.extracted_at,
            )
            self._session.add(evidence_orm)

        # Save quarantine details
        if qa.status == QAStatus.QUARANTINED and qa.rejection_reason:
            existing_q = (
                self._session.query(QuarantineDetailORM)
                .filter(QuarantineDetailORM.product_id == product_id)
                .first()
            )
            if existing_q:
                existing_q.rejection_reason = qa.rejection_reason
            else:
                qd = QuarantineDetailORM(
                    product_id=product_id,
                    rejection_reason=qa.rejection_reason,
                    rejection_code=qa.checks_failed[0] if qa.checks_failed else None,
                )
                self._session.add(qd)

        return product_id

    def get_products(
        self,
        brand_slug: str | None = None,
        verified_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProductORM]:
        query = self._session.query(ProductORM)
        if brand_slug:
            query = query.filter(ProductORM.brand_slug == brand_slug)
        if verified_only:
            query = query.filter(ProductORM.verification_status == "verified_inci")
        return query.offset(offset).limit(limit).all()

    def get_product_by_id(self, product_id: str) -> ProductORM | None:
        return self._session.query(ProductORM).filter(ProductORM.id == product_id).first()

    def upsert_brand_coverage(self, stats: dict) -> None:
        slug = stats["brand_slug"]
        existing = (
            self._session.query(BrandCoverageORM)
            .filter(BrandCoverageORM.brand_slug == slug)
            .first()
        )
        if existing:
            for key, val in stats.items():
                if key != "brand_slug" and hasattr(existing, key):
                    setattr(existing, key, val)
            existing.last_run = datetime.now(timezone.utc)
        else:
            cov = BrandCoverageORM(**stats)
            cov.last_run = datetime.now(timezone.utc)
            self._session.add(cov)

    def get_brand_coverage(self, brand_slug: str) -> BrandCoverageORM | None:
        return (
            self._session.query(BrandCoverageORM)
            .filter(BrandCoverageORM.brand_slug == brand_slug)
            .first()
        )

    def get_all_brand_coverages(self) -> list[BrandCoverageORM]:
        return self._session.query(BrandCoverageORM).all()
```

**Step 4: Run tests**

Run: `pytest tests/storage/test_repository.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/storage/repository.py tests/storage/test_repository.py
git commit -m "feat: add product repository with upsert, query, and brand coverage stats"
```

---

### Task 8: Excel Registry Loader

**Files:**
- Create: `src/registry/excel_loader.py`
- Create: `tests/registry/__init__.py`
- Create: `tests/registry/test_excel_loader.py`
- Create: `tests/fixtures/test_brands.xlsx` (small test fixture)

**Step 1: Write the failing tests**

```python
# tests/registry/test_excel_loader.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.registry.excel_loader import load_brands_from_excel, Brand


# We'll mock openpyxl to avoid needing a real xlsx in tests
class TestLoadBrands:
    def test_loads_nacionais(self, tmp_path):
        # Create a minimal test xlsx
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Nacionais"
        ws.append(["Marca", "Marketplace", "Site da Marca", "Ingredientes no site"])
        ws.append(["Amend Cosméticos", "Beleza na Web", "https://www.amend.com.br/", "sim"])
        ws.append(["Test Brand", "Amazon", "https://www.testbrand.com.br/", "não"])
        filepath = tmp_path / "test.xlsx"
        wb.save(filepath)

        brands = load_brands_from_excel(str(filepath))
        assert len(brands) == 2
        assert brands[0].brand_name == "Amend Cosméticos"
        assert brands[0].brand_slug == "amend-cosmeticos"
        assert brands[0].official_url_root == "https://www.amend.com.br/"

    def test_loads_internacionais(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Nacionais"
        ws1.append(["Marca", "Marketplace", "Site da Marca", "Ingredientes no site"])

        ws2 = wb.create_sheet("Internacionais")
        ws2.append(["Marca", "País de Origem", "Marketplace", "Site da Marca", "Ingredientes no site da Marca"])
        ws2.append(["Kérastase", "França", "Sephora", "https://www.kerastase.com.br/", "sim"])
        filepath = tmp_path / "test.xlsx"
        wb.save(filepath)

        brands = load_brands_from_excel(str(filepath))
        assert len(brands) == 1
        assert brands[0].country == "França"

    def test_loads_marcas_principais_entrypoints(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Nacionais"
        ws1.append(["Marca", "Marketplace", "Site da Marca", "Ingredientes no site"])

        ws2 = wb.create_sheet("Marcas Principais")
        ws2.append(["Nome", "Site", "Caminho", "Extrair", "OBS"])
        ws2.append(["Wella", "https://loja.wella.com.br", "todo o site", None, None])
        ws2.append(["Truss", "https://www.trussprofessional.com.br", "Home > Produtos", "https://truss.com/produtos", None])
        filepath = tmp_path / "test.xlsx"
        wb.save(filepath)

        brands = load_brands_from_excel(str(filepath))
        wella = next(b for b in brands if b.brand_name == "Wella")
        assert "https://loja.wella.com.br" in wella.official_url_root
        assert wella.priority is not None  # Marcas Principais get priority

    def test_deduplicates_by_slug(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Nacionais"
        ws1.append(["Marca", "Marketplace", "Site da Marca", "Ingredientes no site"])
        ws1.append(["Amend", "BnW", "https://www.amend.com.br/", "sim"])

        ws2 = wb.create_sheet("Marcas Principais")
        ws2.append(["Nome", "Site", "Caminho", "Extrair", "OBS"])
        ws2.append(["Amend", "https://www.amend.com.br/", None, None, None])
        filepath = tmp_path / "test.xlsx"
        wb.save(filepath)

        brands = load_brands_from_excel(str(filepath))
        amend_brands = [b for b in brands if "amend" in b.brand_slug]
        assert len(amend_brands) == 1
        assert amend_brands[0].priority is not None  # Marcas Principais priority wins

    def test_export_to_json(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Nacionais"
        ws.append(["Marca", "Marketplace", "Site da Marca", "Ingredientes no site"])
        ws.append(["TestBrand", "BnW", "https://www.test.com.br/", "não"])
        filepath = tmp_path / "test.xlsx"
        wb.save(filepath)

        brands = load_brands_from_excel(str(filepath))
        output = tmp_path / "brands.json"
        from src.registry.excel_loader import export_brands_json
        export_brands_json(brands, str(output))

        data = json.loads(output.read_text())
        assert len(data) == 1
        assert data[0]["brand_name"] == "TestBrand"
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/registry/test_excel_loader.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/registry/excel_loader.py
from __future__ import annotations

import json
import logging
from pathlib import Path

import openpyxl
from python_slugify import slugify

from src.core.models import Brand

logger = logging.getLogger(__name__)


def _clean_url(url: str | None) -> str:
    if not url:
        return ""
    return url.strip()


def load_brands_from_excel(filepath: str) -> list[Brand]:
    wb = openpyxl.load_workbook(filepath, read_only=True)
    brands_by_slug: dict[str, Brand] = {}

    # 1. Load Nacionais
    if "Nacionais" in wb.sheetnames:
        ws = wb["Nacionais"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            name = row[0] if row[0] else None
            site = row[2] if len(row) > 2 else None
            has_inci = row[3] if len(row) > 3 else None
            if not name:
                continue
            name = str(name).strip()
            slug = slugify(name)
            if not slug:
                continue
            brand = Brand(
                brand_name=name,
                brand_slug=slug,
                official_url_root=_clean_url(str(site)) if site else "",
                country="Brasil",
                notes=f"inci_on_site={has_inci}" if has_inci else None,
            )
            brands_by_slug[slug] = brand

    # 2. Load Internacionais
    if "Internacionais" in wb.sheetnames:
        ws = wb["Internacionais"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            name = row[0] if row[0] else None
            country = row[1] if len(row) > 1 else None
            site = row[3] if len(row) > 3 else None
            if not name:
                continue
            name = str(name).strip()
            slug = slugify(name)
            if not slug:
                continue
            if slug not in brands_by_slug:
                brand = Brand(
                    brand_name=name,
                    brand_slug=slug,
                    official_url_root=_clean_url(str(site)) if site else "",
                    country=str(country).strip() if country else None,
                )
                brands_by_slug[slug] = brand

    # 3. Load Marcas Principais (these get priority + entrypoints)
    if "Marcas Principais" in wb.sheetnames:
        ws = wb["Marcas Principais"]
        current_brand_slug: str | None = None
        priority_counter = 1
        for row in ws.iter_rows(min_row=2, values_only=True):
            name = row[0] if row[0] else None
            site = row[1] if len(row) > 1 else None
            caminho = row[2] if len(row) > 2 else None
            extrair = row[3] if len(row) > 3 else None
            obs = row[4] if len(row) > 4 else None

            if name:
                name = str(name).strip()
                slug = slugify(name)
                current_brand_slug = slug
                if slug in brands_by_slug:
                    brands_by_slug[slug].priority = priority_counter
                    if site:
                        brands_by_slug[slug].official_url_root = _clean_url(str(site))
                    if obs:
                        brands_by_slug[slug].notes = str(obs).strip()
                else:
                    brand = Brand(
                        brand_name=name,
                        brand_slug=slug,
                        official_url_root=_clean_url(str(site)) if site else "",
                        priority=priority_counter,
                        notes=str(obs).strip() if obs else None,
                    )
                    brands_by_slug[slug] = brand
                priority_counter += 1

            # Add entrypoints from Caminho or Extrair columns
            target_slug = current_brand_slug
            if target_slug and target_slug in brands_by_slug:
                if extrair and str(extrair).startswith("http"):
                    url = _clean_url(str(extrair))
                    if url not in brands_by_slug[target_slug].catalog_entrypoints:
                        brands_by_slug[target_slug].catalog_entrypoints.append(url)
                elif site and str(site).startswith("http") and name:
                    url = _clean_url(str(site))
                    if url not in brands_by_slug[target_slug].catalog_entrypoints:
                        brands_by_slug[target_slug].catalog_entrypoints.append(url)

    wb.close()
    result = list(brands_by_slug.values())
    logger.info(f"Loaded {len(result)} brands from {filepath}")
    return result


def export_brands_json(brands: list[Brand], output_path: str) -> None:
    data = [b.model_dump() for b in brands]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Exported {len(data)} brands to {output_path}")
```

**Step 4: Run tests**

Run: `pytest tests/registry/test_excel_loader.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/registry/excel_loader.py tests/registry/__init__.py tests/registry/test_excel_loader.py
git commit -m "feat: add Excel registry loader with 3-sheet merge and JSON export"
```

---

## Phase 2: Core Pipeline

### Task 9: LLM Client Wrapper with Cost Tracking

**Files:**
- Create: `src/core/llm.py`
- Create: `src/pipeline/cost_tracker.py`
- Create: `tests/core/test_llm.py`
- Create: `tests/pipeline/__init__.py`
- Create: `tests/pipeline/test_cost_tracker.py`

**Step 1: Write tests for cost_tracker**

```python
# tests/pipeline/test_cost_tracker.py
import pytest
from src.pipeline.cost_tracker import CostTracker


class TestCostTracker:
    def test_initial_state(self):
        tracker = CostTracker(max_calls=50)
        assert tracker.total_calls == 0
        assert tracker.budget_remaining == 50

    def test_record_call(self):
        tracker = CostTracker(max_calls=50)
        tracker.record_call(input_tokens=100, output_tokens=50)
        assert tracker.total_calls == 1
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50

    def test_budget_exceeded(self):
        tracker = CostTracker(max_calls=2)
        tracker.record_call(100, 50)
        tracker.record_call(100, 50)
        assert tracker.budget_exceeded is True

    def test_can_call(self):
        tracker = CostTracker(max_calls=1)
        assert tracker.can_call is True
        tracker.record_call(100, 50)
        assert tracker.can_call is False

    def test_summary(self):
        tracker = CostTracker(max_calls=50)
        tracker.record_call(1000, 500)
        summary = tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["budget_remaining"] == 49
```

**Step 2: Write tests for llm**

```python
# tests/core/test_llm.py
import pytest
from unittest.mock import MagicMock, patch
from src.core.llm import LLMClient


class TestLLMClient:
    def test_budget_check(self):
        client = LLMClient(max_calls_per_brand=2)
        client.reset_brand_budget()
        assert client.can_call is True

    def test_budget_exceeded_raises(self):
        client = LLMClient(max_calls_per_brand=0)
        client.reset_brand_budget()
        with pytest.raises(RuntimeError, match="budget"):
            client.extract_structured(page_text="test", prompt="test")
```

**Step 3: Implement cost_tracker.py**

```python
# src/pipeline/cost_tracker.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostTracker:
    max_calls: int = 50
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def budget_remaining(self) -> int:
        return max(0, self.max_calls - self.total_calls)

    @property
    def budget_exceeded(self) -> bool:
        return self.total_calls >= self.max_calls

    @property
    def can_call(self) -> bool:
        return self.total_calls < self.max_calls

    def record_call(self, input_tokens: int, output_tokens: int) -> None:
        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def summary(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "budget_remaining": self.budget_remaining,
            "budget_exceeded": self.budget_exceeded,
        }
```

**Step 4: Implement llm.py**

```python
# src/core/llm.py
from __future__ import annotations

import json
import logging
import os

import anthropic

from src.pipeline.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, max_calls_per_brand: int | None = None):
        self._model = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else None
        max_calls = max_calls_per_brand or int(os.environ.get("MAX_LLM_CALLS_PER_BRAND", "50"))
        self._tracker = CostTracker(max_calls=max_calls)

    @property
    def can_call(self) -> bool:
        return self._tracker.can_call

    @property
    def cost_summary(self) -> dict:
        return self._tracker.summary()

    def reset_brand_budget(self) -> None:
        self._tracker = CostTracker(max_calls=self._tracker.max_calls)

    def extract_structured(self, page_text: str, prompt: str, max_tokens: int = 4096) -> dict:
        if not self._tracker.can_call:
            raise RuntimeError("LLM budget exceeded for this brand")
        if not self._client:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        system = (
            "You are a hair product data extractor. Extract ONLY information present "
            "in the provided page text. If a field is not found, return null. "
            "Never hallucinate or infer data not explicitly present."
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": f"{prompt}\n\n---PAGE TEXT---\n{page_text[:15000]}"}],
        )
        self._tracker.record_call(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        text = response.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end])
            elif "```" in text:
                start = text.index("```") + 3
                end = text.index("```", start)
                return json.loads(text[start:end])
            logger.warning("LLM response was not valid JSON")
            return {}

    def classify_hair_relevance(self, product_name: str, page_snippet: str) -> dict:
        prompt = (
            "Based ONLY on the product name and page text below, determine if this is a hair/scalp product.\n"
            "Return JSON: {\"hair_related\": true/false, \"reason\": \"...\", \"evidence_quote\": \"...\"}\n\n"
            f"Product name: {product_name}\n"
        )
        return self.extract_structured(page_text=page_snippet, prompt=prompt, max_tokens=256)
```

**Step 5: Run tests**

Run: `pytest tests/core/test_llm.py tests/pipeline/test_cost_tracker.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/core/llm.py src/pipeline/cost_tracker.py tests/core/test_llm.py tests/pipeline/__init__.py tests/pipeline/test_cost_tracker.py
git commit -m "feat: add LLM client with cost tracking and budget enforcement"
```

---

### Task 10: Browser Wrapper

**Files:**
- Create: `src/core/browser.py`
- Create: `tests/core/test_browser.py`

**Step 1: Write tests**

```python
# tests/core/test_browser.py
import pytest
from unittest.mock import MagicMock, patch
from src.core.browser import BrowserClient


class TestBrowserClient:
    def test_rate_limiting_config(self):
        client = BrowserClient(delay_seconds=5)
        assert client._delay == 5

    def test_default_delay(self):
        client = BrowserClient()
        assert client._delay == 3

    def test_respects_domain_allowlist(self):
        client = BrowserClient()
        assert client.is_allowed_domain("https://www.amend.com.br/produto", ["www.amend.com.br"]) is True
        assert client.is_allowed_domain("https://www.incidecoder.com/x", ["www.amend.com.br"]) is False
```

**Step 2: Implement**

```python
# src/core/browser.py
from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BrowserClient:
    def __init__(self, delay_seconds: float | None = None):
        self._delay = delay_seconds or float(os.environ.get("REQUEST_DELAY_SECONDS", "3"))
        self._headless = os.environ.get("HEADLESS", "true").lower() == "true"
        self._browser = None
        self._page = None
        self._last_request_time: float = 0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request_time = time.time()

    def _ensure_browser(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page()

    def fetch_page(self, url: str, wait_for: str | None = None) -> str:
        self._ensure_browser()
        self._rate_limit()
        logger.info(f"Fetching: {url}")
        self._page.goto(url, timeout=30000, wait_until="networkidle")
        if wait_for:
            try:
                self._page.wait_for_selector(wait_for, timeout=5000)
            except Exception:
                logger.debug(f"Selector {wait_for} not found, continuing")
        return self._page.content()

    def fetch_page_text(self, url: str) -> str:
        self._ensure_browser()
        self._rate_limit()
        self._page.goto(url, timeout=30000, wait_until="networkidle")
        return self._page.inner_text("body")

    @staticmethod
    def is_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return any(host == d or host.endswith(f".{d}") for d in allowed_domains)

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._playwright.stop()
            self._browser = None
            self._page = None
```

**Step 3: Run tests**

Run: `pytest tests/core/test_browser.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/core/browser.py tests/core/test_browser.py
git commit -m "feat: add Playwright browser wrapper with rate limiting"
```

---

### Task 11: Deterministic Extraction (JSON-LD + CSS Selectors)

**Files:**
- Create: `src/extraction/deterministic.py`
- Create: `src/extraction/evidence_tracker.py`
- Create: `tests/extraction/__init__.py`
- Create: `tests/extraction/test_deterministic.py`
- Create: `tests/fixtures/sample_product_page.html`

**Step 1: Create HTML fixture**

```html
<!-- tests/fixtures/sample_product_page.html -->
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Shampoo Gold Black Reparador",
  "image": "https://www.amend.com.br/img/shampoo-gold-black.jpg",
  "description": "Shampoo reparador para cabelos danificados",
  "offers": {
    "@type": "Offer",
    "price": "29.90",
    "priceCurrency": "BRL"
  }
}
</script>
</head>
<body>
<h1 class="product-name">Shampoo Gold Black Reparador</h1>
<img class="product-image" src="https://www.amend.com.br/img/shampoo-gold-black.jpg" />
<div class="product-description">Shampoo reparador para cabelos danificados</div>
<div class="product-ingredients">
  <h3>Ingredientes</h3>
  <p>Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid, Sodium Chloride, Panthenol, Dimethicone, Phenoxyethanol</p>
</div>
<div class="product-usage">
  <h3>Modo de uso</h3>
  <p>Aplique nos cabelos molhados e massageie.</p>
</div>
</body>
</html>
```

**Step 2: Write tests**

```python
# tests/extraction/test_deterministic.py
import pytest
from pathlib import Path
from src.extraction.deterministic import extract_jsonld, extract_by_selectors, extract_product_deterministic


@pytest.fixture
def sample_html():
    return (Path(__file__).parent.parent / "fixtures" / "sample_product_page.html").read_text()


class TestExtractJsonLD:
    def test_extracts_product_name(self, sample_html):
        data = extract_jsonld(sample_html)
        assert data is not None
        assert data["name"] == "Shampoo Gold Black Reparador"

    def test_extracts_price(self, sample_html):
        data = extract_jsonld(sample_html)
        assert data["offers"]["price"] == "29.90"

    def test_returns_none_for_no_jsonld(self):
        data = extract_jsonld("<html><body>No JSON-LD</body></html>")
        assert data is None


class TestExtractBySelectors:
    def test_extracts_ingredients(self, sample_html):
        result = extract_by_selectors(sample_html, inci_selectors=[".product-ingredients p"])
        assert result["inci_raw"] is not None
        assert "Aqua" in result["inci_raw"]

    def test_extracts_name(self, sample_html):
        result = extract_by_selectors(sample_html, name_selectors=[".product-name", "h1"])
        assert result["name"] == "Shampoo Gold Black Reparador"


class TestExtractProductDeterministic:
    def test_full_extraction(self, sample_html):
        result = extract_product_deterministic(
            html=sample_html,
            url="https://www.amend.com.br/shampoo-gold-black",
            inci_selectors=[".product-ingredients p"],
        )
        assert result["product_name"] == "Shampoo Gold Black Reparador"
        assert result["inci_raw"] is not None
        assert "Aqua" in result["inci_raw"]
        assert result["image_url_main"] is not None
        assert len(result["evidence"]) > 0
```

**Step 3: Implement evidence_tracker.py**

```python
# src/extraction/evidence_tracker.py
from __future__ import annotations

from datetime import datetime, timezone

from src.core.models import Evidence, ExtractionMethod


def create_evidence(
    field_name: str,
    source_url: str,
    evidence_locator: str,
    raw_source_text: str,
    method: ExtractionMethod,
) -> Evidence:
    return Evidence(
        field_name=field_name,
        source_url=source_url,
        evidence_locator=evidence_locator,
        raw_source_text=raw_source_text[:2000],
        extraction_method=method,
        extracted_at=datetime.now(timezone.utc),
    )
```

**Step 4: Implement deterministic.py**

```python
# src/extraction/deterministic.py
from __future__ import annotations

import json
import re
import logging

from src.core.models import ExtractionMethod
from src.extraction.evidence_tracker import create_evidence

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

def _get_soup(html: str):
    if BeautifulSoup is None:
        raise ImportError("beautifulsoup4 is required: pip install beautifulsoup4 lxml")
    return BeautifulSoup(html, "lxml")


def extract_jsonld(html: str) -> dict | None:
    soup = _get_soup(html)
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        return item
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def extract_by_selectors(
    html: str,
    inci_selectors: list[str] | None = None,
    name_selectors: list[str] | None = None,
    image_selectors: list[str] | None = None,
) -> dict:
    soup = _get_soup(html)
    result: dict = {"name": None, "inci_raw": None, "image": None, "inci_selector": None, "name_selector": None}

    if name_selectors:
        for sel in name_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["name"] = el.get_text(strip=True)
                result["name_selector"] = sel
                break

    if inci_selectors:
        for sel in inci_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["inci_raw"] = el.get_text(strip=True)
                result["inci_selector"] = sel
                break

    if image_selectors:
        for sel in image_selectors:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src")
                if src:
                    result["image"] = src
                    break

    return result


def extract_product_deterministic(
    html: str,
    url: str,
    inci_selectors: list[str] | None = None,
    name_selectors: list[str] | None = None,
) -> dict:
    evidence_list = []
    result = {
        "product_name": None,
        "image_url_main": None,
        "inci_raw": None,
        "description": None,
        "price": None,
        "currency": None,
        "evidence": evidence_list,
        "extraction_method": None,
    }

    # Try JSON-LD first
    jsonld = extract_jsonld(html)
    if jsonld:
        if jsonld.get("name"):
            result["product_name"] = jsonld["name"]
            evidence_list.append(create_evidence(
                "product_name", url, "json-ld @type=Product .name",
                jsonld["name"], ExtractionMethod.JSONLD,
            ))
        if jsonld.get("image"):
            img = jsonld["image"]
            if isinstance(img, list):
                img = img[0]
            result["image_url_main"] = img
            evidence_list.append(create_evidence(
                "image_url_main", url, "json-ld @type=Product .image",
                str(img), ExtractionMethod.JSONLD,
            ))
        if jsonld.get("description"):
            result["description"] = jsonld["description"]
        offers = jsonld.get("offers", {})
        if isinstance(offers, dict):
            if offers.get("price"):
                result["price"] = float(offers["price"])
                result["currency"] = offers.get("priceCurrency", "BRL")
        result["extraction_method"] = "jsonld"

    # Try CSS selectors to fill gaps
    default_name_selectors = name_selectors or ["h1.product-name", "h1", ".product-title"]
    default_inci_selectors = inci_selectors or [
        ".product-ingredients p", ".product-ingredients",
        "#composicao", "#ingredientes",
        "[data-tab='ingredientes']",
    ]

    sel_result = extract_by_selectors(
        html,
        inci_selectors=default_inci_selectors,
        name_selectors=default_name_selectors if not result["product_name"] else None,
        image_selectors=[".product-image", "img.product-img"] if not result["image_url_main"] else None,
    )

    if not result["product_name"] and sel_result["name"]:
        result["product_name"] = sel_result["name"]
        evidence_list.append(create_evidence(
            "product_name", url, sel_result["name_selector"] or "",
            sel_result["name"], ExtractionMethod.HTML_SELECTOR,
        ))

    if sel_result["inci_raw"]:
        result["inci_raw"] = sel_result["inci_raw"]
        evidence_list.append(create_evidence(
            "inci_ingredients", url, sel_result["inci_selector"] or "",
            sel_result["inci_raw"][:500], ExtractionMethod.HTML_SELECTOR,
        ))
        if not result["extraction_method"]:
            result["extraction_method"] = "html_selector"

    if not result["image_url_main"] and sel_result.get("image"):
        result["image_url_main"] = sel_result["image"]

    return result
```

**Step 5: Add beautifulsoup4 + lxml to pyproject.toml dependencies**

Add `"beautifulsoup4>=4.12"` and `"lxml>=5.0"` to the dependencies list in pyproject.toml.

**Step 6: Run tests**

Run: `pip install -e ".[dev]" && pytest tests/extraction/test_deterministic.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/extraction/ tests/extraction/ tests/fixtures/sample_product_page.html pyproject.toml
git commit -m "feat: add deterministic extraction with JSON-LD and CSS selectors + evidence tracking"
```

---

### Task 12: INCI Extractor (Full Pipeline)

**Files:**
- Create: `src/extraction/inci_extractor.py`
- Create: `tests/extraction/test_inci_extractor.py`

**Step 1: Write tests**

```python
# tests/extraction/test_inci_extractor.py
import pytest
from src.extraction.inci_extractor import extract_and_validate_inci


class TestExtractAndValidateInci:
    def test_clean_inci_from_raw(self):
        raw = "Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Parfum, Citric Acid"
        result = extract_and_validate_inci(raw)
        assert result.valid is True
        assert len(result.cleaned) == 6

    def test_inci_with_cut_marker(self):
        raw = "Aqua, Sodium Laureth Sulfate, Glycerin, Parfum, Citric Acid, Panthenol. Modo de uso: aplique nos cabelos"
        result = extract_and_validate_inci(raw)
        assert result.valid is True
        assert "Modo de uso" not in " ".join(result.cleaned)

    def test_inci_with_garbage(self):
        raw = "Aqua, Sodium Laureth Sulfate, click here, Glycerin, Parfum, ver mais, Citric Acid"
        result = extract_and_validate_inci(raw)
        assert result.valid is True
        assert all("click" not in i for i in result.cleaned)

    def test_concatenated_inci_rejected(self):
        raw = "Shampoo: Aqua, Glycerin, Parfum. Condicionador: Aqua, Cetearyl Alcohol, Dimethicone"
        result = extract_and_validate_inci(raw)
        assert result.valid is False

    def test_too_few_rejected(self):
        raw = "Aqua, Glycerin"
        result = extract_and_validate_inci(raw)
        assert result.valid is False

    def test_none_input(self):
        result = extract_and_validate_inci(None)
        assert result.valid is False
```

**Step 2: Implement**

```python
# src/extraction/inci_extractor.py
from __future__ import annotations

from src.core.inci_validator import clean_inci_text, validate_inci_list, INCIValidationResult


def extract_and_validate_inci(raw_text: str | None) -> INCIValidationResult:
    if not raw_text or not raw_text.strip():
        return INCIValidationResult(valid=False, rejection_reason="no_inci_text")

    cleaned_text = clean_inci_text(raw_text)
    if not cleaned_text:
        return INCIValidationResult(valid=False, rejection_reason="empty_after_cleaning")

    ingredients = [i.strip() for i in cleaned_text.split(",") if i.strip()]
    return validate_inci_list(ingredients)
```

**Step 3: Run tests**

Run: `pytest tests/extraction/test_inci_extractor.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/extraction/inci_extractor.py tests/extraction/test_inci_extractor.py
git commit -m "feat: add INCI extractor with full cleaning and validation pipeline"
```

---

### Task 13: URL Classifier

**Files:**
- Create: `src/discovery/url_classifier.py`
- Create: `tests/discovery/__init__.py`
- Create: `tests/discovery/test_url_classifier.py`

**Step 1: Write tests**

```python
# tests/discovery/test_url_classifier.py
import pytest
from src.discovery.url_classifier import classify_url, URLType


class TestClassifyUrl:
    def test_product_url(self):
        assert classify_url("https://www.amend.com.br/shampoo-gold-black-reparador") == URLType.PRODUCT

    def test_category_url(self):
        assert classify_url("https://www.amend.com.br/cabelos/shampoo") == URLType.CATEGORY

    def test_kit_url(self):
        assert classify_url("https://www.amend.com.br/kit-shampoo-condicionador") == URLType.KIT

    def test_non_hair_url(self):
        assert classify_url("https://www.amend.com.br/corpo/hidratante-corporal") == URLType.NON_HAIR

    def test_unknown_url(self):
        assert classify_url("https://www.amend.com.br/sobre-nos") == URLType.OTHER
```

**Step 2: Implement**

```python
# src/discovery/url_classifier.py
from __future__ import annotations

import enum
import re

from src.core.taxonomy import HAIR_KEYWORDS, EXCLUDE_KEYWORDS, KIT_PATTERNS


class URLType(str, enum.Enum):
    PRODUCT = "product"
    CATEGORY = "category"
    KIT = "kit"
    NON_HAIR = "non_hair"
    OTHER = "other"


CATEGORY_INDICATORS = [
    "/cabelos/", "/cabelo/", "/hair/", "/produtos/", "/products/",
    "/collections/", "/categoria/", "/category/",
    "/shampoo/", "/condicionador/", "/tratamento/", "/finalizacao/",
    "/masculino/", "/men/",
]

PRODUCT_INDICATORS = [
    r"-\d+ml", r"-\d+g", r"/p$", r"/p/", r"\.html$",
    r"-shampoo-", r"-condicionador-", r"-mascara-",
]


def classify_url(url: str, product_url_pattern: str | None = None) -> URLType:
    lower = url.lower()

    # Check kit first
    for pattern in KIT_PATTERNS:
        if re.search(pattern, lower):
            return URLType.KIT

    # Check non-hair
    for kw in EXCLUDE_KEYWORDS:
        if f"/{kw}/" in lower or f"/{kw}" == lower.split("?")[0][-len(f"/{kw}"):]:
            return URLType.NON_HAIR

    # Check category
    for indicator in CATEGORY_INDICATORS:
        if indicator in lower and lower.rstrip("/").endswith(indicator.rstrip("/")):
            return URLType.CATEGORY
        if indicator in lower and lower.count("/") <= 4:
            # Likely a category if it's a short path with category indicator
            path = lower.split("?")[0]
            segments = [s for s in path.split("/") if s]
            if len(segments) <= 4:
                # Check if it looks like a product (has product-specific patterns)
                is_product = any(re.search(p, lower) for p in PRODUCT_INDICATORS)
                if not is_product:
                    return URLType.CATEGORY

    # Check product patterns
    if product_url_pattern:
        if re.search(product_url_pattern, lower):
            return URLType.PRODUCT

    for pattern in PRODUCT_INDICATORS:
        if re.search(pattern, lower):
            return URLType.PRODUCT

    # Check hair relevance by keywords in URL
    has_hair_keyword = any(kw.replace(" ", "-") in lower or kw.replace(" ", "") in lower for kw in HAIR_KEYWORDS[:20])
    if has_hair_keyword:
        # If it has many path segments, likely a product
        path = lower.split("?")[0]
        segments = [s for s in path.split("/")[3:] if s]  # skip domain
        if len(segments) >= 2:
            return URLType.PRODUCT
        return URLType.CATEGORY

    return URLType.OTHER
```

**Step 3: Run tests**

Run: `pytest tests/discovery/test_url_classifier.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/discovery/ tests/discovery/
git commit -m "feat: add URL classifier for product/category/kit/non-hair detection"
```

---

### Task 14: CLI Foundation

**Files:**
- Create: `src/cli/main.py`

**Step 1: Implement CLI skeleton**

```python
# src/cli/main.py
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from src.core.models import Brand

logger = logging.getLogger("haira")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
def cli(log_level: str):
    """HAIRA v2 — Hair Product Intelligence Platform"""
    _setup_logging(log_level)


@cli.command()
@click.option("--input", "input_path", required=True, help="Path to Excel file")
@click.option("--output", "output_path", default="config/brands.json", help="Output JSON path")
def registry(input_path: str, output_path: str):
    """Import brand registry from Excel spreadsheet."""
    from src.registry.excel_loader import load_brands_from_excel, export_brands_json

    brands = load_brands_from_excel(input_path)
    export_brands_json(brands, output_path)
    click.echo(f"Exported {len(brands)} brands to {output_path}")

    # Summary stats
    with_site = sum(1 for b in brands if b.official_url_root)
    with_priority = sum(1 for b in brands if b.priority is not None)
    click.echo(f"  With official site: {with_site}")
    click.echo(f"  Priority brands: {with_priority}")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
@click.option("--regenerate", is_flag=True, help="Force regenerate blueprint")
def blueprint(brand: str, regenerate: bool):
    """Generate or update blueprint YAML for a brand."""
    click.echo(f"Blueprint for {brand} (regenerate={regenerate}) — not yet implemented")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
def recon(brand: str):
    """Run discovery + small sample extraction for a brand."""
    click.echo(f"Recon for {brand} — not yet implemented")


@cli.command()
@click.option("--brand", help="Brand slug (single brand)")
@click.option("--priority", type=int, help="Run brands with this priority level")
@click.option("--max-brands", type=int, default=10, help="Max brands to process")
def scrape(brand: str | None, priority: int | None, max_brands: int):
    """Run full scrape pipeline for brand(s)."""
    click.echo(f"Scrape — not yet implemented")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
def audit(brand: str):
    """Run QA audit on existing data for a brand."""
    click.echo(f"Audit for {brand} — not yet implemented")


@cli.command()
@click.option("--brand", help="Brand slug")
@click.option("--all-brands", "all_brands", is_flag=True, help="Report for all brands")
def report(brand: str | None, all_brands: bool):
    """Generate coverage report."""
    click.echo(f"Report — not yet implemented")


if __name__ == "__main__":
    cli()
```

**Step 2: Verify CLI runs**

Run: `python -m src.cli.main --help`
Expected: Shows help with all commands

Run: `python -m src.cli.main registry --input "Lista de Produtos.xlsx" --output config/brands.json`
Expected: Exports brands and shows summary

**Step 3: Commit**

```bash
git add src/cli/main.py
git commit -m "feat: add Click CLI skeleton with registry import command"
```

---

### Task 15: Alembic Migrations Setup

**Files:**
- Create: `alembic.ini`
- Create: `src/storage/migrations/env.py`
- Create: `src/storage/migrations/script.py.mako`
- Create: `src/storage/migrations/versions/`

**Step 1: Initialize alembic**

Run: `cd /Users/nikollasanches/Documents/hairaproducts && alembic init src/storage/migrations`

**Step 2: Edit alembic.ini** — set `sqlalchemy.url = sqlite:///haira.db`

**Step 3: Edit migrations/env.py** — import `Base` from `src.storage.orm_models` and set `target_metadata = Base.metadata`

**Step 4: Generate initial migration**

Run: `alembic revision --autogenerate -m "initial schema"`

**Step 5: Apply migration**

Run: `alembic upgrade head`

**Step 6: Commit**

```bash
git add alembic.ini src/storage/migrations/
git commit -m "feat: add Alembic migrations with initial schema"
```

---

## Phase 3: Operational Layer (Tasks 16-19)

### Task 16: FastAPI Application

**Files:**
- Create: `src/api/main.py`
- Create: `src/api/routes/products.py`
- Create: `src/api/routes/brands.py`
- Create: `src/api/routes/quarantine.py`
- Create: `src/api/routes/__init__.py`

Implement FastAPI app with:
- `GET /api/products` (verified_only=true by default, brand filter, pagination)
- `GET /api/products/{id}` (includes evidence)
- `GET /api/brands` (coverage stats per brand)
- `GET /api/brands/{slug}/coverage`
- `GET /api/quarantine` (pending review items)
- `POST /api/quarantine/{id}/approve` (manual override)
- CORS middleware enabled

### Task 17: Coverage Engine (Orchestrator)

**Files:**
- Create: `src/pipeline/coverage_engine.py`
- Create: `src/pipeline/report_generator.py`
- Create: `tests/pipeline/test_coverage_engine.py`

The coverage engine ties everything together for a single brand:
1. Load blueprint YAML
2. Run discovery (product URLs)
3. Classify URLs (hair/non-hair/kit)
4. Extract each product (deterministic first, LLM fallback)
5. Run INCI extraction + validation
6. Run QA gate per product
7. Store results (catalog_only, verified_inci, quarantine)
8. Generate coverage report
9. Update brand_coverage stats
10. Stop-the-line if failure_rate > 50%

### Task 18: Blueprint Engine

**Files:**
- Create: `src/discovery/blueprint_engine.py`
- Create: `tests/discovery/test_blueprint_engine.py`

Blueprint engine:
- Reads brand from registry
- Detects platform (VTEX, Shopify, custom) by checking known patterns
- Generates default YAML blueprint with entrypoints, keywords, selectors
- Saves to `config/blueprints/{slug}.yaml`

### Task 19: Product Discoverer with Platform Adapters

**Files:**
- Create: `src/discovery/product_discoverer.py`
- Create: `src/discovery/platform_adapters/base.py`
- Create: `src/discovery/platform_adapters/sitemap.py`
- Create: `src/discovery/platform_adapters/dom_crawler.py`
- Create: `tests/discovery/test_product_discoverer.py`

Product discoverer:
- Reads blueprint
- Tries platform adapters in priority order (sitemap → category crawl → DOM)
- Handles pagination per blueprint config
- Returns deduplicated list of DiscoveredURL objects

---

## Phase 4: Frontend + Scale (Tasks 20-21)

### Task 20: React Frontend

**Files:**
- Create: `frontend/` (Vite + React + TS + Tailwind scaffold)

Three views:
1. Brand dashboard — coverage table with progress bars
2. Product browser — search/filter verified products
3. Quarantine review — approve/reject with evidence

### Task 21: First 3 Brands to Excellence

Run the full pipeline for:
1. **Amend** — known to have INCI on site, good baseline
2. **Kérastase** — L'Oréal platform, JS-heavy, hidden ingredients
3. A VTEX brand from the registry

For each: generate blueprint, run discovery, extract, validate, review quarantine, iterate until verified_inci_rate >= 90%.
