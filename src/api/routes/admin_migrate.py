"""Temporary migration endpoint — accepts JSON data for bulk import.

Protected by MIGRATION_SECRET env var. Remove after migration is complete.
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.storage.database import get_engine

logger = logging.getLogger("haira.migrate")

router = APIRouter(prefix="/admin", tags=["admin"])

MIGRATION_SECRET = os.environ.get("MIGRATION_SECRET", "")

TABLE_ORDER = [
    "ingredients", "ingredient_aliases", "claims", "claim_aliases",
    "products", "product_evidence", "quarantine_details",
    "product_ingredients", "product_claims", "product_images",
    "product_compositions", "brand_coverage",
]

BOOL_COLUMNS = {"is_kit", "is_active", "manually_verified", "manually_overridden"}


class MigrateRequest(BaseModel):
    secret: str
    table: str
    rows: list[dict]


def _prepare_params(row: dict) -> dict:
    params = {}
    for k, v in row.items():
        if isinstance(v, (dict, list)):
            params[k] = json.dumps(v, ensure_ascii=False)
        elif k in BOOL_COLUMNS and isinstance(v, int):
            params[k] = bool(v)
        else:
            params[k] = v
    return params


@router.post("/migrate-json")
def migrate_json(body: MigrateRequest):
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    if body.table not in TABLE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown table: {body.table}")

    if not body.rows:
        return {"inserted": 0, "skipped": 0, "errors": []}

    engine = get_engine()
    inserted = 0
    skipped = 0
    errors = []

    # Use a single transaction for the whole batch
    prepared = [_prepare_params(row) for row in body.rows]
    cols = list(prepared[0].keys())
    col_names = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    sql = text(f"INSERT INTO {body.table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")

    try:
        with engine.begin() as conn:
            for params in prepared:
                result = conn.execute(sql, params)
                if result.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
    except Exception as e:
        err_msg = str(e)[:500]
        errors.append(err_msg)
        logger.warning("Batch error on %s: %s", body.table, err_msg)

    return {
        "inserted": inserted,
        "skipped": skipped,
        "table": body.table,
        "errors": errors[:5],
        "total_errors": len(errors),
    }


@router.get("/migrate-status")
def migrate_status(secret: str = ""):
    if not MIGRATION_SECRET or secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    engine = get_engine()
    result = {}
    with engine.connect() as conn:
        for table in TABLE_ORDER:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                result[table] = count
            except Exception:
                result[table] = "error"

        brands = conn.execute(
            text("SELECT brand_slug, COUNT(*) FROM products GROUP BY brand_slug ORDER BY COUNT(*) DESC")
        ).fetchall()
        result["brands"] = {b: c for b, c in brands}

    return result
