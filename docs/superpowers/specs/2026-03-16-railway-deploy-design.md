# Railway Deploy + Visual Experience — Design Specification

**Date:** 2026-03-16
**Status:** Approved
**Scope:** Deploy HAIRA to Railway with per-brand databases and a public-facing visual experience

---

## 1. Overview

Deploy HAIRA as a production service on Railway with isolated PostgreSQL databases per brand, a redesigned public-facing frontend for product/brand exploration, and admin routes for operational pages. Prepares the data layer for a future AI recommendation engine based on user hair profiles.

**Key decisions:**
- One PostgreSQL per brand (isolation, independent scaling, future AI knowledge bases)
- Single app service serving both API and frontend
- Public catalog experience + admin operational pages under `/admin/*`

## 2. Architecture — Multi-Database

### Database Topology

```
Railway Project
├── haira-app (Web service, Dockerfile)
├── haira-central (PostgreSQL) — brand registry, users, config
├── haira-amend (PostgreSQL)
├── haira-boticario (PostgreSQL)
├── haira-eudora (PostgreSQL)
├── haira-loccitane (PostgreSQL)
├── haira-mustela (PostgreSQL)
├── haira-avatim (PostgreSQL)
├── haira-granado (PostgreSQL)
├── haira-johnsons (PostgreSQL)
├── haira-loreal (PostgreSQL)
└── haira-redken (PostgreSQL)
```

### Central Database Schema

```sql
-- Brand → database mapping
CREATE TABLE brand_databases (
    id UUID PRIMARY KEY,
    brand_slug TEXT NOT NULL UNIQUE,
    brand_name TEXT NOT NULL,
    database_url TEXT NOT NULL,        -- connection string (Railway internal networking, not publicly exposed)
    is_active BOOLEAN DEFAULT true,
    product_count INTEGER DEFAULT 0,
    inci_rate FLOAT DEFAULT 0.0,
    platform TEXT,                     -- vtex_io, shopify, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- users and user_profiles deferred to AI recommendation phase (separate spec)
```

### Per-Brand Database Schema

Each brand database contains the full existing schema:
- `products`, `product_evidence`, `quarantine_details`, `brand_coverage`
- `ingredients`, `ingredient_aliases`, `product_ingredients`
- `claims`, `claim_aliases`, `product_claims`
- `product_images`, `product_compositions`
- `validation_comparisons`, `review_queue`

All brand databases share identical schema — same Alembic migrations applied to all.

### Database Router

```
Request: GET /api/brands/amend/products
  → Route extracts brand_slug from path param
  → db_router looks up connection string in central DB (cached in-memory, TTL 5min)
  → Returns SQLAlchemy session bound to brand's PostgreSQL
  → Route handler uses session normally via Depends()
```

**Implementation:**
- `src/storage/db_router.py` — new module
- `get_brand_session(brand_slug)` — dependency injection function
- Two dependency variants:
  - `get_brand_db_from_path(slug: str)` — for `/brands/{slug}/...` routes
  - `get_brand_db_from_query(brand: str = Query(...))` — for `/products?brand=...` routes
- Connection pools cached per slug in a dict (engine pool per brand, `pool_size=3` per brand to stay within Railway limits — max ~33 connections across 11 DBs per worker)
- Central DB has its own dedicated engine/session (`pool_size=5`)
- `FOCUS_BRAND` env var deprecated — replaced by db_router brand selection

### Cross-Brand Query Strategy

Cross-brand queries (search, global stats) are **deferred to Phase 2**. In Phase 1:
- `/api/search` is not implemented — search is per-brand only (within brand page)
- `/api/stats` returns pre-computed stats from `brand_databases` table in central DB (no cross-DB queries)
- Global ingredient search deferred — canonical ingredients are duplicated per brand DB, matched by `canonical_name` string when needed

**Phase 2 approach (future):** A `product_index` table in the central DB with denormalized product summaries (id, brand_slug, name, seals, top ingredients) for fast cross-brand search without querying all DBs.

### Alembic Multi-Database Strategy

