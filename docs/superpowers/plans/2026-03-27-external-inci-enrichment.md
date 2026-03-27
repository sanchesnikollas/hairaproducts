# External INCI Enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill INCI gaps for catalog_only products by scraping Beleza na Web and cross-referencing via fuzzy match.

**Architecture:** Two-phase pipeline: `haira source-scrape` populates `external_inci` table from retailers, `haira enrich-external` matches and applies INCI to catalog_only products. Data strictly separated.

**Tech Stack:** Python 3.12, SQLAlchemy, Click CLI, difflib (stdlib), Alembic migrations

**Spec:** `docs/superpowers/specs/2026-03-26-external-inci-enrichment-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/storage/orm_models.py` | Modify | Add `ExternalInciORM`, `EnrichmentQueueORM` |
| `src/core/models.py` | Modify | Add `EXTERNAL_ENRICHMENT` to `ExtractionMethod` enum |
| `src/storage/repository.py` | Modify | Add re-scrape protection in `upsert_product()`, add external_inci repo methods |
| `src/enrichment/__init__.py` | Create | Module init |
| `src/enrichment/source_scraper.py` | Create | Scrape external sources, save to `external_inci` |
| `src/enrichment/matcher.py` | Create | Hybrid match algorithm (normalize, fuzzy, type check) |
| `src/cli/main.py` | Modify | Add `source-scrape` and `enrich-external` commands |
| `config/blueprints/sources/belezanaweb.yaml` | Create | Beleza na Web blueprint |
| `src/storage/migrations/versions/xxx_add_external_inci_tables.py` | Create | Migration for new tables |
| `tests/enrichment/test_matcher.py` | Create | Tests for match algorithm |
| `tests/enrichment/test_source_scraper.py` | Create | Tests for source scraper |

---

### Task 1: Data Model — ORM + Migration

**Files:**
- Modify: `src/storage/orm_models.py:212` (add after ProductCompositionORM)
- Modify: `src/core/models.py:25-30` (add enum value)
- Create: migration file

- [ ] **Step 1: Add ExtractionMethod enum value**

In `src/core/models.py`, add to `ExtractionMethod` enum (line ~30):

```python
EXTERNAL_ENRICHMENT = "external_enrichment"
```

- [ ] **Step 2: Add ORM models**

In `src/storage/orm_models.py`, add after `ProductCompositionORM`:

```python
class ExternalInciORM(Base):
    __tablename__ = "external_inci"

    id = Column(String(36), primary_key=True, default=_uuid)
    source = Column(String(50), nullable=False)  # "belezanaweb", "epocacosmeticos"
    source_url = Column(Text, nullable=False)
    brand_slug = Column(String(255), nullable=False, index=True)
    product_name = Column(Text, nullable=True)
    product_type = Column(String(100), nullable=True)
    inci_raw = Column(Text, nullable=True)
    inci_ingredients = Column(JSON, nullable=True)
    ean = Column(String(50), nullable=True)
    scraped_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("source", "source_url", name="uq_external_inci_source_url"),
    )


class EnrichmentQueueORM(Base):
    __tablename__ = "enrichment_queue"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_id = Column(String(36), nullable=False, index=True)
    external_inci_id = Column(String(36), nullable=False)
    match_score = Column(Float, nullable=False)
    match_details = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/rejected
    reviewed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
```

Add `UniqueConstraint` import if not present.

- [ ] **Step 3: Generate migration**

Run: `alembic revision --autogenerate -m "add external_inci and enrichment_queue tables"`

Verify the generated migration creates both tables.

- [ ] **Step 4: Run migration**

Run: `alembic upgrade head`

- [ ] **Step 5: Commit**

```bash
git add src/core/models.py src/storage/orm_models.py src/storage/migrations/versions/
git commit -m "feat: add external_inci and enrichment_queue tables"
```

---

### Task 2: Matcher — Hybrid Match Algorithm

**Files:**
- Create: `src/enrichment/__init__.py`
- Create: `src/enrichment/matcher.py`
- Create: `tests/enrichment/__init__.py`
- Create: `tests/enrichment/test_matcher.py`

