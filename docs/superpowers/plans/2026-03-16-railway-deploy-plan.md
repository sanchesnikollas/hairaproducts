# Railway Deploy + Visual Experience Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy HAIRA to Railway with per-brand PostgreSQL databases and a redesigned public-facing frontend.

**Architecture:** Central PostgreSQL holds brand registry + connection strings. Each brand gets its own PostgreSQL with the full product schema. A database router resolves brand_slug → session per request. Frontend serves public catalog pages + admin operational pages under `/admin/*`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, React 19, TypeScript, Vite, Tailwind CSS 4, Shadcn UI, Railway

**Spec:** `docs/superpowers/specs/2026-03-16-railway-deploy-design.md`

---

## Chunk 1: Backend Multi-Database Infrastructure

### Task 1: Central Database ORM Models

**Files:**
- Create: `src/storage/central_models.py`
- Test: `tests/storage/test_central_models.py`

- [ ] **Step 1: Write failing test for BrandDatabaseORM**

```python
# tests/storage/test_central_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_models import CentralBase, BrandDatabaseORM


def test_brand_database_orm_create():
    engine = create_engine("sqlite:///:memory:")
    CentralBase.metadata.create_all(engine)
    with Session(engine) as session:
        brand = BrandDatabaseORM(
            brand_slug="amend",
            brand_name="Amend",
            database_url="postgresql://user:pass@host/amend_db",
            platform="custom_vtex",
            product_count=700,
            inci_rate=0.899,
        )
        session.add(brand)
        session.commit()
        session.refresh(brand)
        assert brand.id is not None
        assert brand.brand_slug == "amend"
        assert brand.is_active is True


def test_brand_database_slug_unique():
    engine = create_engine("sqlite:///:memory:")
    CentralBase.metadata.create_all(engine)
    with Session(engine) as session:
        b1 = BrandDatabaseORM(brand_slug="amend", brand_name="Amend", database_url="url1")
        b2 = BrandDatabaseORM(brand_slug="amend", brand_name="Amend2", database_url="url2")
        session.add_all([b1, b2])
        with pytest.raises(Exception):
            session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/storage/test_central_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.storage.central_models'`

- [ ] **Step 3: Implement CentralBase and BrandDatabaseORM**

```python
# src/storage/central_models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class CentralBase(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BrandDatabaseORM(CentralBase):
    __tablename__ = "brand_databases"

    id = Column(String(36), primary_key=True, default=_uuid)
    brand_slug = Column(String(255), nullable=False, unique=True)
    brand_name = Column(String(255), nullable=False)
    database_url = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    product_count = Column(Integer, nullable=False, default=0)
    inci_rate = Column(Float, nullable=False, default=0.0)
    platform = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/storage/test_central_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/central_models.py tests/storage/test_central_models.py
git commit -m "feat: add central database ORM models for brand registry"
```

---

### Task 2: Database Router

**Files:**
- Create: `src/storage/db_router.py`
- Test: `tests/storage/test_db_router.py`

**Context:** The router maintains a cache of SQLAlchemy engines per brand_slug. It looks up the connection string from the central DB (BrandDatabaseORM), creates an engine on first access, and returns sessions. Existing `src/storage/database.py` patterns: `get_engine()` returns a singleton, `get_session()` returns a session from that engine.

- [ ] **Step 1: Write failing tests for DatabaseRouter**

```python
# tests/storage/test_db_router.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_models import CentralBase, BrandDatabaseORM
from src.storage.db_router import DatabaseRouter, BrandDatabaseUnavailable


@pytest.fixture
def central_engine():
    engine = create_engine("sqlite:///:memory:")
    CentralBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def router_with_brands(central_engine):
    """Set up a router with two brands pointing to in-memory SQLite DBs."""
    with Session(central_engine) as session:
        session.add(BrandDatabaseORM(
            brand_slug="brand-a",
            brand_name="Brand A",
            database_url="sqlite:///:memory:",
            is_active=True,
        ))
        session.add(BrandDatabaseORM(
            brand_slug="brand-b",
            brand_name="Brand B",
            database_url="sqlite:///:memory:",
            is_active=True,
        ))
        session.add(BrandDatabaseORM(
            brand_slug="brand-inactive",
            brand_name="Inactive",
            database_url="sqlite:///:memory:",
            is_active=False,
        ))
        session.commit()
    router = DatabaseRouter(central_engine)
    return router


def test_get_session_valid_brand(router_with_brands):
    session = router_with_brands.get_session("brand-a")
    assert session is not None
    session.close()


def test_get_session_unknown_brand(router_with_brands):
    with pytest.raises(BrandDatabaseUnavailable):
        router_with_brands.get_session("nonexistent")


def test_get_session_inactive_brand(router_with_brands):
    with pytest.raises(BrandDatabaseUnavailable):
        router_with_brands.get_session("brand-inactive")


def test_list_active_brands(router_with_brands):
    brands = router_with_brands.list_brands()
    slugs = [b.brand_slug for b in brands]
    assert "brand-a" in slugs
    assert "brand-b" in slugs
    assert "brand-inactive" not in slugs


def test_engine_caching(router_with_brands):
    s1 = router_with_brands.get_session("brand-a")
    s2 = router_with_brands.get_session("brand-a")
    # Same engine is reused (same bind)
    assert s1.get_bind() is s2.get_bind()
    s1.close()
    s2.close()


def test_get_central_session(router_with_brands):
    session = router_with_brands.get_central_session()
    assert session is not None
    session.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/storage/test_db_router.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement DatabaseRouter**

```python
# src/storage/db_router.py
from __future__ import annotations

import logging
import threading
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.storage.central_models import BrandDatabaseORM

logger = logging.getLogger(__name__)


class BrandDatabaseUnavailable(Exception):
    """Raised when a brand database cannot be reached."""
    pass