- **Central DB:** Separate Alembic environment at `src/storage/central_migrations/` with its own `env.py` pointing to `CENTRAL_DATABASE_URL`
- **Brand DBs:** Existing Alembic environment at `src/storage/migrations/` — a new script `scripts/migrate_all_brands.py` programmatically runs `alembic.command.upgrade(config, "head")` for each brand, overriding `sqlalchemy.url` per iteration
- **Partial failure:** If migration fails on one brand DB, log the error, skip that brand, continue with others. Failed brands marked `is_active=false` in central DB. Startup does NOT block on brand migration failures.
- **Schema drift detection:** `migrate_all_brands.py` reports which brands are at which Alembic revision — mismatches flagged in logs

### Connection Pool Limits

Railway Starter PostgreSQL allows ~20 concurrent connections. With `--workers 2`:
- Per-brand engine: `pool_size=3, max_overflow=2` = max 5 connections per brand per worker
- Central engine: `pool_size=5, max_overflow=3`
- Lazy engine creation: brand engines created on first request, not at startup
- Idle connections recycled after 300s (`pool_recycle=300`)

### Migration Script

`scripts/migrate_to_railway.py`:
1. Read products from local SQLite filtered by `brand_slug`
2. Connect to target PostgreSQL for that brand
3. Insert all related data (products, ingredients, claims, images, evidence, etc.)
4. Update product counts and INCI rate in central DB
5. Validate: compare row counts SQLite vs PostgreSQL

Usage:
```bash
python3 scripts/migrate_to_railway.py --brand amend
python3 scripts/migrate_to_railway.py --all
```

## 3. Frontend — Public Experience

### Route Structure

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Hero stats, featured brands grid |
| `/brands` | Brand Catalog | Cards with logo, counts, INCI rate, top seals |
| `/brands/:slug` | Brand Page | Brand header + product grid with filters |
| `/brands/:slug/products/:id` | Product Detail | Image, INCI list, seals, composition, usage |
| `/admin` | Admin Dashboard | Operational dashboard (existing) |
| `/admin/quarantine` | Quarantine Review | Existing quarantine page |
| `/admin/review-queue` | Review Queue | Existing review queue page |

### Page Designs

#### Home (`/`)
- Hero section: "HAIRA — Base de conhecimento de produtos capilares"
- Stats bar: X produtos, Y marcas, Z ingredientes canônicos, W% INCI médio
- Featured brands grid (3x3 or 4x3 cards)
- Each card: brand name, product count, INCI rate bar, top 3 seal badges

#### Brand Catalog (`/brands`)
- Search/filter bar at top
- Grid of BrandCards (responsive: 4 cols desktop, 2 tablet, 1 mobile)
- Sort by: name, product count, INCI rate
- Filter by: platform, INCI rate range

#### Brand Page (`/brands/:slug`)
- Brand header: name, platform badge, stats (products, INCI rate, seals breakdown)
- Filter sidebar: product type, seals (checkboxes), ingredient search
- Product grid: ProductCards with image, name, seal badges
- Sort by: name, seal count

#### Product Detail (`/brands/:slug/products/:id`)
- 2-column layout: image (left), data (right)
- Product name, brand link, verification status badge
- INCI ingredient list: numbered by position, highlight silicones (orange) and sulfates (red)
- Seal badges: green (free-from), blue (benefit), yellow (warning)
- Accordions: Composição, Modo de Uso, Descrição
- Evidence trail (collapsible): extraction method, selectors used, timestamps

#### Global Search (Phase 2 — deferred)
Cross-brand search deferred to Phase 2. In Phase 1, search is available within each brand page only.

### Component Library

Built on existing Shadcn UI installation:

- **BrandCard** — Card with brand avatar/logo, name, product count badge, mini progress bar (INCI rate), top 3 SealBadges
- **ProductCard** — Card with product image (aspect-ratio 1:1), name truncated to 2 lines, brand name, SealBadge row
- **SealBadge** — Colored badge per seal type: green (sulfate_free, paraben_free, silicone_free), blue (vegan, natural, organic), yellow (thermal_protection), with icon + label
- **InciList** — Ordered list of ingredients with position numbers, colored highlights for flagged categories
- **FilterSidebar** — Checkbox groups for product type, seals, ingredients with search
- **StatsBar** — Horizontal bar with key metrics, animated counters