- [ ] **Step 1: Create module structure**

Create `src/enrichment/__init__.py` and `tests/enrichment/__init__.py` (empty files).

- [ ] **Step 2: Write tests for normalize_name**

Create `tests/enrichment/test_matcher.py`:

```python
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
        """High similarity + same type → auto-apply."""
        results = match_products(
            product_name="Shampoo Pos Quimica 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Shampoo Pós Química 350ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua", "Sodium"], "id": "ext-1", "source": "belezanaweb"},
            ],
        )
        assert len(results) == 1
        assert results[0]["action"] == "auto_apply"
        assert results[0]["score"] > 0.90

    def test_similar_match_review(self):
        """Medium similarity → review queue."""
        results = match_products(
            product_name="Shampoo Hidratação Bio Extratus 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Bio Extratus Shampoo Hidratação Intensa 300ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb"},
            ],
        )
        assert len(results) == 1
        assert results[0]["action"] == "review"

    def test_type_mismatch_goes_to_review(self):
        """High name match but type differs → review (not auto-apply)."""
        results = match_products(
            product_name="Bio Extratus Pos Quimica Shampoo 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Bio Extratus Pos Quimica Condicionador 350ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb"},
            ],
        )
        if results:
            assert results[0]["action"] == "review"

    def test_low_match_discarded(self):
        """Low similarity → discarded."""
        results = match_products(
            product_name="Shampoo Pos Quimica 350ml",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Oleo de Argan Leave-in 100ml", "brand_slug": "bio-extratus",
                 "inci_ingredients": ["Aqua"], "id": "ext-1", "source": "belezanaweb"},
            ],
        )
        assert len(results) == 0

    def test_no_inci_candidates_skipped(self):
        """Candidates without inci_ingredients are skipped."""
        results = match_products(
            product_name="Shampoo Test",
            product_brand="bio-extratus",
            candidates=[
                {"product_name": "Shampoo Test", "brand_slug": "bio-extratus",
                 "inci_ingredients": None, "id": "ext-1", "source": "belezanaweb"},
            ],
        )
        assert len(results) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/enrichment/test_matcher.py -v`

- [ ] **Step 4: Implement matcher**

Create `src/enrichment/matcher.py`:

```python
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Product type keywords (Portuguese + English)
PRODUCT_TYPES = {
    "shampoo": ["shampoo"],
    "condicionador": ["condicionador", "conditioner"],
    "mascara": ["mascara", "máscara", "mask", "masque"],
    "leave-in": ["leave-in", "leave in"],
    "creme": ["creme de pentear", "creme para pentear", "creme pentear"],
    "oleo": ["oleo", "óleo", "oil"],
    "spray": ["spray"],
    "serum": ["serum", "sérum"],
    "ampola": ["ampola", "ampoule"],
    "kit": ["kit"],
    "gel": ["gel", "gelatina", "geleia"],
    "finalizador": ["finalizador"],
}


def normalize_name(name: str) -> str:
    """Normalize product name for fuzzy comparison."""
    name = name.lower()
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    # Remove sizes: 300ml, 1kg, 500g, etc.
    name = re.sub(r"\b\d+[.,]?\d*\s*(ml|g|kg|l|oz|lt)\b", "", name)
    # Remove unit suffixes
    name = re.sub(r"\s*[-/]\s*(un|und|unid)\b", "", name)
    # Simplify kit patterns
    name = re.sub(r"\s*kit\s+com\s+\d+", "kit", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def detect_product_type(name: str) -> str | None:
    """Detect product type from name via keywords."""
    lower = name.lower()
    for ptype, keywords in PRODUCT_TYPES.items():
        for kw in keywords:
            if kw in lower:
                return ptype
    return None


def match_products(
    product_name: str,
    product_brand: str,
    candidates: list[dict],
    auto_threshold: float = 0.90,
    review_threshold: float = 0.75,
) -> list[dict]:
    """Match a product against external INCI candidates.

    Returns list of matches with action (auto_apply/review) and score.
    Candidates below review_threshold (0.75) are discarded.
    Note: spec architecture diagram says 0.50 but scoring table says 0.75.
    We use 0.75 (scoring table) as it is safer for PT-BR product names.
    """
    norm_name = normalize_name(product_name)
    product_type = detect_product_type(product_name)

    matches = []
    for cand in candidates:
        # Skip candidates without INCI
        if not cand.get("inci_ingredients"):
            continue

        cand_norm = normalize_name(cand["product_name"] or "")
        ratio = SequenceMatcher(None, norm_name, cand_norm).ratio()

        if ratio < review_threshold:
            continue

        cand_type = detect_product_type(cand["product_name"] or "")
        type_match = (
            product_type is None
            or cand_type is None
            or product_type == cand_type
        )

        # Determine action
        if ratio > auto_threshold and type_match:
            action = "auto_apply"
        elif ratio > auto_threshold and not type_match:
            action = "review"  # high name match but type differs
        else:
            action = "review"

        matches.append({
            "external_id": cand["id"],
            "source": cand["source"],
            "source_url": cand.get("source_url", ""),
            "score": ratio,
            "action": action,
            "type_match": type_match,
            "cand_name": cand["product_name"],
            "inci_ingredients": cand["inci_ingredients"],
        })

    # Sort by score desc, prefer belezanaweb on ties
    matches.sort(key=lambda m: (-m["score"], m["source"] != "belezanaweb"))
    return matches[:1]  # Return best match only
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/enrichment/test_matcher.py -v`