class DatabaseRouter:
    """Routes requests to per-brand database sessions."""

    def __init__(self, central_engine: Engine):
        self._central_engine = central_engine
        self._central_factory = sessionmaker(bind=central_engine)
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()

    def get_central_session(self) -> Session:
        return self._central_factory()

    def _get_brand_engine(self, brand_slug: str) -> Engine:
        with self._lock:
            if brand_slug in self._engines:
                return self._engines[brand_slug]

        # Look up connection string from central DB
        with self._central_factory() as session:
            brand = (
                session.query(BrandDatabaseORM)
                .filter_by(brand_slug=brand_slug, is_active=True)
                .first()
            )
            if not brand:
                raise BrandDatabaseUnavailable(f"Brand '{brand_slug}' not found or inactive")
            db_url = brand.database_url

        # Create engine with conservative pool settings
        kwargs: dict = {}
        if db_url.startswith("postgres"):
            # Railway PostgreSQL limits
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            kwargs.update(pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=300)

        engine = create_engine(db_url, **kwargs)

        with self._lock:
            self._engines[brand_slug] = engine

        logger.info("Created engine for brand '%s'", brand_slug)
        return engine

    def get_session(self, brand_slug: str) -> Session:
        engine = self._get_brand_engine(brand_slug)
        factory = sessionmaker(bind=engine)
        return factory()

    def list_brands(self) -> list[BrandDatabaseORM]:
        with self._central_factory() as session:
            return (
                session.query(BrandDatabaseORM)
                .filter_by(is_active=True)
                .order_by(BrandDatabaseORM.brand_name)
                .all()
            )

    def close_all(self) -> None:
        with self._lock:
            for slug, engine in self._engines.items():
                engine.dispose()
                logger.info("Disposed engine for brand '%s'", slug)
            self._engines.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/storage/test_db_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/db_router.py tests/storage/test_db_router.py
git commit -m "feat: add database router for per-brand session routing"
```

---

### Task 3: FastAPI Dependencies for Multi-Database

**Files:**
- Create: `src/api/dependencies.py`
- Modify: `src/api/main.py`
- Test: `tests/api/test_dependencies.py`

**Context:** The API needs two new dependency injection functions: one that extracts `brand_slug` from path params, one from query params. Both use the DatabaseRouter to get a session. The router must be initialized on app startup with the central engine.

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_dependencies.py
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_models import CentralBase, BrandDatabaseORM
from src.storage.db_router import DatabaseRouter
from src.api.dependencies import get_brand_db_from_path, get_central_db, init_router


@pytest.fixture
def test_app():
    """Create a test app with a router backed by in-memory databases."""
    central_engine = create_engine("sqlite:///:memory:")
    CentralBase.metadata.create_all(central_engine)

    # Register a test brand pointing to in-memory SQLite
    with Session(central_engine) as session:
        session.add(BrandDatabaseORM(
            brand_slug="test-brand",
            brand_name="Test Brand",
            database_url="sqlite:///:memory:",
            is_active=True,
            product_count=10,
            inci_rate=0.95,
        ))
        session.commit()

    router = init_router(central_engine)

    app = FastAPI()

    @app.get("/brands/{slug}/test")
    def test_route(slug: str, session: Session = Depends(get_brand_db_from_path)):
        return {"connected": True, "slug": slug}

    @app.get("/central/test")
    def test_central(session: Session = Depends(get_central_db)):
        brands = session.query(BrandDatabaseORM).all()
        return {"count": len(brands)}

    return TestClient(app)


def test_brand_db_from_path(test_app):
    resp = test_app.get("/brands/test-brand/test")
    assert resp.status_code == 200
    assert resp.json()["connected"] is True


def test_brand_db_unknown_returns_503(test_app):
    resp = test_app.get("/brands/unknown-brand/test")
    assert resp.status_code == 503


def test_central_db(test_app):
    resp = test_app.get("/central/test")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/api/test_dependencies.py -v`
Expected: FAIL

- [ ] **Step 3: Implement dependencies module**

```python
# src/api/dependencies.py
from __future__ import annotations

import logging
from typing import Generator

from fastapi import HTTPException, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.storage.db_router import DatabaseRouter, BrandDatabaseUnavailable

logger = logging.getLogger(__name__)

_router: DatabaseRouter | None = None


def init_router(central_engine: Engine) -> DatabaseRouter:
    """Initialize the global database router. Called once at app startup."""
    global _router
    _router = DatabaseRouter(central_engine)
    return _router


def get_router() -> DatabaseRouter:
    if _router is None:
        raise RuntimeError("DatabaseRouter not initialized. Call init_router() first.")
    return _router


def get_brand_db_from_path(request: Request) -> Generator[Session, None, None]:
    """Dependency: get brand DB session from path param 'slug'."""
    slug = request.path_params.get("slug")
    if not slug:
        raise HTTPException(status_code=400, detail="Missing brand slug in path")
    router = get_router()
    try:
        session = router.get_session(slug)
    except BrandDatabaseUnavailable:
        raise HTTPException(status_code=503, detail=f"Brand database '{slug}' temporarily unavailable")
    try:
        yield session
    finally:
        session.close()


def get_brand_db_from_query(brand: str) -> Generator[Session, None, None]:
    """Dependency: get brand DB session from query param 'brand'."""
    router = get_router()
    try:
        session = router.get_session(brand)
    except BrandDatabaseUnavailable:
        raise HTTPException(status_code=503, detail=f"Brand database '{brand}' temporarily unavailable")
    try:
        yield session
    finally:
        session.close()


def get_central_db() -> Generator[Session, None, None]:
    """Dependency: get central DB session."""
    router = get_router()
    session = router.get_central_session()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/api/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/dependencies.py tests/api/test_dependencies.py
git commit -m "feat: add FastAPI dependencies for multi-database routing"
```

---

### Task 4: Adapt API Routes for Multi-Database

**Files:**
- Modify: `src/api/main.py`
- Modify: `src/api/routes/brands.py`
- Modify: `src/api/routes/products.py`
- Modify: `src/api/routes/quarantine.py`
- Modify: `src/api/routes/ingredients.py`
- Create: `src/api/routes/stats.py`

