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

logger = logging.getLogger("haira.api")

# ── Rate limiter (in-memory, per-IP) ──

_RATE_WINDOW = 60  # seconds
_RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "120"))  # requests per window

_request_log: dict[str, collections.deque] = {}

app = FastAPI(title="HAIRA v2", version="2.0.0", description="Hair Product Intelligence Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.on_event("startup")
def _init_multi_db() -> None:
    """Initialise multi-database routing if CENTRAL_DATABASE_URL is set."""
    central_url = os.environ.get("CENTRAL_DATABASE_URL", "").strip()
    if central_url:
        from sqlalchemy import create_engine
        from src.api.dependencies import init_router

        if central_url.startswith("postgres://"):
            central_url = central_url.replace("postgres://", "postgresql://", 1)
        central_engine = create_engine(
            central_url,
            pool_size=3,
            max_overflow=2,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        init_router(central_engine)
        logger.info("Multi-database mode enabled (CENTRAL_DATABASE_URL set)")
    else:
        logger.info("Single-database mode (CENTRAL_DATABASE_URL not set)")


@app.get("/health")
def health():
    return {"status": "ok"}



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
