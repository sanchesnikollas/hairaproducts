# src/api/main.py
from __future__ import annotations

import collections
import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes.products import router as products_router
from src.api.routes.brands import router as brands_router
from src.api.routes.quarantine import router as quarantine_router
from src.api.routes.ingredients import router as ingredients_router
from src.api.routes.stats import router as stats_router
from src.api.routes.auth import router as auth_router
from src.api.routes.ops import router as ops_router
from src.api.routes.ops_ingredients import router as ops_ingredients_router
from src.api.routes.admin_migrate import router as admin_migrate_router
from src.api.routes.admin_knowledge import router as admin_knowledge_router
from src.api.routes.admin_apify import router as admin_apify_router
from src.api.routes.admin_audit import router as admin_audit_router
from src.api.routes.admin_brands import router as admin_brands_router
from src.api.routes.admin_moon import router as admin_moon_router
from src.api.routes.admin_scrape import router as admin_scrape_router
from src.api.routes.moon import router as moon_router

logger = logging.getLogger("haira.api")

# ── Rate limiter (in-memory, per-IP) ──

_RATE_WINDOW = 60  # seconds
_RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "120"))  # requests per window

_request_log: dict[str, collections.deque] = {}

app = FastAPI(title="HAIRA v2", version="2.0.0", description="Hair Product Intelligence Platform API")

# Origin whitelisting — em prod, set ALLOWED_ORIGINS=https://haira-app-production-deb8.up.railway.app
# (vírgulas pra múltiplos). Default no Railway hoje cobre o domínio público + dev local.
_DEFAULT_ORIGINS = (
    "https://haira-app-production-deb8.up.railway.app,"
    "http://localhost:5173,"
    "http://localhost:3000"
)
_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Headers HTTP de segurança aplicados em toda resposta.

    Não inclui CSP estrito porque o frontend serve assets variáveis (Vite +
    imagens externas dos catálogos). HSTS, frame-deny e nosniff são triviais
    e cobrem os ataques mais comuns.
    """
    response = await call_next(request)
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        if client_ip not in _request_log:
            _request_log[client_ip] = collections.deque()
        dq = _request_log[client_ip]
        # Purge entries older than the window
        while dq and dq[0] < now - _RATE_WINDOW:
            dq.popleft()
        if len(dq) >= _RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
            )
        dq.append(now)
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %s %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

app.include_router(products_router, prefix="/api")
app.include_router(brands_router, prefix="/api")
app.include_router(quarantine_router, prefix="/api")
app.include_router(ingredients_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(ops_router, prefix="/api")
app.include_router(ops_ingredients_router, prefix="/api")
app.include_router(admin_migrate_router, prefix="/api")  # temporary migration
app.include_router(admin_knowledge_router, prefix="/api")
app.include_router(admin_apify_router, prefix="/api")
app.include_router(admin_brands_router, prefix="/api")  # central counter sync
app.include_router(admin_moon_router, prefix="/api")    # Moon personality editor
app.include_router(admin_audit_router, prefix="/api")   # Audit log viewer
app.include_router(admin_scrape_router, prefix="/api")  # remote scrape trigger
app.include_router(moon_router, prefix="/api")  # Moon AI ingredient analysis


def _normalise_pg_url(url: str) -> str:
    """Railway/Heroku usam `postgres://` — SQLAlchemy precisa `postgresql://`."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _make_engine(url: str, *, pool_size: int = 3, max_overflow: int = 2):
    from sqlalchemy import create_engine
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=300,
    )