**Context:** All existing routes use `_get_session()` which calls `get_engine()` → single DB. We need to:
1. `main.py`: Initialize the database router on startup using `CENTRAL_DATABASE_URL` env var. Fall back to existing `DATABASE_URL` behavior for local dev (single DB mode).
2. `brands.py`: Replace `get_all_brand_coverages()` with `list_brands()` from the router (reads from central DB).
3. `products.py`: Add `/brands/{slug}/products` and `/brands/{slug}/products/{id}` routes using `get_brand_db_from_path`. Keep existing `/products` route for backwards compatibility (uses brand query param).
4. `quarantine.py`: Add brand query param requirement.
5. `stats.py`: New route that reads global stats from central DB.
6. Remove all `FOCUS_BRAND` references.

- [ ] **Step 1: Update `src/api/main.py` — add router init on startup**

Add import for `dependencies.init_router` and a startup event that creates the central engine from `CENTRAL_DATABASE_URL` and calls `init_router()`. If `CENTRAL_DATABASE_URL` is not set, fall back to single-DB mode (existing behavior for local dev).

```python
# Add to main.py after existing imports:
from src.api.dependencies import init_router
from src.api.routes.stats import router as stats_router

# Add after app creation:
@app.on_event("startup")
def startup():
    central_url = os.environ.get("CENTRAL_DATABASE_URL")
    if central_url:
        from sqlalchemy import create_engine
        if central_url.startswith("postgres://"):
            central_url = central_url.replace("postgres://", "postgresql://", 1)
        central_engine = create_engine(central_url, pool_size=5, pool_pre_ping=True)
        init_router(central_engine)
        logger.info("Multi-database mode: central DB initialized")
    else:
        logger.info("Single-database mode: CENTRAL_DATABASE_URL not set")

# Add stats router:
app.include_router(stats_router, prefix="/api")

# Remove _REQUIRED_ENV = ["DATABASE_URL"] — no longer required in multi-db mode
```

- [ ] **Step 2: Update `src/api/routes/brands.py` — use central DB**

Replace the entire file. The new version reads brand list from central DB (`BrandDatabaseORM`), and brand coverage from the brand's own DB.

```python
# src/api/routes/brands.py
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_central_db, get_brand_db_from_path, get_router
from src.storage.central_models import BrandDatabaseORM
from src.storage.database import get_engine
from src.storage.repository import ProductRepository

router = APIRouter(tags=["brands"])


def _get_session():
    """Legacy single-DB session for backwards compatibility in local dev."""
    from sqlalchemy.orm import Session as SASession
    engine = get_engine()
    with SASession(engine) as session:
        yield session


def _is_multi_db() -> bool:
    return os.environ.get("CENTRAL_DATABASE_URL") is not None


@router.get("/brands")
def list_brands(session: Session = Depends(_get_session)):
    if _is_multi_db():
        router_instance = get_router()
        brands = router_instance.list_brands()
        return [
            {
                "brand_slug": b.brand_slug,
                "brand_name": b.brand_name,
                "product_count": b.product_count,
                "inci_rate": b.inci_rate,
                "platform": b.platform,
                "is_active": b.is_active,
            }
            for b in brands
        ]
    # Single-DB fallback
    repo = ProductRepository(session)
    coverages = repo.get_all_brand_coverages()
    return [
        {
            "brand_slug": c.brand_slug,
            "discovered_total": c.discovered_total,
            "hair_total": c.hair_total,
            "extracted_total": c.extracted_total,
            "verified_inci_total": c.verified_inci_total,
            "verified_inci_rate": c.verified_inci_rate,
            "catalog_only_total": c.catalog_only_total,
            "quarantined_total": c.quarantined_total,
            "status": c.status,
            "last_run": str(c.last_run) if c.last_run else None,
        }
        for c in coverages
    ]


@router.get("/brands/{slug}/coverage")
def get_brand_coverage(slug: str, session: Session = Depends(_get_session)):
    repo = ProductRepository(session)
    cov = repo.get_brand_coverage(slug)
    if not cov:
        raise HTTPException(status_code=404, detail="Brand coverage not found")
    return {
        "brand_slug": cov.brand_slug,
        "discovered_total": cov.discovered_total,
        "hair_total": cov.hair_total,
        "kits_total": cov.kits_total,
        "non_hair_total": cov.non_hair_total,
        "extracted_total": cov.extracted_total,
        "verified_inci_total": cov.verified_inci_total,
        "verified_inci_rate": cov.verified_inci_rate,
        "catalog_only_total": cov.catalog_only_total,
        "quarantined_total": cov.quarantined_total,
        "status": cov.status,
        "last_run": str(cov.last_run) if cov.last_run else None,
        "blueprint_version": cov.blueprint_version,
        "coverage_report": cov.coverage_report,
    }


@router.get("/brands/{slug}/products")
def get_brand_products(
    slug: str,
    verified_only: bool = False,
    exclude_kits: bool = True,
    search: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_brand_db_from_path),
):
    repo = ProductRepository(session)
    products = repo.get_products(
        verified_only=verified_only,
        search=search,
        category=category,
        exclude_kits=exclude_kits,
        limit=limit,
        offset=offset,
    )
    total = repo.count_products(
        verified_only=verified_only,
        search=search,
        category=category,
        exclude_kits=exclude_kits,
    )
    from src.api.routes.products import _serialize_product_list_item
    items = [_serialize_product_list_item(p) for p in products]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/brands/{slug}/products/{product_id}")
def get_brand_product(
    slug: str,
    product_id: str,
    session: Session = Depends(get_brand_db_from_path),
):
    repo = ProductRepository(session)
    product = repo.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    from src.api.routes.products import _serialize_product_detail
    return _serialize_product_detail(product)
```

- [ ] **Step 3: Update `src/api/routes/products.py` — extract serialization helpers, remove FOCUS_BRAND**

Extract `_serialize_product_detail()` from the inline dict in `get_product()` so it can be reused by `brands.py`. Remove all `FOCUS_BRAND` references. Keep existing routes for backwards compatibility.

- [ ] **Step 4: Create `src/api/routes/stats.py`**

