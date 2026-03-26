# External INCI Enrichment — Design Spec

**Date:** 2026-03-26
**Goal:** Fill INCI gaps for catalog_only products by scraping external sources (Beleza na Web, Epoca Cosmeticos) and cross-referencing with existing products.
**Approach:** Two-phase pipeline: source-scrape (populate external_inci) then enrich (match and apply). Data strictly separated — external data never mixes with official scrape data.

---

## Architecture Overview

```
haira source-scrape --source belezanaweb --brand bio-extratus
         |
         v
   [external_inci table]  ← Separate from products table
         |
haira enrich --brand bio-extratus
         |
    Match hybrid:
    1. Filter by brand_slug
    2. Fuzzy match product name (difflib, ratio > 0.75)
    3. Validate product type (shampoo↔shampoo)
    4. Score: >0.90 auto-apply, 0.50-0.90 review queue, <0.50 discard
         |
         v
   [products table]  ← INCI applied with source=external_enrichment
   [enrichment_queue] ← Uncertain matches for review
```

---

## Section 1: External Source Scraper

### New module: `src/enrichment/`

- `src/enrichment/source_scraper.py` — Scrapes external sources, saves to `external_inci`
- `src/enrichment/matcher.py` — Match hybrid algorithm
- `config/blueprints/sources/belezanaweb.yaml` — Blueprint for Beleza na Web
- `config/blueprints/sources/epocacosmeticos.yaml` — Blueprint for Epoca (Phase 2)

### Beleza na Web Blueprint

- Platform: VTEX
- Domain: belezanaweb.com.br
- Discovery: sitemap + brand filter (e.g., `/bio-extratus/`, `/griffus/`)
- INCI location: VTEX product specifications — `[data-specification-name="Composicao"]` or `[data-specification-name="Ingredientes"]`
- Extraction: same deterministic pipeline, but saves to `external_inci` instead of `products`
- Rate limiting: 3 second delay between requests (same as brand scrapes)

### Brand Slug Mapping

Source blueprints include a `brand_slug_map` that maps external URL segments to HAIRA brand slugs:

```yaml
brand_slug_map:
  bio-extratus: bio-extratus
  griffus: griffus
  lola-cosmetics: lola-cosmetics
  widi-care: widi-care
  # External slug → HAIRA slug (when they differ)
```

Discovery filters URLs by matching brand segment in the URL path against this map.

### INCI Parsing During Source-Scrape

Raw INCI text extracted from external source goes through `extract_and_validate_inci()` (same as main pipeline). Results:
- If valid: store both `inci_raw` and parsed `inci_ingredients` list
- If invalid: store `inci_raw` only, set `inci_ingredients` to null (product still saved for potential manual review)

### CLI Command

```
haira source-scrape --source belezanaweb [--brand <slug>]
```

- If `--brand` provided, filter discovery to that brand's products only
- Saves to `external_inci` table (never to `products`)
- Upserts by `source + source_url` (re-scrape safe)

---

## Section 2: Data Model

### Table: `external_inci`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| source | String(50) | "belezanaweb" or "epocacosmeticos" |
| source_url | Text | Product URL on external source |
| brand_slug | String(255) | Normalized brand slug |
| product_name | Text | Product name as found on external source |
| product_type | String(100) | Detected type (shampoo, condicionador, etc.) |
| inci_raw | Text | Raw INCI text as scraped |
| inci_ingredients | JSON | Parsed list of ingredients |
| ean | String(50) | Barcode if available (nullable, often not exposed in VTEX HTML) |
| scraped_at | DateTime | When scraped |
| updated_at | DateTime | Last update (for re-scrape tracking) |

Unique constraint: `(source, source_url)`
Index on: `brand_slug`

### Table: `enrichment_queue`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| product_id | String(36) | FK to products.id |
| external_inci_id | String(36) | FK to external_inci.id |
| match_score | Float | 0.0 to 1.0 |
| match_details | JSON | {name_ratio, type_match, brand_match} |
| status | String(20) | pending / approved / rejected |
| reviewed_by | String(100) | Nullable |
| created_at | DateTime | |

---

## Section 3: Match Hybrid Algorithm

### Input
- Product from `products` table (status=catalog_only, brand_slug=X)
- Candidates from `external_inci` (brand_slug=X)

### Steps

**3a. Name normalization:**
```python
import re
import unicodedata

def normalize_name(name: str) -> str:
    # 1. lowercase
    name = name.lower()
    # 2. strip accents (unicodedata NFD + strip combining chars)
    name = ''.join(c for c in unicodedata.normalize('NFD', name)
                   if unicodedata.category(c) != 'Mn')
    # 3. remove sizes: 300ml, 1kg, 500g, 1l, 250ml, etc.
    name = re.sub(r'\b\d+[.,]?\d*\s*(ml|g|kg|l|oz|lt)\b', '', name)
    # 4. remove common suffixes
    name = re.sub(r'\s*[-/]\s*(un|und|unid)\b', '', name)
    name = re.sub(r'\s*kit\s+com\s+\d+', 'kit', name)
    # 5. collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name
```

