# Haira Data — Design Specification

**Date:** 2026-03-13
**Status:** Approved
**Scope:** Evolution of the existing Haira platform into a full hair product knowledge base

---

## 1. Overview

Haira Data transforms the existing scraping tool into a reliable, auditable knowledge base for hair products. The core priorities are **data quality** and **deduplication** — no duplicate products from casing differences, no wrong fields, no untracked changes.

**Key principle:** Evolution in-place. No separate repo or module. New tables coexist with existing JSON columns for backwards compatibility.

## 2. Architecture

### Pipeline Flow

```
Discovery → Extraction → Dual Validation → QA Gate → Label Detection → Storage
                              ↓
                        Review Queue (divergences)
```

### Components

- **Platform Adapters** (`src/discovery/platform_adapters/`) — Per-platform logic. Currently: `base.py`, `sitemap.py`, `dom_crawler.py`. Planned: dedicated adapters for VTEX, Shopify, L'Oréal stack, Grupo Boticário. Handle sitemaps, DOM crawling, WAF bypass.
- **Semi-auto Blueprints** (`config/blueprints/{slug}.yaml`) — YAML configs per brand defining platform type, selectors, extraction settings. Generated semi-automatically from platform adapter + manual tuning.
- **Dual Validation** — Two independent extractions compared automatically. Divergences go to review queue, not directly to catalog.
- **Evidence Trail** — Every extracted field tracked via `ProductEvidenceORM` with method, selector, and original value.

### Processing Model

- **Marca a marca** — One brand at a time, fully validated before moving to next.
- **Cadence:** 5 brands / 2 days target (complex brands with WAF or custom DOM may take longer).
- **Tier 1 first** — Brands with complete ingredient data on their sites.

## 3. Database Schema

### Existing Tables (preserved as-is)

| Table | Purpose |
|-------|---------|
| `products` | Core product data with JSON columns (inci_ingredients, benefits_claims, etc.) |
| `product_evidence` | Provenance tracking per extracted field |
| `quarantine_details` | Failed QA check records |
| `brand_coverage` | Coverage snapshots per brand |

### New Normalized Tables

#### Ingredients

```sql
-- Canonical ingredient registry
CREATE TABLE ingredients (
    id UUID PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,  -- e.g. "Dimethicone"
    inci_name TEXT,                        -- official INCI name
    cas_number TEXT,
    category TEXT,                         -- silicone, surfactant, preservative, etc.
    safety_rating TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Aliases for deduplication
CREATE TABLE ingredient_aliases (
    id UUID PRIMARY KEY,
    ingredient_id UUID REFERENCES ingredients(id),
    alias TEXT NOT NULL,                   -- e.g. "DIMETHICONE", "Dimeticone", "Dimeticonol"
    language TEXT DEFAULT 'en',            -- pt, en, inci
    UNIQUE(alias)
);

-- Product ↔ Ingredient junction
CREATE TABLE product_ingredients (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    ingredient_id UUID REFERENCES ingredients(id),
    position INTEGER,                      -- order in INCI list (1 = highest concentration)
    raw_name TEXT,                          -- original name as scraped
    validation_status TEXT DEFAULT 'raw',   -- raw, auto_validated, dual_validated, needs_review, manually_verified
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(product_id, ingredient_id)
);
```

#### Claims & Labels

```sql
-- Canonical claims registry
CREATE TABLE claims (
    id UUID PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,   -- e.g. "sulfate_free"
    display_name TEXT,                     -- "Sulfate Free"
    category TEXT,                         -- seal, benefit, warning
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE claim_aliases (
    id UUID PRIMARY KEY,
    claim_id UUID REFERENCES claims(id),
    alias TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    UNIQUE(alias)
);

CREATE TABLE product_claims (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    claim_id UUID REFERENCES claims(id),
    source TEXT,                           -- 'keyword', 'inci_inference', 'manual'
    confidence_score FLOAT,               -- numeric confidence (0.0-1.0), distinct from validation_status
    evidence_text TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(product_id, claim_id)
);
```

#### Images