```python
# src/api/routes/stats.py
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.dependencies import get_central_db, get_router
from src.storage.central_models import BrandDatabaseORM
from src.storage.database import get_engine
from src.storage.orm_models import ProductORM

router = APIRouter(tags=["stats"])


def _get_session():
    from sqlalchemy.orm import Session as SASession
    engine = get_engine()
    with SASession(engine) as session:
        yield session


@router.get("/stats")
def get_global_stats(session: Session = Depends(_get_session)):
    if os.environ.get("CENTRAL_DATABASE_URL"):
        router_instance = get_router()
        brands = router_instance.list_brands()
        return {
            "total_brands": len(brands),
            "total_products": sum(b.product_count for b in brands),
            "avg_inci_rate": (
                sum(b.inci_rate * b.product_count for b in brands) /
                max(sum(b.product_count for b in brands), 1)
            ),
            "platforms": list(set(b.platform for b in brands if b.platform)),
        }
    # Single-DB fallback
    total = session.query(func.count(ProductORM.id)).scalar() or 0
    brands_count = session.query(func.count(func.distinct(ProductORM.brand_slug))).scalar() or 0
    verified = session.query(func.count(ProductORM.id)).filter(
        ProductORM.verification_status == "verified_inci"
    ).scalar() or 0
    return {
        "total_brands": brands_count,
        "total_products": total,
        "avg_inci_rate": verified / max(total, 1),
        "platforms": [],
    }
```

- [ ] **Step 5: Run all existing tests to ensure nothing breaks**

Run: `python3 -m pytest tests/ -v --ignore=tests/core/test_taxonomy.py`
Expected: All tests pass (test_taxonomy has a pre-existing failure unrelated to our changes)

- [ ] **Step 6: Commit**

```bash
git add src/api/main.py src/api/dependencies.py src/api/routes/brands.py src/api/routes/products.py src/api/routes/quarantine.py src/api/routes/stats.py
git commit -m "feat: adapt API routes for multi-database with single-DB fallback"
```

---

### Task 5: Alembic Central Database Migrations

**Files:**
- Create: `alembic_central.ini`
- Create: `src/storage/central_migrations/env.py`
- Create: `src/storage/central_migrations/script.py.mako`
- Create: `src/storage/central_migrations/versions/` (empty dir)

**Context:** The central DB needs its own Alembic environment separate from the brand DB migrations. The existing `alembic.ini` and `src/storage/migrations/` continue to manage brand DB schemas.

- [ ] **Step 1: Create `alembic_central.ini`**

```ini
[alembic]
script_location = src/storage/central_migrations
sqlalchemy.url = sqlite:///haira_central.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create central migrations env.py**

```python
# src/storage/central_migrations/env.py
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from src.storage.central_models import CentralBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = CentralBase.metadata