- [ ] **Step 6: Commit**

```bash
git add src/enrichment/ tests/enrichment/
git commit -m "feat: add hybrid match algorithm for external INCI enrichment"
```

---

### Task 3: Re-scrape Protection in Repository

**Files:**
- Modify: `src/storage/repository.py:20-50`
- Create: `tests/storage/test_upsert_protection.py`

- [ ] **Step 1: Write test**

Create `tests/storage/test_upsert_protection.py`:

```python
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from src.storage.repository import ProductRepository
from src.storage.orm_models import ProductORM


def test_upsert_preserves_external_inci_when_new_has_none(tmp_path):
    """When existing product has external INCI and new extraction has no INCI,
    the external INCI should be preserved."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.storage.orm_models import Base

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = ProductRepository(session)

        # Create product with external enrichment INCI
        product = ProductORM(
            id="test-123",
            brand_slug="bio-extratus",
            product_name="Shampoo Test",
            product_url="https://example.com/test",
            verification_status="verified_inci",
            inci_ingredients=["Aqua", "Sodium Laureth Sulfate"],
            extraction_method="external_enrichment",
            confidence=0.85,
            gender_target="all",
        )
        session.add(product)
        session.commit()

        # Simulate re-scrape with no INCI (catalog_only result)
        from src.core.models import ProductExtraction, QAResult, QAStatus, GenderTarget
        extraction = ProductExtraction(
            brand_slug="bio-extratus",
            product_name="Shampoo Test Updated",
            product_url="https://example.com/test",
            inci_ingredients=None,  # No INCI from official site
            confidence=0.30,
            extraction_method="jsonld",
        )
        qa = MagicMock()
        qa.status = QAStatus.CATALOG_ONLY

        repo.upsert_product(extraction, qa)
        session.commit()

        # Verify: INCI should be preserved, but name should be updated
        refreshed = session.query(ProductORM).filter_by(id="test-123").first()
        assert refreshed.inci_ingredients == ["Aqua", "Sodium Laureth Sulfate"]
        assert refreshed.verification_status == "verified_inci"
        assert refreshed.extraction_method == "external_enrichment"
        assert refreshed.product_name == "Shampoo Test Updated"  # Non-INCI fields update
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_upsert_protection.py -v`
Expected: FAIL — INCI gets overwritten.

- [ ] **Step 3: Implement protection**

In `src/storage/repository.py`, in `upsert_product()` update block. Insert AFTER line 35 (`existing.hair_relevance_reason = ...`) and BEFORE line 36 (`existing.inci_ingredients = ...`):

