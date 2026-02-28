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

logger = logging.getLogger("haira.api")

# ── Env validation ──

_REQUIRED_ENV = ["DATABASE_URL"]


def _validate_env() -> None:
    missing = [v for v in _REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        logger.warning("Missing environment variables: %s", ", ".join(missing))


_validate_env()

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


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Serve frontend static files in production ──

_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # Serve Vite-built assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    # Catch-all: serve index.html for any non-API route (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # Try to serve static file first
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html (React Router handles the route)
        return FileResponse(_FRONTEND_DIST / "index.html")