def get_url():
    return os.environ.get("CENTRAL_DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_online():
    url = get_url()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

- [ ] **Step 3: Create script.py.mako template** (copy from existing `src/storage/migrations/script.py.mako`)

- [ ] **Step 4: Generate initial central migration**

Run: `python3 -m alembic -c alembic_central.ini revision --autogenerate -m "create brand_databases table"`

- [ ] **Step 5: Run central migration**

Run: `CENTRAL_DATABASE_URL=sqlite:///haira_central.db python3 -m alembic -c alembic_central.ini upgrade head`
Expected: Creates `brand_databases` table

- [ ] **Step 6: Commit**

```bash
git add alembic_central.ini src/storage/central_migrations/
git commit -m "feat: add Alembic environment for central database"
```

---

### Task 6: Multi-Brand Migration Script

**Files:**
- Create: `scripts/migrate_all_brands.py`

**Context:** This script runs `alembic upgrade head` on each brand database registered in the central DB. Used during Railway startup to ensure all brand DBs have the latest schema.

- [ ] **Step 1: Implement the script**

```python
# scripts/migrate_all_brands.py
"""Run Alembic migrations on all brand databases registered in the central DB."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.storage.central_models import CentralBase, BrandDatabaseORM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


def get_central_engine():
    url = os.environ.get("CENTRAL_DATABASE_URL", "sqlite:///haira_central.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url)


def run_brand_migrations():
    central_engine = get_central_engine()
    CentralBase.metadata.create_all(central_engine)  # Ensure central tables exist

    with Session(central_engine) as session:
        brands = session.query(BrandDatabaseORM).filter_by(is_active=True).all()
        brand_list = [(b.brand_slug, b.database_url) for b in brands]

    if not brand_list:
        logger.info("No active brands found in central DB")
        return

    alembic_cfg = Config("alembic.ini")
    success = 0
    failed = 0

    for slug, db_url in brand_list:
        try:
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
            command.upgrade(alembic_cfg, "head")
            logger.info("✓ %s — migrations applied", slug)
            success += 1
        except Exception as e:
            logger.error("✗ %s — migration failed: %s", slug, e)
            failed += 1
            # Mark as inactive in central DB
            with Session(central_engine) as session:
                brand = session.query(BrandDatabaseORM).filter_by(brand_slug=slug).first()
                if brand:
                    brand.is_active = False
                    session.commit()

    logger.info("Migration complete: %d success, %d failed", success, failed)


if __name__ == "__main__":
    run_brand_migrations()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/migrate_all_brands.py
git commit -m "feat: add script to run migrations on all brand databases"
```

---

### Task 7: Data Migration Script (SQLite → PostgreSQL)

**Files:**
- Create: `scripts/migrate_to_railway.py`

**Context:** One-time script to migrate data from local SQLite to per-brand PostgreSQL instances on Railway. Reads all rows for a brand from SQLite, inserts into the target PostgreSQL, and updates stats in the central DB.

- [ ] **Step 1: Implement the migration script**

```python
# scripts/migrate_to_railway.py
"""Migrate data from local SQLite to per-brand PostgreSQL on Railway."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from src.storage.orm_models import (
    Base, ProductORM, ProductEvidenceORM, QuarantineDetailORM, BrandCoverageORM,
    IngredientORM, IngredientAliasORM, ProductIngredientORM,
    ClaimORM, ClaimAliasORM, ProductClaimORM,
    ProductImageORM, ProductCompositionORM,
    ValidationComparisonORM, ReviewQueueORM,
)
from src.storage.central_models import CentralBase, BrandDatabaseORM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


def get_central_engine():
    url = os.environ.get("CENTRAL_DATABASE_URL", "sqlite:///haira_central.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url)


def migrate_brand(brand_slug: str, source_url: str, target_url: str, central_engine):
    """Migrate all data for a brand from source DB to target DB."""
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    # Ensure target has schema
    Base.metadata.create_all(target_engine)

    with Session(source_engine) as src, Session(target_engine) as tgt:
        # Products
        products = src.query(ProductORM).filter_by(brand_slug=brand_slug).all()
        logger.info("  Products: %d", len(products))
        for p in products:
            src.expunge(p)
            tgt.merge(p)

        # Evidence
        product_ids = [p.id for p in products]
        if product_ids:
            evidence = src.query(ProductEvidenceORM).filter(
                ProductEvidenceORM.product_id.in_(product_ids)
            ).all()
            logger.info("  Evidence: %d", len(evidence))
            for e in evidence:
                src.expunge(e)
                tgt.merge(e)

            # Quarantine
            quarantine = src.query(QuarantineDetailORM).filter(
                QuarantineDetailORM.product_id.in_(product_ids)
            ).all()
            logger.info("  Quarantine: %d", len(quarantine))
            for q in quarantine:
                src.expunge(q)
                tgt.merge(q)

            # Product Ingredients
            pi_rows = src.query(ProductIngredientORM).filter(
                ProductIngredientORM.product_id.in_(product_ids)
            ).all()
            logger.info("  ProductIngredients: %d", len(pi_rows))

            # Collect unique ingredient IDs
            ingredient_ids = list(set(pi.ingredient_id for pi in pi_rows))
            if ingredient_ids:
                ingredients = src.query(IngredientORM).filter(
                    IngredientORM.id.in_(ingredient_ids)
                ).all()
                for ing in ingredients:
                    src.expunge(ing)
                    tgt.merge(ing)
                # Aliases
                aliases = src.query(IngredientAliasORM).filter(
                    IngredientAliasORM.ingredient_id.in_(ingredient_ids)
                ).all()
                for a in aliases:
                    src.expunge(a)
                    tgt.merge(a)

            for pi in pi_rows:
                src.expunge(pi)
                tgt.merge(pi)

            # Product Claims
            pc_rows = src.query(ProductClaimORM).filter(
                ProductClaimORM.product_id.in_(product_ids)
            ).all()
            logger.info("  ProductClaims: %d", len(pc_rows))
            claim_ids = list(set(pc.claim_id for pc in pc_rows))
            if claim_ids:
                claims = src.query(ClaimORM).filter(ClaimORM.id.in_(claim_ids)).all()
                for c in claims:
                    src.expunge(c)
                    tgt.merge(c)
                claim_aliases = src.query(ClaimAliasORM).filter(
                    ClaimAliasORM.claim_id.in_(claim_ids)
                ).all()
                for ca in claim_aliases:
                    src.expunge(ca)
                    tgt.merge(ca)
            for pc in pc_rows:
                src.expunge(pc)
                tgt.merge(pc)

            # Images
            images = src.query(ProductImageORM).filter(
                ProductImageORM.product_id.in_(product_ids)
            ).all()
            logger.info("  Images: %d", len(images))
            for img in images:
                src.expunge(img)
                tgt.merge(img)

            # Compositions
            compositions = src.query(ProductCompositionORM).filter(
                ProductCompositionORM.product_id.in_(product_ids)
            ).all()
            logger.info("  Compositions: %d", len(compositions))
            for comp in compositions:
                src.expunge(comp)
                tgt.merge(comp)

            # Validation + Review
            validations = src.query(ValidationComparisonORM).filter(
                ValidationComparisonORM.product_id.in_(product_ids)
            ).all()
            for v in validations:
                src.expunge(v)
                tgt.merge(v)

            reviews = src.query(ReviewQueueORM).filter(
                ReviewQueueORM.product_id.in_(product_ids)
            ).all()
            for r in reviews:
                src.expunge(r)
                tgt.merge(r)

        # Brand coverage
        coverage = src.query(BrandCoverageORM).filter_by(brand_slug=brand_slug).all()
        for c in coverage:
            src.expunge(c)
            tgt.merge(c)

        tgt.commit()
        logger.info("  ✓ Committed to target")

    # Update central DB stats
    with Session(target_engine) as tgt:
        total = tgt.query(func.count(ProductORM.id)).scalar() or 0
        verified = tgt.query(func.count(ProductORM.id)).filter(
            ProductORM.verification_status == "verified_inci"
        ).scalar() or 0

    with Session(central_engine) as central:
        brand = central.query(BrandDatabaseORM).filter_by(brand_slug=brand_slug).first()
        if brand:
            brand.product_count = total
            brand.inci_rate = verified / max(total, 1)
            central.commit()
            logger.info("  ✓ Central DB updated: %d products, %.1f%% INCI", total, brand.inci_rate * 100)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", help="Brand slug to migrate (or --all)")
    parser.add_argument("--all", action="store_true", help="Migrate all brands")
    parser.add_argument("--source", default="sqlite:///haira.db", help="Source database URL")
    args = parser.parse_args()

    central_engine = get_central_engine()
    CentralBase.metadata.create_all(central_engine)

    with Session(central_engine) as session:
        if args.all:
            brands = session.query(BrandDatabaseORM).filter_by(is_active=True).all()
        elif args.brand:
            brands = session.query(BrandDatabaseORM).filter_by(brand_slug=args.brand).all()
        else:
            logger.error("Specify --brand <slug> or --all")
            return

        brand_list = [(b.brand_slug, b.database_url) for b in brands]

    for slug, target_url in brand_list:
        logger.info("Migrating %s...", slug)
        migrate_brand(slug, args.source, target_url, central_engine)

    logger.info("Done!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/migrate_to_railway.py
git commit -m "feat: add SQLite to PostgreSQL migration script"
```

---

### Task 8: Update Dockerfile and Entrypoint

**Files:**
- Modify: `Dockerfile`
- Modify: `entrypoint.sh`

- [ ] **Step 1: Update Dockerfile — add scripts/ copy**

Add after `COPY alembic.ini ./`:
```dockerfile
COPY alembic_central.ini ./
COPY scripts/ ./scripts/
```

- [ ] **Step 2: Update entrypoint.sh**

```bash
#!/bin/sh

echo "=== HAIRA v2 Starting ==="
echo "Working directory: $(pwd)"
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"
echo "CENTRAL_DATABASE_URL set: $([ -n "$CENTRAL_DATABASE_URL" ] && echo 'yes' || echo 'NO')"

if [ -n "$CENTRAL_DATABASE_URL" ]; then
    echo "Running central DB migrations..."
    ALEMBIC_DATABASE_URL=$CENTRAL_DATABASE_URL python -m alembic -c alembic_central.ini upgrade head 2>&1 || echo "WARNING: central migrations failed"

    echo "Running brand DB migrations..."
    python scripts/migrate_all_brands.py 2>&1 || echo "WARNING: some brand migrations failed"
else
    echo "Single-DB mode: running standard migrations..."
    python -m alembic upgrade head 2>&1 || echo "WARNING: migrations failed, continuing..."
fi

echo "Starting server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 2
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile entrypoint.sh
git commit -m "feat: update Dockerfile and entrypoint for multi-database support"
```

---

## Chunk 2: Frontend Redesign

### Task 9: New TypeScript Types

**Files:**
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add new types for the public experience**

```typescript
// Add to frontend/src/types/api.ts

export interface BrandSummary {
  brand_slug: string;
  brand_name: string;
  product_count: number;
  inci_rate: number;
  platform: string | null;
  is_active: boolean;
}

export interface GlobalStats {
  total_brands: number;
  total_products: number;
  avg_inci_rate: number;
  platforms: string[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat: add TypeScript types for brand summary and global stats"
```

---

### Task 10: New API Client Functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add new functions**

```typescript
// Add to frontend/src/lib/api.ts

import type { BrandSummary, GlobalStats } from '../types/api';

export async function getGlobalStats(): Promise<GlobalStats> {
  return fetchJSON<GlobalStats>('/stats');
}

export async function getBrandSummaries(): Promise<BrandSummary[]> {
  return fetchJSON<BrandSummary[]>('/brands');
}

export async function getBrandProducts(
  slug: string,
  filters: Omit<ProductFilters, 'brand'> = {}
): Promise<PaginatedResponse<Product>> {
  const params = new URLSearchParams();
  if (filters.verified_only !== undefined) params.set('verified_only', String(filters.verified_only));
  if (filters.exclude_kits !== undefined) params.set('exclude_kits', String(filters.exclude_kits));
  if (filters.search) params.set('search', filters.search);
  if (filters.category) params.set('category', filters.category);
  const perPage = filters.per_page ?? 100;
  params.set('limit', String(perPage));
  if (filters.page) params.set('offset', String(((filters.page ?? 1) - 1) * perPage));
  const qs = params.toString();
  return fetchJSON<PaginatedResponse<Product>>(`/brands/${slug}/products${qs ? `?${qs}` : ''}`);
}

export async function getBrandProduct(slug: string, productId: string): Promise<Product> {
  return fetchJSON<Product>(`/brands/${slug}/products/${productId}`);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add API client functions for brand-scoped endpoints"
```

---

### Task 11: SealBadge Component

**Files:**
- Create: `frontend/src/components/SealBadge.tsx`

- [ ] **Step 1: Implement SealBadge**

```tsx
// frontend/src/components/SealBadge.tsx
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const SEAL_CONFIG: Record<string, { label: string; color: string }> = {
  sulfate_free: { label: 'Sulfate Free', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  paraben_free: { label: 'Paraben Free', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  silicone_free: { label: 'Silicone Free', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  petrolatum_free: { label: 'Petrolatum Free', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  dye_free: { label: 'Dye Free', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  vegan: { label: 'Vegan', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  natural: { label: 'Natural', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  organic: { label: 'Organic', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  cruelty_free: { label: 'Cruelty Free', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  low_poo: { label: 'Low Poo', color: 'bg-amber-100 text-amber-800 border-amber-200' },
  no_poo: { label: 'No Poo', color: 'bg-amber-100 text-amber-800 border-amber-200' },
  thermal_protection: { label: 'Thermal Protection', color: 'bg-orange-100 text-orange-800 border-orange-200' },
  dermatologically_tested: { label: 'Dermatologically Tested', color: 'bg-violet-100 text-violet-800 border-violet-200' },
};

interface SealBadgeProps {
  seal: string;
  className?: string;
}

export default function SealBadge({ seal, className }: SealBadgeProps) {
  const config = SEAL_CONFIG[seal] || { label: seal.replace(/_/g, ' '), color: 'bg-gray-100 text-gray-700 border-gray-200' };
  return (
    <Badge
      variant="outline"
      className={cn('text-[10px] font-medium px-1.5 py-0.5 border', config.color, className)}
    >
      {config.label}
    </Badge>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SealBadge.tsx
git commit -m "feat: add SealBadge component with color-coded seal types"
```

---

### Task 12: BrandCard Component

**Files:**
- Create: `frontend/src/components/BrandCard.tsx`

- [ ] **Step 1: Implement BrandCard**

```tsx
// frontend/src/components/BrandCard.tsx
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface BrandCardProps {
  slug: string;
  name: string;
  productCount: number;
  inciRate: number;
  platform: string | null;
}

export default function BrandCard({ slug, name, productCount, inciRate, platform }: BrandCardProps) {
  return (
    <Link to={`/brands/${slug}`}>
      <Card className="group hover:shadow-md transition-shadow duration-200 cursor-pointer h-full">
        <CardContent className="p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-100 to-emerald-50 flex items-center justify-center">
              <span className="text-lg font-bold text-emerald-700">
                {name.charAt(0).toUpperCase()}
              </span>
            </div>
            {platform && (
              <Badge variant="outline" className="text-[10px] text-ink-muted">
                {platform}
              </Badge>
            )}
          </div>
          <h3 className="font-semibold text-ink mb-1 group-hover:text-emerald-700 transition-colors">
            {name}
          </h3>
          <p className="text-sm text-ink-muted mb-3">
            {productCount} product{productCount !== 1 ? 's' : ''}
          </p>
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-ink-muted">INCI Rate</span>
              <span className="font-medium text-ink">{(inciRate * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${inciRate * 100}%`,
                  backgroundColor: inciRate > 0.9 ? '#22c55e' : inciRate > 0.5 ? '#f59e0b' : '#ef4444',
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/BrandCard.tsx
git commit -m "feat: add BrandCard component with INCI rate indicator"
```

---

### Task 13: ProductCard Component

**Files:**
- Create: `frontend/src/components/ProductCard.tsx`

- [ ] **Step 1: Implement ProductCard**

```tsx
// frontend/src/components/ProductCard.tsx
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import SealBadge from '@/components/SealBadge';
import type { Product } from '@/types/api';

interface ProductCardProps {
  product: Product;
  brandSlug: string;
}

export default function ProductCard({ product, brandSlug }: ProductCardProps) {
  const allSeals = [
    ...(product.product_labels?.detected || []),
    ...(product.product_labels?.inferred || []),
  ];
  const displaySeals = allSeals.slice(0, 3);

  return (
    <Link to={`/brands/${brandSlug}/products/${product.id}`}>
      <Card className="group hover:shadow-md transition-shadow duration-200 cursor-pointer h-full">
        <CardContent className="p-0">
          <div className="aspect-square bg-gray-50 rounded-t-lg overflow-hidden">
            {product.image_url_main ? (
              <img
                src={product.image_url_main}
                alt={product.product_name}
                className="w-full h-full object-contain p-4 group-hover:scale-105 transition-transform duration-300"
                loading="lazy"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-ink-faint">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <path d="M21 15l-5-5L5 21" />
                </svg>
              </div>
            )}
          </div>
          <div className="p-4">
            <h3 className="font-medium text-sm text-ink line-clamp-2 mb-2 min-h-[2.5rem]">
              {product.product_name}
            </h3>
            {displaySeals.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {displaySeals.map((seal) => (
                  <SealBadge key={seal} seal={seal} />
                ))}
                {allSeals.length > 3 && (
                  <span className="text-[10px] text-ink-muted self-center">
                    +{allSeals.length - 3}
                  </span>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ProductCard.tsx
git commit -m "feat: add ProductCard component with image and seal badges"
```

---

### Task 14: Home Page

**Files:**
- Create: `frontend/src/pages/Home.tsx`

- [ ] **Step 1: Implement Home page**

```tsx
// frontend/src/pages/Home.tsx
import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import BrandCard from '@/components/BrandCard';
import { getBrands, getGlobalStats } from '@/lib/api';
import type { BrandCoverage } from '@/types/api';
import type { GlobalStats, BrandSummary } from '@/types/api';

export default function Home() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [brands, setBrands] = useState<(BrandCoverage | BrandSummary)[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getGlobalStats(), getBrands()])
      .then(([s, b]) => {
        setStats(s);
        setBrands(b);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-12">
      {/* Hero */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center py-12"
      >
        <h1 className="text-4xl font-display font-bold text-ink mb-3">
          HAIRA
        </h1>
        <p className="text-lg text-ink-muted max-w-xl mx-auto">
          Base de conhecimento de produtos capilares.
          Ingredientes verificados, selos de qualidade, dados confiáveis.
        </p>
      </motion.section>

      {/* Stats */}
      {stats && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {[
            { label: 'Produtos', value: stats.total_products.toLocaleString('pt-BR') },
            { label: 'Marcas', value: stats.total_brands },
            { label: 'INCI Médio', value: `${(stats.avg_inci_rate * 100).toFixed(0)}%` },
            { label: 'Plataformas', value: stats.platforms.length },
          ].map((stat) => (
            <div key={stat.label} className="bg-white rounded-xl border border-ink/5 p-6 text-center">
              <div className="text-2xl font-bold text-ink">{stat.value}</div>
              <div className="text-sm text-ink-muted mt-1">{stat.label}</div>
            </div>
          ))}
        </motion.section>
      )}

      {/* Brand Grid */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        <h2 className="text-xl font-semibold text-ink mb-6">Marcas</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {brands.map((b) => {
            const slug = b.brand_slug;
            const name = 'brand_name' in b ? b.brand_name : b.brand_slug;
            const count = 'product_count' in b ? b.product_count : b.extracted_total;
            const rate = 'inci_rate' in b ? b.inci_rate : b.verified_inci_rate;
            const platform = 'platform' in b ? b.platform : null;
            return (
              <BrandCard
                key={slug}
                slug={slug}
                name={name}
                productCount={count}
                inciRate={rate}
                platform={platform}
              />
            );
          })}
        </div>
      </motion.section>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "feat: add Home page with stats and brand grid"
```

---

### Task 15: Brand Page (Product Grid with Filters)

**Files:**
- Create: `frontend/src/pages/BrandPage.tsx`

- [ ] **Step 1: Implement BrandPage**

A page that shows a brand's products in a grid with filter sidebar. Uses `getBrandProducts()` or falls back to `getProducts({ brand: slug })` for single-DB mode. Includes filters for verification status, product type, and seals.

The component should:
- Read `slug` from URL params via `useParams()`
- Fetch brand info from `getBrandCoverage(slug)`
- Fetch products from `getBrandProducts(slug)` with filters
- Show brand header with stats
- Show filter checkboxes (verified only, product type, seals)
- Show responsive product grid using `ProductCard`
- Handle loading and empty states

This is a substantial component (~150 lines). Implementation should follow the existing page patterns in `frontend/src/pages/ProductBrowser.tsx`.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/BrandPage.tsx
git commit -m "feat: add BrandPage with product grid and filters"
```

---

### Task 16: Product Detail Page

**Files:**
- Create: `frontend/src/pages/ProductDetail.tsx`

- [ ] **Step 1: Implement ProductDetail**

A page that shows full product details. Uses `getBrandProduct(slug, id)` or falls back to `getProduct(id)`. Shows:
- 2-column layout: image left, data right
- Product name, brand link, verification badge
- INCI ingredient list (numbered, with highlights for silicones/sulfates)
- Seal badges (detected + inferred)
- Accordions for composition, modo de uso, descrição
- Evidence trail (collapsible)

Read URL params: `slug` and `productId` from `useParams()`.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ProductDetail.tsx
git commit -m "feat: add ProductDetail page with INCI list and seal badges"
```

---

### Task 17: Update App Router and Layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Update App.tsx with new routes**

```tsx
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import BrandCatalog from './pages/BrandsDashboard'  // Reuse existing, or create new
import BrandPage from './pages/BrandPage'
import ProductDetail from './pages/ProductDetail'
import ProductBrowser from './pages/ProductBrowser'
import QuarantineReview from './pages/QuarantineReview'
import ReviewQueue from './pages/ReviewQueue'
import Dashboard from './pages/Dashboard'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Public routes */}
        <Route index element={<Home />} />
        <Route path="brands" element={<BrandCatalog />} />
        <Route path="brands/:slug" element={<BrandPage />} />
        <Route path="brands/:slug/products/:productId" element={<ProductDetail />} />

        {/* Admin routes */}
        <Route path="admin" element={<Dashboard />} />
        <Route path="admin/products" element={<ProductBrowser />} />
        <Route path="admin/quarantine" element={<QuarantineReview />} />
        <Route path="admin/review-queue" element={<ReviewQueue />} />
      </Route>
    </Routes>
  )
}

export default App
```

- [ ] **Step 2: Update Layout.tsx navigation**

Split navigation into public and admin sections. Public nav shows Home, Brands. Admin nav shows Dashboard, Products, Quarantine, Review Queue (collapsed under "Admin" dropdown or separate section).

- [ ] **Step 3: Build and verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat: reorganize routes into public catalog and admin sections"
```

---

## Chunk 3: Deploy and Validate

### Task 18: Railway Setup and Deploy

**This task requires manual Railway dashboard actions + CLI commands.**

- [ ] **Step 1: Create PostgreSQL instances on Railway**

In Railway dashboard, create 12 PostgreSQL services:
- `haira-central`
- `haira-amend`, `haira-boticario`, `haira-eudora`, `haira-loccitane`, `haira-mustela`, `haira-avatim`, `haira-granado`, `haira-johnsons`, `haira-loreal`, `haira-redken`

Note each connection string (internal URL).

- [ ] **Step 2: Populate central database**

```bash
# Set CENTRAL_DATABASE_URL to Railway's central PostgreSQL
export CENTRAL_DATABASE_URL="postgresql://..."

# Run central migrations
python3 -m alembic -c alembic_central.ini upgrade head

# Register each brand with its Railway PostgreSQL URL
python3 -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.storage.central_models import CentralBase, BrandDatabaseORM

engine = create_engine('$CENTRAL_DATABASE_URL')
CentralBase.metadata.create_all(engine)

brands = [
    ('amend', 'Amend', 'postgresql://...', 'custom_vtex'),
    ('o-boticario', 'O Boticário', 'postgresql://...', 'vtex_io'),
    ('eudora', 'Eudora', 'postgresql://...', 'vtex_io'),
    ('loccitane', 'L'\''Occitane', 'postgresql://...', 'demandware'),
    ('mustela', 'Mustela', 'postgresql://...', 'shopify'),
    ('avatim', 'Avatim', 'postgresql://...', 'vnda'),
    ('granado', 'Granado', 'postgresql://...', 'deco_cx'),
    ('johnsons-baby', 'Johnson'\''s Baby', 'postgresql://...', 'nextjs_contentful'),
    ('loreal-professionel', 'L'\''Oréal Professionnel', 'postgresql://...', 'sitecore_vue'),
    ('redken', 'Redken', 'postgresql://...', 'sitecore_wsf'),
]

with Session(engine) as session:
    for slug, name, url, platform in brands:
        session.add(BrandDatabaseORM(brand_slug=slug, brand_name=name, database_url=url, platform=platform))
    session.commit()
print('Done!')
"
```

- [ ] **Step 3: Run brand DB migrations**

```bash
python3 scripts/migrate_all_brands.py
```

- [ ] **Step 4: Migrate data from SQLite**

```bash
python3 scripts/migrate_to_railway.py --all
```

- [ ] **Step 5: Validate migration**

```bash
python3 -c "
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from src.storage.central_models import CentralBase, BrandDatabaseORM
from src.storage.orm_models import ProductORM

engine = create_engine('$CENTRAL_DATABASE_URL')
with Session(engine) as session:
    for b in session.query(BrandDatabaseORM).filter_by(is_active=True).all():
        print(f'{b.brand_slug}: {b.product_count} products, {b.inci_rate:.1%} INCI')
"
```

- [ ] **Step 6: Set Railway environment variables**

In Railway dashboard for `haira-app`:
- `CENTRAL_DATABASE_URL` = internal URL of `haira-central`
- `ANTHROPIC_API_KEY` = (existing key)

- [ ] **Step 7: Deploy**

```bash
git push origin main
```
Railway auto-builds from Dockerfile.

- [ ] **Step 8: Smoke test production**

```bash
# Health check
curl https://haira-app.up.railway.app/health

# API tests
curl https://haira-app.up.railway.app/api/stats
curl https://haira-app.up.railway.app/api/brands
curl https://haira-app.up.railway.app/api/brands/amend/products?limit=5

# Open frontend
open https://haira-app.up.railway.app/
```

- [ ] **Step 9: Commit any fixes**

```bash
git add -A
git commit -m "fix: post-deploy adjustments"
```