### Design Tokens

- **Colors:** Neutral grays (zinc) + green accent (#22c55e for seals/positive) + brand-specific accents
- **Typography:** System font stack, clean hierarchy (Inter if available)
- **Spacing:** Tailwind defaults, consistent padding (p-4/p-6)
- **Cards:** Rounded-lg, subtle shadow, hover:shadow-md transition
- **Responsive breakpoints:** sm:640px, md:768px, lg:1024px, xl:1280px

## 4. Backend API Changes

### New Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/brands` | List all brands with stats (from central DB) |
| GET | `/api/brands/:slug` | Brand detail with full stats |
| GET | `/api/brands/:slug/products` | Products for a brand (from brand DB) |
| GET | `/api/brands/:slug/products/:id` | Product detail with INCI, seals, evidence |
| GET | `/api/stats` | Global stats (total products, brands, ingredients) |

### Modified Endpoints

Existing endpoints adapted to work with multi-database:
- `GET /api/products` — requires `brand` query param (or returns cross-brand results)
- `GET /api/quarantine` — requires `brand` query param
- `GET /api/ingredients` — can query specific brand DB or cross-brand

### Database Router Dependency

```python
# Path-based dependency (for /brands/{slug}/... routes)
def get_brand_db_from_path(slug: str) -> Generator[Session, None, None]:
    session = db_router.get_session(slug)
    try:
        yield session
    finally:
        session.close()

# Query-based dependency (for /products?brand=... routes)
def get_brand_db_from_query(brand: str = Query(...)) -> Generator[Session, None, None]:
    session = db_router.get_session(brand)
    try:
        yield session
    finally:
        session.close()

# Route usage
@router.get("/brands/{slug}/products")
async def get_brand_products(slug: str, session: Session = Depends(get_brand_db_from_path)):
    repo = ProductRepository(session)
    return repo.get_products()
```

### Existing Endpoint Migration

- `GET /api/brands` — reads from central DB `brand_databases` table (replaces existing single-DB query)
- `GET /api/brands/{slug}/coverage` — kept for backwards compatibility, reads from brand DB
- `GET /api/products` — requires `brand` query param, routed to brand DB
- `GET /api/quarantine` — requires `brand` query param, routed to brand DB
- `GET /api/ingredients` — requires `brand` query param, routed to brand DB
- `FOCUS_BRAND` env var — deprecated, removed from all routes

### Error Handling for Database Unavailability

- If a brand PostgreSQL is unreachable, `db_router.get_session()` raises `BrandDatabaseUnavailable`
- `GET /api/brands` returns all brands from central DB, with an `is_available` boolean per brand (checked via lightweight ping)
- Brand-specific routes return 503 with message "Brand database temporarily unavailable"
- Home page stats come from central DB only (pre-computed) — never blocked by brand DB issues

## 5. Deploy Configuration

### Railway Setup

**Environment Variables (haira-app):**
- `CENTRAL_DATABASE_URL` — connection string for central PostgreSQL
- `ANTHROPIC_API_KEY` — for future AI features
- `PORT` — auto-injected by Railway

**Brand database URLs** stored in `brand_databases` table in central DB (not as env vars — avoids 10+ env vars and allows dynamic addition of brands).

### Dockerfile (existing, minor updates)

- Already multi-stage (Node build → Python runtime)
- Add: install `psycopg2-binary` for PostgreSQL support (may already be in deps)
- Add: copy `scripts/` directory (currently not copied)
- Entrypoint updated: migrate central DB + all brand DBs on startup

### Startup Flow

```
entrypoint.sh:
  1. ALEMBIC_DATABASE_URL=$CENTRAL_DATABASE_URL alembic -c alembic_central.ini upgrade head
  2. python3 scripts/migrate_all_brands.py  # runs alembic on each brand DB, non-blocking on failure
  3. uvicorn src.api.main:app --workers 2 --port $PORT
```

### Estimated Costs

| Service | Plan | Cost/month |
|---------|------|------------|
| haira-app | Starter | ~$5 |
| 11x PostgreSQL | Starter | ~$5 each = $55 |
| **Total** | | **~$60/month** |

## 6. Data Migration

### Migration Script (`scripts/migrate_to_railway.py`)

**Per-brand migration:**
1. Connect to local SQLite
2. Query all rows for `brand_slug` from each table
3. Connect to target PostgreSQL (brand-specific)
4. Bulk insert with conflict resolution (upsert by UUID)
5. Verify row counts match
6. Update `brand_databases.product_count` and `inci_rate` in central DB

**Tables migrated per brand:**
- products, product_evidence, quarantine_details, brand_coverage
- ingredients, ingredient_aliases, product_ingredients
- claims, claim_aliases, product_claims
- product_images, product_compositions
- validation_comparisons, review_queue

**Cross-brand tables (central DB only):**
- brand_databases (manually populated with connection strings)
- users, user_profiles (deferred to AI phase)

### Validation

```bash
python3 scripts/validate_migration.py --brand amend
# Output:
# products: SQLite=700, PostgreSQL=700 ✓
# product_ingredients: SQLite=12345, PostgreSQL=12345 ✓
# ...
```

## 7. Out of Scope

- AI recommendation engine (future — separate spec)
- User authentication/login
- Users and user_profiles tables (deferred to AI phase)
- Cross-brand global search (Phase 2 — requires product_index in central DB)
- Pipeline monitor real-time page
- L'Oréal inside-our-products.loreal.com INCI scraping
- Brand logo upload/management (use placeholder icons for now)
- PWA/mobile app
- CLI pipeline commands (`haira scrape`, `haira labels`) multi-database support (keep using local SQLite for pipeline, migrate results to Railway after)

---

## Implementation Notes

### Dependencies

- Existing: FastAPI, SQLAlchemy, Alembic, React, Vite, Tailwind, Shadcn UI
- Add: `psycopg2-binary` (PostgreSQL driver, may already be present)
- No new frontend dependencies needed (Shadcn + Lucide already installed)

### File Structure (new/modified)

```
src/storage/
  db_router.py          — NEW: multi-database routing, connection pool cache
  central_models.py     — NEW: ORM for brand_databases, users, user_profiles
  central_migrations/   — NEW: Alembic env for central DB schema

src/api/
  main.py              — MODIFIED: add central DB init, new routes
  routes/brands.py     — MODIFIED: use db_router for brand-specific queries
  routes/products.py   — MODIFIED: use db_router
  routes/stats.py      — NEW: global stats endpoint (reads from central DB)

frontend/src/
  pages/
    Home.tsx           — NEW: landing page with stats + brand grid
    BrandCatalog.tsx   — NEW: replaces BrandsDashboard for public view
    BrandPage.tsx      — NEW: brand detail with product grid + filters
    ProductDetail.tsx  — NEW: full product page with INCI/seals
    admin/             — NEW directory: move existing operational pages here
  components/
    BrandCard.tsx      — NEW
    ProductCard.tsx    — NEW
    SealBadge.tsx      — NEW
    InciList.tsx       — NEW
    FilterSidebar.tsx  — NEW
    StatsBar.tsx       — NEW

scripts/
  migrate_to_railway.py    — NEW: SQLite → PostgreSQL per-brand migration
  validate_migration.py    — NEW: post-migration row count verification
  migrate_all_brands.py    — NEW: run Alembic on all brand DBs
```

### Migration Order

1. Create central DB ORM models + Alembic env
2. Implement db_router with connection pool caching
3. Adapt existing API routes to use db_router
4. Build new frontend pages (Home, BrandCatalog, BrandPage, ProductDetail, Search)
5. Build new components (BrandCard, ProductCard, SealBadge, InciList, FilterSidebar)
6. Move existing pages to `/admin/*` routes
7. Create migration scripts
8. Test locally with multiple SQLite files simulating per-brand DBs
9. Deploy to Railway: create PostgreSQL instances, run migrations, migrate data
10. Validate and smoke test production
