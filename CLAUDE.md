# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HAIRA v2 is a hair product intelligence platform. It scrapes e-commerce sites to discover, extract, validate, and categorize hair products. Python backend (FastAPI + Click CLI + SQLAlchemy) with a React TypeScript frontend.

## Commands

### Backend

```bash
# Install (Python 3.12+, editable mode with dev deps)
pip install -e ".[dev]"

# Run API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# CLI (entry point: src.cli.main:cli)
haira registry --input "Lista de Produtos.xlsx"
haira blueprint --brand <slug>
haira scrape --brand <slug>
haira labels --brand <slug>
haira labels --brand <slug> --dry-run
haira audit --brand <slug>
haira report --brand <slug>

# Tests
pytest                                              # all tests
pytest tests/core/test_label_engine.py              # one module
pytest tests/core/test_label_engine.py::TestKeywordDetection::test_name -v  # one test

# Migrations (Alembic, config: alembic.ini, scripts: src/storage/migrations/)
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # Vite dev server on :5173, proxies /api to :8000
npm run build     # tsc -b && vite build
npm run lint      # ESLint
```

## Architecture

### Pipeline (src/)

Products flow through stages orchestrated by `src/pipeline/coverage_engine.py`:

1. **Discovery** (`src/discovery/`) — Crawls product URLs via sitemaps + DOM. Per-brand YAML blueprints in `config/blueprints/` define platform type (VTEX, Shopify, WooCommerce), domains, and CSS selectors. Platform adapters in `src/discovery/platform_adapters/`.

2. **Extraction** (`src/extraction/`) — Pulls product data from HTML via JSON-LD, blueprint CSS selectors, and BeautifulSoup fallback. INCI ingredient lists extracted separately via `inci_extractor.py`.

3. **Validation** (`src/core/qa_gate.py`) — QA gate assigns status: `verified_inci` (full INCI validated), `catalog_only` (basic data only), or `quarantined` (failed checks). Products that fail get `QuarantineDetailORM` records.

4. **Label Detection** (`src/core/label_engine.py`) — Post-processing step (CLI: `haira labels`). Detects quality seals (sulfate_free, vegan, etc.) via keyword matching against `config/labels/seals.yaml` + INCI ingredient inference against `config/labels/silicones.yaml` and `config/labels/surfactants.yaml`. Results stored as JSON in `product_labels` column.

### Storage (src/storage/)

- **Database**: SQLite (`haira.db`) by default, PostgreSQL via `DATABASE_URL` env var
- **ORM** (`orm_models.py`): `ProductORM`, `ProductEvidenceORM`, `QuarantineDetailORM`, `BrandCoverageORM`
- **Repository** (`repository.py`): Data access layer — `ProductRepository` with `upsert_product()`, `get_products()`, `update_product_labels()`, etc.
- Product IDs are UUIDs (string). Evidence rows track provenance per extracted field.
- `product_labels` is a JSON column: `{detected: [], inferred: [], confidence: float, sources: [], manually_verified: bool, manually_overridden: bool}`

### API (src/api/)

FastAPI app in `src/api/main.py`. All routes mounted under `/api` prefix. Three route modules:
- `routes/products.py` — GET `/api/products`, GET `/api/products/{id}`
- `routes/brands.py` — GET `/api/brands`, GET `/api/brands/{slug}/coverage`
- `routes/quarantine.py` — GET `/api/quarantine`, POST `/api/quarantine/{id}/approve`

### Frontend (frontend/)

React 19 + TypeScript + Vite + Tailwind CSS 4. Key libraries: `recharts` (charts), `motion` (animations), `react-router-dom` (routing).

- **Pages**: `Dashboard`, `BrandsDashboard`, `ProductBrowser`, `QuarantineReview` in `src/pages/`
- **API client**: `src/lib/api.ts` — typed fetch wrappers
- **Data hook**: `src/hooks/useAPI.ts` — generic async fetcher with loading/error/refetch
- **Proxy**: Vite proxies `/api` to `http://localhost:8000` (see `vite.config.ts`)
- **Types**: `src/types/api.ts` — must match API response shapes

## Key Conventions

- Python uses `from __future__ import annotations` throughout
- Pydantic models in `src/core/models.py`, ORM models in `src/storage/orm_models.py` — these are separate layers
- Blueprints are YAML files in `config/blueprints/{brand_slug}.yaml`
- Brand registry lives in `config/brands.json` (generated from Excel via `haira registry`)
- Environment variables defined in `.env` (see `.env.example`): `ANTHROPIC_API_KEY`, `DATABASE_URL`, `LLM_MODEL`, etc.
- Commit messages use conventional format: `feat:`, `fix:`, `chore:`, `docs:`

## Running Both Servers for Development

Terminal 1: `uvicorn src.api.main:app --reload --port 8000`
Terminal 2: `cd frontend && npm run dev`
Open: `http://localhost:5173`