```sql
CREATE TABLE product_images (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    url TEXT NOT NULL,
    image_type TEXT DEFAULT 'gallery',     -- main, gallery, swatch, ingredient_list
    position INTEGER,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### Compositions

```sql
-- Multi-section compositions (complements ProductORM.composition which stores single text)
-- During dual-write: ProductORM.composition = concatenation of all sections; this table = structured view
CREATE TABLE product_compositions (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    section_label TEXT,                    -- "Composição", "Fórmula"
    content TEXT NOT NULL,
    source_selector TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### Validation

```sql
-- Dual-pass comparison records
CREATE TABLE validation_comparisons (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    field_name TEXT NOT NULL,
    pass_1_value TEXT,
    pass_2_value TEXT,
    resolution TEXT,                       -- 'auto_matched', 'human_resolved', 'pending'
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Review queue for divergences
CREATE TABLE review_queue (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    comparison_id UUID REFERENCES validation_comparisons(id),
    field_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',         -- pending, approved, rejected
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);
```

### Migration Strategy

- New tables added via Alembic migrations
- Existing JSON columns (`inci_ingredients`, `benefits_claims`, etc.) preserved
- Dual-write: pipeline writes to both JSON columns and normalized tables
- Normalized tables become source of truth once validated

## 4. Scraping Strategy

### Platform Adapters

**Existing** (`src/discovery/platform_adapters/`): `base.py`, `sitemap.py`, `dom_crawler.py`

**Planned** (to be built as brands require them):

| Platform | Adapter | Discovery | Notes |
|----------|---------|-----------|-------|
| VTEX IO | `vtex_adapter.py` | Sitemap + DOM crawling | Akamai WAF on some stores |
| VTEX Classic | `vtex_adapter.py` | Sitemap XML | Simpler HTML structure |
| Shopify | `shopify_adapter.py` | `/products.json` API + sitemap | JSON API preferred |
| WooCommerce | `woo_adapter.py` | Sitemap XML | Standard WordPress |
| L'Oréal stack | `loreal_adapter.py` | Custom sitemap patterns | Shared across L'Oréal brands |
| Grupo Boticário | `boticario_adapter.py` | DOM crawling | Headed browser required |

### Blueprint Structure

```yaml
brand_slug: "o-boticario"
platform: "vtex_io"
domains: ["www.boticario.com.br"]

discovery:
  strategy: "dom_crawler"
  seed_urls: [...]
  link_pattern: "boticario.com.br/.*/p$"

extraction:
  headless: false          # WAF bypass
  delay_seconds: 6
  wait_for_selector: ".accordion-pdp-header"
  expand_accordions: true
  name_selectors: ["h1.product-name"]
  inci_selectors: []       # Uses tab-label heuristic
  section_label_map:
    composição: composition
    ingredientes: ingredients_inci_raw
    modo de uso: care_usage
    detalhes: description
```

### Extraction Hierarchy

1. **JSON-LD** (`@type: Product`) — product name, price, image, description
2. **Blueprint CSS selectors** — targeted selectors per brand
3. **Section classifier** — heading-based extraction with `section_label_map`
4. **Tab-label heuristic** — accordion/tab content matched by label text
5. **BeautifulSoup fallback** — generic HTML parsing

### WAF Handling

- **Detection:** 403 responses, empty pages, CAPTCHA presence
- **Mitigation:** Headed browser, realistic user-agent, anti-webdriver scripts, rate limiting
- **Recovery:** Browser auto-restart on crash, retry with exponential backoff

## 5. Operational Cycles

### Brand Processing Flow

```
1. Register brand (brands.json)
2. Create/generate blueprint (config/blueprints/{slug}.yaml)
3. Discovery: crawl URLs → data/{slug}_all_urls.txt
4. Test extraction: 5 URLs → verify selectors and INCI capture
5. Full extraction: all URLs → DB with evidence
6. QA gate: verify/quarantine/catalog-only
7. Label detection: haira labels --brand {slug}
8. Data quality audit: coverage report
9. Fix issues, re-extract if needed
10. Mark brand complete, move to next
```

### Cadence

- **Target:** 5 brands every 2 days
- **Reality check:** Complex brands (WAF, custom DOM) take longer
- **Priority:** Tier 1 (Marcas Principais with ingredients) first

### Current Progress

| # | Brand | Status | Products | INCI Rate |
|---|-------|--------|----------|-----------|
| 1 | Amend | Complete | 700 (270+430 kits) | 89.9% (629/700) |
| 2 | O Boticário | Complete | 145 | 98.6% (143/145) |
| 3 | Eudora | Queue | — | — |
| 4 | L'Occitane au Brésil | Queue | — | — |
| 5 | Mustela | Queue | — | — |
| 6 | Avatim | Queue | — | — |
| 7 | Granado | Queue | — | — |
| 8+ | Johnson's Baby, L'Oréal Pro, Redken... | Queue | — | — |

## 6. Dual Validation

### Process

1. **Pass 1:** Standard extraction (JSON-LD + selectors + heuristics)
2. **Pass 2:** Independent re-extraction (different selector priority or LLM-assisted)
3. **Comparison:** Field-by-field diff of both passes
4. **Resolution:**
   - All fields match → `auto_validated`, goes to catalog
   - Minor divergences (whitespace, casing) → `auto_validated` with normalization
   - Significant divergences → `needs_review`, enters review queue

### Confidence Levels

| Level | Meaning |
|-------|---------|
| `raw` | Single extraction, not yet validated |
| `auto_validated` | Dual pass matched or minor diff auto-resolved |
| `dual_validated` | Dual pass matched with high confidence |
| `needs_review` | Divergences detected, human review needed |
| `manually_verified` | Human confirmed via review queue |

### Fields Compared

- `product_name` — exact match after normalization
- `inci_ingredients` — ordered list comparison with fuzzy matching for ingredient names
- `price` — numeric comparison (tolerance ±1%)
- `description` — similarity score (>90% = match)
- `composition` — similarity score
- `care_usage` — similarity score
- `image_url_main` — URL comparison

### Integration with Pipeline

- **Module:** `src/core/dual_validator.py` — comparison logic, diff engine, auto-resolution rules
- **CLI:** `haira validate --brand <slug>` — runs Pass 2 on already-extracted products
- **Flow in CoverageEngine:**
  1. `haira scrape --brand <slug>` runs Pass 1 (standard extraction), saves with `validation_status='raw'`
  2. `haira validate --brand <slug>` runs Pass 2 (re-extraction with different selector priority), compares fields, writes `validation_comparisons` rows
  3. Matches → `validation_status='auto_validated'`; divergences → `review_queue` with `status='pending'`
- Pass 2 reuses `_extract_product()` but shuffles selector priority (e.g., section classifier first, JSON-LD second) to test extraction robustness
- Dual validation is a separate step, not inline with scrape — allows running Pass 1 for all URLs first, then batch validation

### Quarantine vs Review Queue

These are complementary systems:
- **`quarantine_details`** — QA gate failures (missing name, invalid INCI, failed checks). Existing system.
- **`review_queue`** — Dual validation divergences (Pass 1 ≠ Pass 2). New system.
- Both visible in the Quarantine Review page, with a tab/filter to distinguish source.

## 7. Interface (Operational)

### Priority: Monitor & Review

The interface focuses on operational needs first:

1. **Pipeline Monitor** — Real-time view of extraction cycles: brand being processed, progress, errors, success rate
2. **Review Queue** — Dual validation divergences for human resolution: side-by-side comparison, approve/reject/edit
3. **Quality Dashboard** — Per-brand coverage metrics: INCI rate, field completeness, quarantine rate, trend over time
4. **Brand Management** — Status of each brand in pipeline, blueprint config, re-extraction triggers

### Existing Pages (enhanced)

- **Dashboard** — Add pipeline status widget, brand progress overview
- **Product Browser** — Add normalized ingredient view, evidence trail
- **Quarantine Review** — Already exists, enhance with dual validation context

### New API Routes (planned)

| Route | Module | Purpose |
|-------|--------|---------|
| `GET /api/ingredients` | `routes/ingredients.py` | List/search canonical ingredients |
| `GET /api/products/{id}/ingredients` | `routes/products.py` | Normalized ingredient list for a product |
| `GET /api/review-queue` | `routes/quarantine.py` | List pending dual validation divergences |
| `POST /api/review-queue/{id}/resolve` | `routes/quarantine.py` | Resolve a review queue item |
| `GET /api/validation/{product_id}` | `routes/products.py` | View comparison results for a product |

Corresponding Pydantic response models must be added to `src/core/models.py` (e.g., `Ingredient`, `Claim`, `ValidationComparison`, `ReviewQueueItem`).

### Future (exploratory)

- Ingredient explorer (search across all products by ingredient)
- Claim analytics (which brands have most vegan/sulfate-free products)
- Cross-brand comparison tools

## 8. Anti-Failure Plan

### 8.1 Extraction Resilience

- **Rate limiting adaptativo** — Base delay per blueprint (3-6s), exponential backoff on 429/503
- **Browser auto-restart** — Playwright restarts after WAF-induced crashes (already implemented)
- **Retry with circuit breaker** — 3 attempts per URL; if >30% fail for a brand, auto-pause
- **Checkpointing** — Progress saved per URL; reruns skip already-extracted products (upsert by URL)

### 8.2 Data Integrity

- **Dual validation** — Two independent extractions compared; divergences go to review queue
- **Evidence trail** — Each extracted field has `ProductEvidenceORM` with method, selector, original value
- **Quarantine gate** — Products with inconsistent data stay quarantined, never enter active catalog
- **Schema constraints** — UUID PKs, foreign keys, unique constraints on product_url+brand_slug

### 8.3 Operational Monitoring

- **BrandCoverageORM** — Coverage snapshot per brand after each cycle
- **Threshold alerts** — If INCI rate drops below 80% on a brand that was 95%+, flag for review
- **Structured logging** — Each extraction logged with timestamp, method, errors

### 8.4 Recovery

- **Backup before re-extraction** — Snapshot current state before running new cycle
- **Rollback per brand** — Can revert an entire brand to previous state
- **Immutable evidence** — Evidence records never deleted, only appended
- **Git-tracked configs** — Blueprints and label configs versioned, changes traceable

### 8.5 Scalability

- **Brand-by-brand** — Sequential processing avoids overloading target sites
- **5 brands / 2 days** — Sustainable pace with time for manual QA between brands
- **Reusable blueprints** — Brands on same platform share adapter, only selectors change

---

## Implementation Notes

### Dependencies

- Python 3.12+, FastAPI, SQLAlchemy, Alembic, Playwright, BeautifulSoup4
- React 19, TypeScript, Vite, Tailwind CSS 4, Recharts

### Environment

- SQLite for development, PostgreSQL for production (via `DATABASE_URL`)
- Playwright requires system-level browser install (`playwright install chromium`)

### ORM Implementation Notes

- All timestamps use Python-level defaults (SQLAlchemy `_utcnow()` pattern) for SQLite/PostgreSQL compatibility — not SQL `NOW()`
- Alias uniqueness: `UNIQUE(alias)` on `ingredient_aliases` is intentional — one canonical name per alias globally. Conflicts resolved during seeding by human review.
- New ORM models in `src/storage/orm_models.py`, Pydantic models in `src/core/models.py`
- Dual-write logic in a new `src/storage/normalized_writer.py` service — keeps `ProductRepository` focused on the existing product table

### Ingredient Seeding Strategy

1. Parse existing `inci_ingredients` JSON arrays from all products in DB
2. Normalize casing (title case) and strip whitespace
3. Group by normalized name → each group becomes one canonical ingredient
4. Portuguese names (from O Boticário) get alias entries with `language='pt'`
5. CAS numbers and safety ratings populated later from external reference data
6. Manual review for ambiguous cases (e.g., short names that could match multiple ingredients)

### Migration Order

1. Create new normalized tables (ingredients, claims, images, compositions, validation)
2. Populate canonical ingredient glossary (seed from existing INCI data)
3. Add dual-write to pipeline — incrementally:
   a. First: ingredients only (`product_ingredients`)
   b. Then: claims (`product_claims`)
   c. Then: images (`product_images`)
   d. Then: compositions (`product_compositions`)
4. Build review queue UI
5. Migrate historical data from JSON columns to normalized tables
6. Add pipeline monitor and quality dashboard widgets
