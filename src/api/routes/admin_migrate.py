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


class DedupRequest(BaseModel):
    secret: str
    brand_slug: str | None = None  # if None, dedup all brands


@router.post("/dedup-variants")
def dedup_variants(body: DedupRequest):
    """Deduplicate products by (brand_slug, product_name, size_volume).

    For each duplicate group, keeps the row with the richest data (verified_inci
    > has INCI > has price > has description > URL contains /produto), deletes
    the rest with cascading child rows.
    """
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    engine = get_engine()
    deleted_total = 0
    groups_processed = 0
    by_brand: dict[str, int] = {}

    score_sql = """
        (CASE WHEN verification_status = 'verified_inci' THEN 1000 ELSE 0 END) +
        (CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients::text NOT IN ('[]', 'null') THEN 500 ELSE 0 END) +
        (CASE WHEN price IS NOT NULL THEN 100 ELSE 0 END) +
        (CASE WHEN description IS NOT NULL THEN 50 ELSE 0 END) +
        (CASE WHEN image_url_main IS NOT NULL THEN 25 ELSE 0 END) +
        (CASE WHEN product_url ILIKE '%/produto%' THEN 200 ELSE 0 END)
    """

    where = "WHERE 1=1"
    params: dict = {}
    if body.brand_slug:
        where += " AND brand_slug = :slug"
        params["slug"] = body.brand_slug

    try:
        with engine.begin() as conn:
            # Find duplicate groups
            groups_q = text(
                f"""SELECT brand_slug, product_name, COALESCE(size_volume, '') as sz
                    FROM products
                    {where}
                    GROUP BY brand_slug, product_name, COALESCE(size_volume, '')
                    HAVING COUNT(*) > 1"""
            )
            groups = list(conn.execute(groups_q, params).fetchall())
            groups_processed = len(groups)

            for g in groups:
                # Find best row to keep, return ids of others
                ids_to_delete = list(conn.execute(text(
                    f"""WITH ranked AS (
                        SELECT id, ROW_NUMBER() OVER (
                            ORDER BY {score_sql} DESC, created_at ASC
                        ) as rn
                        FROM products
                        WHERE brand_slug = :brand
                          AND product_name = :name
                          AND COALESCE(size_volume, '') = :sz
                    )
                    SELECT id FROM ranked WHERE rn > 1"""
                ), {"brand": g.brand_slug, "name": g.product_name, "sz": g.sz}).fetchall())

                if not ids_to_delete:
                    continue

                ids = [r.id for r in ids_to_delete]
                # Delete child rows first
                for tbl in ["product_evidence", "product_ingredients", "product_claims",
                            "product_images", "product_compositions", "quarantine_details"]:
                    try:
                        conn.execute(text(f"DELETE FROM {tbl} WHERE product_id = ANY(:ids)"),
                                     {"ids": ids})
                    except Exception:
                        pass
                r = conn.execute(text("DELETE FROM products WHERE id = ANY(:ids)"),
                                 {"ids": ids})
                deleted_total += r.rowcount or 0
                by_brand[g.brand_slug] = by_brand.get(g.brand_slug, 0) + len(ids)
    except Exception as e:
        return {"error": str(e)[:500], "deleted": deleted_total}

    return {
        "groups_processed": groups_processed,
        "deleted_total": deleted_total,
        "deleted_by_brand": dict(sorted(by_brand.items(), key=lambda x: -x[1])[:20]),
    }


class DeleteBrandRequest(BaseModel):
    secret: str
    brand_slug: str


@router.post("/migrate-delete-brand")
def migrate_delete_brand(body: DeleteBrandRequest):
    """Delete all data for a brand — for re-import after re-scrape."""
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    engine = get_engine()
    deleted = {}
    try:
        with engine.begin() as conn:
            # Delete in FK order
            for table in ["product_ingredients", "product_claims", "product_images",
                          "product_compositions", "product_evidence", "quarantine_details"]:
                try:
                    r = conn.execute(text(
                        f"DELETE FROM {table} WHERE product_id IN (SELECT id FROM products WHERE brand_slug = :slug)"
                    ), {"slug": body.brand_slug})
                    deleted[table] = r.rowcount
                except Exception:
                    pass
            r = conn.execute(text("DELETE FROM products WHERE brand_slug = :slug"), {"slug": body.brand_slug})
            deleted["products"] = r.rowcount
            r = conn.execute(text("DELETE FROM brand_coverage WHERE brand_slug = :slug"), {"slug": body.brand_slug})
            deleted["brand_coverage"] = r.rowcount
    except Exception as e:
        return {"error": str(e)[:500]}

    return {"deleted": deleted}


class UpdateRequest(BaseModel):
    secret: str
    updates: list[dict]  # [{id: str, field: value, ...}]