@app.on_event("startup")
def _init_databases() -> None:
    """Inicializa até 3 engines (core/catalog/audit) + DatabaseRouter legacy.

    Cada engine só é criado se sua env específica estiver setada — o resto
    cai em fallback chain via `dependencies.py:_resolve_default_engine()`,
    que volta pro modo single-DB se nenhuma envvar nova existir.

    Compatibilidade backward:
    - Setar apenas `DATABASE_URL` → modo single-DB (legacy, é o estado atual prod).
    - Setar `CENTRAL_DATABASE_URL` → multi-brand mode antigo (per-brand DB).
    - Setar `CORE_DATABASE_URL` + `CATALOG_DATABASE_URL` + `AUDIT_DATABASE_URL`
      → split 3-DB novo (objetivo da arquitetura).
    """
    from src.api.dependencies import (
        init_router,
        set_audit_engine,
        set_catalog_engine,
        set_core_engine,
    )

    enabled: list[str] = []

    # ── haira_core ─────────────────────────────────────────────────────────
    core_url = os.environ.get("CORE_DATABASE_URL", "").strip()
    if core_url:
        core_engine = _make_engine(_normalise_pg_url(core_url), pool_size=3, max_overflow=2)
        set_core_engine(core_engine)
        enabled.append("core")

    # ── haira_catalog (pool maior, mais leitura) ───────────────────────────
    catalog_url = os.environ.get("CATALOG_DATABASE_URL", "").strip()
    if catalog_url:
        catalog_engine = _make_engine(_normalise_pg_url(catalog_url), pool_size=5, max_overflow=5)
        set_catalog_engine(catalog_engine)
        enabled.append("catalog")

    # ── haira_audit (pool menor, append-only) ──────────────────────────────
    audit_url = os.environ.get("AUDIT_DATABASE_URL", "").strip()
    if audit_url:
        audit_engine = _make_engine(_normalise_pg_url(audit_url), pool_size=2, max_overflow=1)
        set_audit_engine(audit_engine)
        enabled.append("audit")

    # ── legacy multi-brand (per-brand DBs via CENTRAL_DATABASE_URL) ───────
    central_url = os.environ.get("CENTRAL_DATABASE_URL", "").strip()
    if central_url:
        from sqlalchemy import create_engine
        central_engine = create_engine(
            _normalise_pg_url(central_url),
            pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=300,
        )
        init_router(central_engine)
        enabled.append("central(legacy multi-brand)")

    if enabled:
        logger.info("DB mode: %s", " + ".join(enabled))
    else:
        logger.info("DB mode: single-db (DATABASE_URL only)")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/admin/dbs/status")
def dbs_status():
    """Reporta connectivity das 3+ DBs. Útil em smoke tests pós-cutover.

    Retorna 200 mesmo se algumas estiverem em fallback — só sinaliza qual é
    qual. `same_engine=True` em pares indica que ainda compartilham origem
    (cutover não terminou).
    """
    from src.api.dependencies import _audit_engine, _catalog_engine, _core_engine, _resolve_default_engine
    default = _resolve_default_engine()

    def probe(label: str, engine):
        e = engine if engine is not None else default
        explicit = engine is not None
        try:
            with e.connect() as conn:
                from sqlalchemy import text
                ver = conn.execute(text("SELECT 1")).scalar()
            return {"label": label, "explicit": explicit, "ok": True, "ping": ver, "engine_id": id(e)}
        except Exception as exc:  # noqa: BLE001
            return {"label": label, "explicit": explicit, "ok": False, "error": str(exc)[:120]}

    return {
        "engines": [
            probe("core", _core_engine),
            probe("catalog", _catalog_engine),
            probe("audit", _audit_engine),
            probe("default", default),
        ],
    }



# ── Serve frontend static files in production ──

# Try multiple possible locations for the frontend dist
_FRONTEND_DIST_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",  # dev (editable install)
    Path("/app/frontend/dist"),  # Docker container
    Path.cwd() / "frontend" / "dist",  # fallback (cwd-based)
]
_FRONTEND_DIST = next((p for p in _FRONTEND_DIST_CANDIDATES if p.is_dir()), _FRONTEND_DIST_CANDIDATES[0])

if _FRONTEND_DIST.is_dir():
    # Serve Vite-built assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    # SPA fallback via middleware — avoids catch-all route that causes 405 on API POST routes
    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        response = await call_next(request)
        # If no API/health/asset route matched, serve index.html for SPA routing
        if (
            response.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith(("/api/", "/health", "/assets/", "/openapi", "/docs", "/redoc"))
        ):
            return FileResponse(_FRONTEND_DIST / "index.html")
        return response
