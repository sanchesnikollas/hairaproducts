# src/api/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