```python
            # Re-scrape protection: preserve externally-enriched INCI
            _preserve_inci = (
                existing.extraction_method == "external_enrichment"
                and existing.inci_ingredients
                and not extraction.inci_ingredients
            )
```

Then replace lines 30, 36, 47, 48 (the INCI-related fields) with conditional updates:

```python
            # Line 30: wrap verification_status
            if not _preserve_inci:
                existing.verification_status = qa.status.value
            # Line 36: wrap inci_ingredients
            if not _preserve_inci:
                existing.inci_ingredients = extraction.inci_ingredients
            # Lines 47-48: wrap confidence and extraction_method
            if not _preserve_inci:
                existing.confidence = extraction.confidence
                existing.extraction_method = extraction.extraction_method
```

All other fields (product_name, description, image, price, etc.) continue to update unconditionally.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/storage/test_upsert_protection.py -v`
Expected: PASS

- [ ] **Step 3: Run tests**

Run: `pytest tests/storage/test_upsert_protection.py -v`

- [ ] **Step 4: Commit**

```bash
git add src/storage/repository.py tests/storage/
git commit -m "feat: add re-scrape protection for externally-enriched INCI"
```

---

### Task 4: Source Scraper

**Files:**
- Create: `src/enrichment/source_scraper.py`
- Create: `config/blueprints/sources/belezanaweb.yaml`

- [ ] **Step 1: Create Beleza na Web blueprint**

Create `config/blueprints/sources/belezanaweb.yaml`:

```yaml
source_name: belezanaweb
source_slug: belezanaweb
platform: vtex
domain: www.belezanaweb.com.br
allowed_domains:
- www.belezanaweb.com.br
- belezanaweb.com.br
discovery:
  strategy: sitemap_first
  sitemap_urls:
  - https://www.belezanaweb.com.br/sitemap/product-0.xml
  - https://www.belezanaweb.com.br/sitemap/product-1.xml
  - https://www.belezanaweb.com.br/sitemap/product-2.xml
  product_url_pattern: ^https://www\.belezanaweb\.com\.br/[\w%-]+$
  max_pages: 5000
extraction:
  requires_js: false
  http_client: curl_cffi
  curl_cffi_impersonate: chrome
  delay_seconds: 3
  inci_selectors:
  - '[data-specification-name="Composição"] .vtex-product-specifications-1-x-specificationValue'
  - '[data-specification-name="Ingredientes"] .vtex-product-specifications-1-x-specificationValue'
  - '[data-specification-name="Composição"]'
  - '[data-specification-name="Ingredientes"]'
  name_selectors:
  - span.vtex-store-components-3-x-productBrand
  - h1
  image_selectors:
  - img.vtex-store-components-3-x-productImageTag
  section_label_map:
    ingredients_inci:
      labels:
      - ingredientes
      - composição
      - composicao
      - ingredients
      validators:
      - has_separators
      - min_length_30
  use_llm_fallback: false
brand_slug_map:
  bio-extratus: bio-extratus
  griffus: griffus
  lola-cosmetics: lola-cosmetics
  widi-care: widi-care
  aneethun: aneethun
  acquaflora: acquaflora
  brae: brae
  loccitane: loccitane
  alva: alva
  haskell: haskell
  salon-line: salon-line
```

- [ ] **Step 2: Implement source scraper**

Create `src/enrichment/source_scraper.py`:

```python
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from src.core.browser import BrowserClient
from src.discovery.product_discoverer import ProductDiscoverer
from src.extraction.deterministic import extract_product_deterministic
from src.extraction.inci_extractor import extract_and_validate_inci
from src.storage.orm_models import ExternalInciORM

logger = logging.getLogger("haira.enrichment.source_scraper")

SOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "blueprints" / "sources"


def load_source_blueprint(source_slug: str) -> dict | None:
    filepath = SOURCES_DIR / f"{source_slug}.yaml"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_brand_from_url(url: str, brand_slug_map: dict) -> str | None:
    """Detect brand slug from product URL using the brand_slug_map."""
    url_lower = url.lower()
    for url_segment, haira_slug in brand_slug_map.items():
        if url_segment.lower() in url_lower:
            return haira_slug
    return None


