# HAIRA v2 Design Document

**Date:** 2026-02-24
**Status:** Approved

## Overview

HAIRA v2 is a hair product intelligence platform that discovers, extracts, validates, and serves verified hair/scalp product data (INCI ingredients, usage, benefits, metadata, images) from ~700 Brazilian + international brands. It prioritizes truth over volume: official sources only, evidence per field, stop-the-line quality gates.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pipeline model | Sequential CLI (Phase 1-3), async-within-brand later | Rate limiting is the bottleneck, not parallelism. Correctness > speed. |
| DB locally | SQLite for dev, Postgres for prod | Same SQLAlchemy models, env-driven via DATABASE_URL |
| Browser | Playwright sync API | Simpler for sequential pipeline |
| LLM | Anthropic Claude via `anthropic` SDK | Structured outputs, grounded extraction |
| Config | YAML blueprints per brand + JSON registry | |
| Frontend | React + TS + Tailwind + Vite (Phase 3) | |

## Data Flow

```
Excel ("Lista de Produtos.xlsx")
  -> Registry Loader -> config/brands.json (706 brands)
  -> Blueprint Engine -> config/blueprints/{slug}.yaml
  -> Coverage Engine (per brand):
       1. Discovery (Platform API > Sitemap > Category crawl > DOM)
       2. Classification (hair / non-hair / kit)
       3. Extraction (JSON-LD > selectors > JS DOM > LLM grounded)
       4. INCI Validation (clean, cut markers, dedup, concat/repeat detection)
       5. QA Gate (catalog_only / verified_inci / quarantine)
       6. Storage + Coverage Report
```

## Database Schema

### products
- id (UUID PK)
- brand_slug (VARCHAR, indexed)
- product_name (VARCHAR NOT NULL)
- product_url (VARCHAR UNIQUE NOT NULL) -- canonical
- image_url_main, image_urls_gallery (JSONB)
- verification_status (ENUM: catalog_only, verified_inci, quarantined)
- product_type_raw, product_type_normalized
- gender_target (ENUM: men, women, unisex, kids, unknown)
- hair_relevance_reason (TEXT)
- inci_ingredients (JSONB, nullable)
- description, usage_instructions (TEXT nullable)
- benefits_claims (JSONB nullable)
- size_volume, price, currency, line_collection
- variants (JSONB)
- confidence (FLOAT)
- extraction_method (VARCHAR)
- extracted_at, created_at, updated_at

### product_evidence
- id (UUID PK)
- product_id (FK products)
- field_name, source_url, evidence_locator, raw_source_text
- extraction_method (ENUM: jsonld, html_selector, js_dom, llm_grounded, manual)
- extracted_at

### quarantine_details
- id (UUID PK)
- product_id (FK products UNIQUE)
- rejection_reason, rejection_code
- review_status (ENUM: pending, approved, rejected)
- reviewer_notes, reviewed_at

### brand_coverage
- id (UUID PK)
- brand_slug (UNIQUE)
- discovered_total, hair_total, kits_total, non_hair_total
- extracted_total, verified_inci_total, verified_inci_rate
- catalog_only_total, quarantined_total
- status (ENUM: active, needs_review, blocked, done)
- last_run, blueprint_version, coverage_report (JSONB)

## Module Architecture

```
src/
  core/           models, browser, llm, inci_validator, qa_gate, taxonomy
  registry/       excel_loader
  discovery/      product_discoverer, platform_adapters/, url_classifier
  extraction/     deterministic, inci_extractor, product_extractor, evidence_tracker
  pipeline/       coverage_engine, cost_tracker, report_generator
  storage/        database, orm_models, repository, migrations/
  api/            main, routes/
  cli/            main
```

## INCI Validation Pipeline

1. Locate INCI section (JSON-LD > selector > LLM)
2. Extract raw text between INCI heading and first cut marker
3. Remove garbage phrases
4. Split by comma
5. Per-ingredient validation (length 2-80, no URLs, no verbs, max 8 words)
6. Deduplication (case-insensitive)
7. Concatenation detection (multiple Aqua/Water, product headings)
8. Repetition detection (repeated subsequences)
9. Minimum 5 valid terms
10. Output: cleaned list OR null

## QA Gate

### Per-product (catalog_only minimum)
- product_name not garbage
- product_url reachable and in allowlist
- at least 1 image_url
- hair_related=true with reason+evidence

### Per-product (verified_inci full)
- all above + type_normalized in HAIR_PRODUCT_TYPES
- inci >= 5 valid terms after cleaning
- INCI deep clean passes
- no duplicates, no repeated blocks, no concatenation
- evidence exists with raw snippet
- confidence >= 0.80

### Per-brand
- coverage report generated
- verified_inci_rate >= 0.60 (configurable)
- if failure_rate > 50% -> halt -> needs_review

## Cost Control

- MAX_LLM_CALLS_PER_BRAND default 50
- LLM used only for: blueprint gen, ambiguous hair classification, extraction fallback
- Budget exceeded -> stop, save progress, mark needs_review

## Implementation Phases

1. Foundation: scaffold, DB, registry loader, blueprint engine, deterministic extraction
2. Core Pipeline: discovery, classification, INCI extraction+validation, QA gate, reports
3. Operational: CLI, FastAPI, React dashboard
4. Scale: first 3 brands to excellence, then expand
