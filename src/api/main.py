# src/api/main.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes.products import router as products_router
from src.api.routes.brands import router as brands_router
from src.api.routes.quarantine import router as quarantine_router

app = FastAPI(title="HAIRA v2", version="2.0.0", description="Hair Product Intelligence Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