def scrape_source(
    session: Session,
    source_slug: str,
    brand_filter: str | None = None,
) -> dict:
    """Scrape an external source and save to external_inci table.

    Returns stats dict with counts.
    """
    bp = load_source_blueprint(source_slug)
    if not bp:
        raise ValueError(f"No source blueprint found for {source_slug}")

    brand_slug_map = bp.get("brand_slug_map", {})
    extraction_config = bp.get("extraction", {})

    # Setup browser
    http_client = extraction_config.get("http_client", "")
    ssl_verify = extraction_config.get("ssl_verify", True)
    if http_client == "curl_cffi":
        browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)
    else:
        browser = BrowserClient(use_httpx=True, ssl_verify=ssl_verify)

    # Discover URLs
    discoverer = ProductDiscoverer(browser=browser)
    discovered = discoverer.discover(bp)

    # Filter by brand if requested
    if brand_filter:
        discovered = [
            d for d in discovered
            if detect_brand_from_url(d.url, {brand_filter: brand_filter}) or
               brand_filter in d.url.lower()
        ]

    stats = {"discovered": len(discovered), "scraped": 0, "with_inci": 0, "skipped": 0}

    for disc_url in discovered:
        url = disc_url.url
        brand = detect_brand_from_url(url, brand_slug_map)
        if not brand:
            stats["skipped"] += 1
            continue
        if brand_filter and brand != brand_filter:
            stats["skipped"] += 1
            continue

        try:
            html = browser.fetch_page(url)
            if not html or len(html) < 500:
                continue

            det_result = extract_product_deterministic(
                html, url,
                inci_selectors=extraction_config.get("inci_selectors"),
                name_selectors=extraction_config.get("name_selectors"),
                image_selectors=extraction_config.get("image_selectors"),
                section_label_map=extraction_config.get("section_label_map"),
            )

            product_name = det_result.get("product_name")
            inci_raw = det_result.get("inci_raw")

            # Parse INCI
            inci_list = None
            if inci_raw:
                inci_result = extract_and_validate_inci(inci_raw, has_section_context=True)
                if inci_result.valid:
                    inci_list = inci_result.cleaned

            # Detect product type
            from src.enrichment.matcher import detect_product_type
            product_type = detect_product_type(product_name or "")

            # Upsert to external_inci
            existing = (
                session.query(ExternalInciORM)
                .filter(
                    ExternalInciORM.source == source_slug,
                    ExternalInciORM.source_url == url,
                )
                .first()
            )
            if existing:
                existing.product_name = product_name
                existing.product_type = product_type
                existing.inci_raw = inci_raw
                existing.inci_ingredients = inci_list
                existing.brand_slug = brand
                existing.updated_at = datetime.now(timezone.utc)
            else:
                record = ExternalInciORM(
                    source=source_slug,
                    source_url=url,
                    brand_slug=brand,
                    product_name=product_name,
                    product_type=product_type,
                    inci_raw=inci_raw,
                    inci_ingredients=inci_list,
                )
                session.add(record)

            stats["scraped"] += 1
            if inci_list:
                stats["with_inci"] += 1

            # Commit in batches
            if stats["scraped"] % 50 == 0:
                session.commit()
                logger.info(
                    "Progress: %d scraped, %d with INCI",
                    stats["scraped"], stats["with_inci"],
                )

        except Exception as e:
            logger.warning("Error scraping %s: %s", url, e)
            continue

    session.commit()
    return stats