@router.post("/migrate-update")
def migrate_update(body: UpdateRequest):
    """Update existing products by ID — for enrichment of fields like usage_instructions, size_volume."""
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    if not body.updates:
        return {"updated": 0}

    ALLOWED_FIELDS = {
        "usage_instructions", "size_volume", "composition", "care_usage",
        "description", "product_category", "product_labels",
    }

    engine = get_engine()
    updated = 0
    errors = []

    try:
        with engine.begin() as conn:
            for row in body.updates:
                pid = row.get("id")
                if not pid:
                    continue
                sets = []
                params = {"pid": pid}
                for k, v in row.items():
                    if k == "id":
                        continue
                    if k not in ALLOWED_FIELDS:
                        continue
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False)
                    sets.append(f"{k} = :{k}")
                    params[k] = v
                if not sets:
                    continue
                sql = text(f"UPDATE products SET {', '.join(sets)} WHERE id = :pid")
                result = conn.execute(sql, params)
                updated += result.rowcount
    except Exception as e:
        errors.append(str(e)[:500])

    return {"updated": updated, "errors": errors[:5]}


class CoverageUpdateRequest(BaseModel):
    secret: str
    brand_slug: str
    updates: dict  # {field: value} for brand_coverage


@router.post("/migrate-update-coverage")
def migrate_update_coverage(body: CoverageUpdateRequest):
    """Update brand_coverage fields for a brand without touching products."""
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    ALLOWED = {
        "discovered_total", "hair_total", "kits_total", "non_hair_total",
        "extracted_total", "verified_inci_total", "verified_inci_rate",
        "catalog_only_total", "quarantined_total", "status", "blueprint_version",
    }

    engine = get_engine()
    sets = []
    params = {"slug": body.brand_slug}
    for k, v in body.updates.items():
        if k not in ALLOWED:
            continue
        sets.append(f"{k} = :{k}")
        params[k] = v
    if not sets:
        return {"updated": 0, "error": "No valid fields to update"}

    try:
        with engine.begin() as conn:
            sql = text(f"UPDATE brand_coverage SET {', '.join(sets)} WHERE brand_slug = :slug")
            result = conn.execute(sql, params)
            return {"updated": result.rowcount, "brand_slug": body.brand_slug}
    except Exception as e:
        return {"error": str(e)[:500]}


class SyncIngredientCategoriesRequest(BaseModel):
    secret: str
    updates: list[dict]  # [{canonical_name: str, category: str}, ...]


@router.post("/sync-ingredient-categories")
def sync_ingredient_categories(body: SyncIngredientCategoriesRequest):
    """Update ingredient.category by canonical_name match (case-insensitive)."""
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    if not body.updates:
        return {"updated": 0}

    engine = get_engine()
    updated = 0
    not_found = 0
    try:
        with engine.begin() as conn:
            for u in body.updates:
                name = u.get("canonical_name")
                cat = u.get("category")
                if not name or not cat:
                    continue
                r = conn.execute(text("""
                    UPDATE ingredients SET category = :cat
                    WHERE LOWER(canonical_name) = LOWER(:n)
                """), {"cat": cat, "n": name})
                if r.rowcount > 0:
                    updated += r.rowcount
                else:
                    not_found += 1
    except Exception as e:
        return {"error": str(e)[:500], "updated": updated}

    return {"updated": updated, "not_matched": not_found}


class SeedCompatRequest(BaseModel):
    secret: str


@router.post("/seed-compatibility-matrix")
def seed_compatibility_matrix(body: SeedCompatRequest):
    """Seed ingredient_category_compatibility table from YAML config.

    Idempotent: clears existing rows then re-inserts. Run after Alembic
    migration creates the table.
    """
    if not MIGRATION_SECRET or body.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid migration secret")

    import yaml
    from pathlib import Path

    yaml_path = Path("config/ingredient_compatibility.yaml")
    if not yaml_path.exists():
        return {"error": "ingredient_compatibility.yaml not found"}

    data = yaml.safe_load(yaml_path.read_text())
    categories = data.get("categories", {})

    engine = get_engine()
    inserted = 0
    try:
        with engine.begin() as conn:
            # Ensure table exists (defensive — Alembic should have created it)
            try:
                conn.execute(text("DELETE FROM ingredient_category_compatibility"))
            except Exception:
                # Table doesn't exist — bail with clear message
                return {"error": "Table ingredient_category_compatibility not found. Run Alembic migration first."}

            for cat, info in categories.items():
                by_hair = info.get("by_hair_type", {}) or {}
                for hair_type, entry in by_hair.items():
                    conn.execute(text("""
                        INSERT INTO ingredient_category_compatibility (category, hair_type, score, reason)
                        VALUES (:cat, :ht, :sc, :rs)
                    """), {"cat": cat, "ht": hair_type, "sc": entry["score"], "rs": entry.get("reason", "")})
                    inserted += 1
    except Exception as e:
        return {"error": str(e)[:500], "inserted": inserted}

    return {"inserted": inserted, "categories": len(categories)}


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