**3b. Fuzzy match:**
- `difflib.SequenceMatcher(None, norm_a, norm_b).ratio()`
- No external dependencies (stdlib only)

**3c. Product type detection:**
- Extract type from name via keyword map:
  - shampoo, condicionador, mascara/máscara, leave-in, creme de pentear, oleo/óleo, spray, serum/sérum, ampola, kit
- Both sides must have same type (or one side has no detected type → accept)

**3d. Scoring:**
| Name ratio | Type match | Action |
|-----------|------------|--------|
| > 0.90 | Yes or N/A | **Auto-apply** (confidence 0.85) |
| 0.75 - 0.90 | Yes or N/A | **Enqueue for review** |
| > 0.90 | No | **Enqueue for review** (name matches but type differs — needs human) |
| < 0.75 | Any | **Discard** |

**3e. Tiebreaker:** If multiple candidates match, pick highest ratio. If tied, prefer Beleza na Web over Epoca.

### When auto-applying:
- Set `product.inci_ingredients` from `external_inci.inci_ingredients`
- Set `product.verification_status` to `verified_inci`
- Set `product.confidence` to 0.85
- Set `product.extraction_method` to `external_enrichment`
- Create `product_evidence` row with `extraction_method="external_enrichment"`, `source_url` from external source

### Re-scrape protection (CRITICAL):

**Problem:** `upsert_product()` in `repository.py` overwrites ALL fields including `inci_ingredients`. If a brand is re-scraped and the official site has no INCI, the externally-enriched INCI would be wiped.

**Solution:** Modify `upsert_product()` to skip overwriting `inci_ingredients` when:
1. The existing product has `extraction_method == "external_enrichment"` AND
2. The new extraction has no INCI (`inci_ingredients` is null/empty)

This means: official scrape with INCI always wins, official scrape without INCI preserves external enrichment, and external enrichment only applies to products without official INCI.

**Priority chain:** official_scrape_with_inci (0.90) > external_enrichment (0.85) > llm_fallback (0.85) > no_inci (catalog_only)

### ExtractionMethod enum update:

Add `EXTERNAL_ENRICHMENT = "external_enrichment"` to `ExtractionMethod` enum in `src/core/models.py`.

### CLI name collision:

The existing `haira enrich` command does LLM-based enrichment. Rename external enrichment to:
```
haira enrich-external [--brand <slug>] [--dry-run] [--threshold 0.90]
```

The existing `haira enrich` remains unchanged for LLM enrichment.

---

## Section 4: CLI Commands

### `haira source-scrape`

```
haira source-scrape --source belezanaweb [--brand <slug>]
```

Flow:
1. Load source blueprint from `config/blueprints/sources/{source}.yaml`
2. If `--brand` specified, filter product URLs by brand
3. Run discovery + extraction (reuse existing pipeline)
4. Save to `external_inci` table (upsert by source+source_url)
5. Report: "Scraped X products, Y with INCI"

### `haira enrich-external`

```
haira enrich-external [--brand <slug>] [--dry-run] [--threshold 0.90]
```

Flow:
1. Get `catalog_only` products (optionally filtered by brand)
2. For each, query `external_inci` candidates (same brand)
3. Run match hybrid algorithm
4. Auto-apply high-confidence matches
5. Enqueue medium-confidence matches
6. Report: "Enriched X products, Y queued for review, Z no match"

`--dry-run` shows matches without applying.
`--threshold` overrides auto-apply threshold (default 0.90).

---

## Section 5: Implementation Phases

### Phase 1: Beleza na Web (this spec)
- `external_inci` table + migration
- `enrichment_queue` table + migration
- Source scraper for Beleza na Web
- Match hybrid algorithm
- `haira source-scrape` + `haira enrich` commands
- Target brands: Bio Extratus, Aneethun, Griffus, Widi Care, Lola Cosmetics, Acquaflora, Brae, L'Occitane, Alva

### Phase 2: Epoca Cosmeticos (future)
- Add `epocacosmeticos` source blueprint
- Run as fallback for products not found on Beleza na Web

### Out of scope
- Ops panel for enrichment queue review (use CLI `--dry-run` for now)
- CosIng INCI name normalizer
- INCIDecoder scraping
- Auto-enrichment on scrape (manual trigger only)

---

## Success Criteria

- Cover >80% of `catalog_only` products for the 9 target brands
- Zero false positives in auto-apply (>90% match threshold)
- Clear audit trail: every externally-sourced INCI has evidence with source URL
- External data cleanly separated in `external_inci` table