```

- [ ] **Step 3: Verify import works**

Run: `python3 -c "from src.enrichment.source_scraper import scrape_source; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add src/enrichment/ config/blueprints/sources/
git commit -m "feat: add source scraper for external INCI enrichment"
```

---

### Task 5: CLI Commands

**Files:**
- Modify: `src/cli/main.py` (add after existing `enrich` command, line ~687)

- [ ] **Step 1: Add `source-scrape` command**

```python
@cli.command(name="source-scrape")
@click.option("--source", required=True, help="Source slug (e.g., belezanaweb)")
@click.option("--brand", default=None, help="Filter by brand slug")
def source_scrape(source: str, brand: str | None):
    """Scrape external source for INCI data."""
    from src.enrichment.source_scraper import scrape_source
    from src.storage.database import get_engine
    from src.storage.orm_models import Base
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    click.echo(f"Scraping source: {source}" + (f" (brand: {brand})" if brand else ""))

    with SASession(engine) as session:
        stats = scrape_source(session, source, brand_filter=brand)

    click.echo(f"\nResults:")
    click.echo(f"  Discovered: {stats['discovered']}")
    click.echo(f"  Scraped:    {stats['scraped']}")
    click.echo(f"  With INCI:  {stats['with_inci']}")
    click.echo(f"  Skipped:    {stats['skipped']}")
```

- [ ] **Step 2: Add `enrich-external` command**

```python
@cli.command(name="enrich-external")
@click.option("--brand", default=None, help="Filter by brand slug")
@click.option("--dry-run", is_flag=True, help="Show matches without applying")
@click.option("--threshold", type=float, default=0.90, help="Auto-apply threshold")
def enrich_external(brand: str | None, dry_run: bool, threshold: float):
    """Match catalog_only products with external INCI sources."""
    from src.enrichment.matcher import match_products
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductORM, ExternalInciORM, EnrichmentQueueORM
    from src.storage.repository import ProductRepository
    from src.core.models import ExtractionMethod
    from sqlalchemy.orm import Session as SASession
    import json

    engine = get_engine()
    Base.metadata.create_all(engine)

    with SASession(engine) as session:
        # Get catalog_only products
        query = session.query(ProductORM).filter(
            ProductORM.verification_status == "catalog_only"
        )
        if brand:
            query = query.filter(ProductORM.brand_slug == brand)
        products = query.all()

        click.echo(f"Found {len(products)} catalog_only products" +
                   (f" for {brand}" if brand else ""))

        auto_applied = 0
        queued = 0
        no_match = 0

        # Pre-load candidates by brand (avoid N+1 query per product)
        brand_slugs = {p.brand_slug for p in products}
        candidates_by_brand: dict[str, list[dict]] = {}
        for slug in brand_slugs:
            cands = (
                session.query(ExternalInciORM)
                .filter(
                    ExternalInciORM.brand_slug == slug,
                    ExternalInciORM.inci_ingredients.isnot(None),
                )
                .all()
            )
            candidates_by_brand[slug] = [
                {
                    "id": c.id,
                    "product_name": c.product_name,
                    "brand_slug": c.brand_slug,
                    "inci_ingredients": c.inci_ingredients,
                    "source": c.source,
                    "source_url": c.source_url,
                }
                for c in cands
            ]

        for product in products:
            cand_dicts = candidates_by_brand.get(product.brand_slug, [])

            if not cand_dicts:
                no_match += 1
                continue

            matches = match_products(
                product_name=product.product_name or "",
                product_brand=product.brand_slug,
                candidates=cand_dicts,
                auto_threshold=threshold,
            )

            if not matches:
                no_match += 1
                continue

            best = matches[0]

            if dry_run:
                click.echo(
                    f"  [{best['action']}] {product.product_name[:50]} "
                    f"↔ {best['cand_name'][:50]} (score={best['score']:.2f})"
                )
                if best["action"] == "auto_apply":
                    auto_applied += 1
                else:
                    queued += 1
                continue

            if best["action"] == "auto_apply":
                # Apply INCI
                product.inci_ingredients = best["inci_ingredients"]
                product.verification_status = "verified_inci"
                product.confidence = 0.85
                product.extraction_method = ExtractionMethod.EXTERNAL_ENRICHMENT.value
                # Create evidence row for audit trail (REQUIRED by spec)
                from src.storage.orm_models import ProductEvidenceORM
                evidence = ProductEvidenceORM(
                    product_id=product.id,
                    field_name="inci_ingredients",
                    source_url=best.get("source_url", ""),
                    selector=f"external_enrichment:{best['source']}",
                    raw_value=str(best["inci_ingredients"])[:500],
                    extraction_method=ExtractionMethod.EXTERNAL_ENRICHMENT.value,
                    confidence=0.85,
                )
                session.add(evidence)
                auto_applied += 1
            else:
                # Enqueue for review
                queue_entry = EnrichmentQueueORM(
                    product_id=product.id,
                    external_inci_id=best["external_id"],
                    match_score=best["score"],
                    match_details={
                        "name_ratio": best["score"],
                        "type_match": best["type_match"],
                        "cand_name": best["cand_name"],
                    },
                )
                session.add(queue_entry)
                queued += 1

        if not dry_run:
            session.commit()

        click.echo(f"\nResults:")
        click.echo(f"  Auto-applied: {auto_applied}")
        click.echo(f"  Queued:       {queued}")
        click.echo(f"  No match:     {no_match}")
```

- [ ] **Step 3: Verify commands work**

Run: `python3 -m src.cli.main source-scrape --help`
Run: `python3 -m src.cli.main enrich-external --help`

- [ ] **Step 4: Commit**

```bash
git add src/cli/main.py
git commit -m "feat: add source-scrape and enrich-external CLI commands"
```

---

### Task 6: End-to-End Test with Beleza na Web

**Files:** CLI commands only

- [ ] **Step 1: Test source-scrape with one brand**

Run: `haira source-scrape --source belezanaweb --brand bio-extratus`

Expected: Discovers products, scrapes, reports stats.

- [ ] **Step 2: Check external_inci table**

```python
python3 -c "
from src.storage.database import get_engine
from src.storage.orm_models import ExternalInciORM
from sqlalchemy.orm import Session
engine = get_engine()
with Session(engine) as s:
    count = s.query(ExternalInciORM).filter(ExternalInciORM.brand_slug=='bio-extratus').count()
    with_inci = s.query(ExternalInciORM).filter(ExternalInciORM.brand_slug=='bio-extratus', ExternalInciORM.inci_ingredients.isnot(None)).count()
    print(f'Bio Extratus: {count} total, {with_inci} with INCI')
"
```

- [ ] **Step 3: Test enrich-external dry-run**

Run: `haira enrich-external --brand bio-extratus --dry-run`

Expected: Shows matches with scores, actions (auto_apply/review).

- [ ] **Step 4: Apply enrichment**

Run: `haira enrich-external --brand bio-extratus`

Expected: Auto-applies high-confidence matches, queues uncertain ones.

- [ ] **Step 5: Verify results**

Run: `haira audit-inci --brand bio-extratus`

Expected: INCI rate should have improved from 0%.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: external INCI enrichment - verified with Bio Extratus"
```

---

### Task 7: Batch Enrichment for All Target Brands

**Files:** CLI commands only

- [ ] **Step 1: Source-scrape for remaining brands**

Run sequentially:
```bash
haira source-scrape --source belezanaweb --brand griffus
haira source-scrape --source belezanaweb --brand lola-cosmetics
haira source-scrape --source belezanaweb --brand widi-care
haira source-scrape --source belezanaweb --brand aneethun
haira source-scrape --source belezanaweb --brand acquaflora
haira source-scrape --source belezanaweb --brand brae
haira source-scrape --source belezanaweb --brand alva
haira source-scrape --source belezanaweb --brand loccitane
```

- [ ] **Step 2: Dry-run enrichment for all**

```bash
haira enrich-external --dry-run
```

Review the output. Check for false positive matches.

- [ ] **Step 3: Apply enrichment**

```bash
haira enrich-external
```

- [ ] **Step 4: Run audit and compare**

```bash
haira audit-inci
```

Compare with baseline. Target: >80% of catalog_only products enriched.

- [ ] **Step 5: Upload to production**

Use the migration endpoint or `haira source-scrape` + `haira enrich-external` on production via admin scrape endpoint.
