"""Remote scrape trigger endpoint.

Protected by MIGRATION_SECRET env var. Runs scrape/labels in background thread.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("haira.admin_scrape")

router = APIRouter(prefix="/admin", tags=["admin"])

MIGRATION_SECRET = os.environ.get("MIGRATION_SECRET", "")

# Track running jobs
_jobs: dict[str, dict[str, Any]] = {}


class ScrapeRequest(BaseModel):
    secret: str
    brand: str
    run_labels: bool = True
    force: bool = False  # Required for brands with >50 verified products


class JobStatus(BaseModel):
    secret: str
    job_id: str | None = None


def _run_scrape(job_id: str, brand: str, run_labels: bool) -> None:
    """Run scrape + labels in background thread.

    Mirrors the CLI scrape command flow: load blueprint, discover URLs,
    create browser, run coverage engine, optionally run labels.
    """
    try:
        _jobs[job_id]["status"] = "discovering"
        logger.info("Starting scrape for %s (job %s)", brand, job_id)

        from pathlib import Path
        from sqlalchemy.orm import Session as SASession

        from src.discovery.blueprint_engine import load_blueprint
        from src.discovery.product_discoverer import ProductDiscoverer
        from src.pipeline.coverage_engine import CoverageEngine
        from src.storage.database import get_engine as get_db_engine
        from src.storage.orm_models import Base

        # Load blueprint
        bp = load_blueprint(brand)
        if not bp:
            raise ValueError(f"No blueprint found for {brand}")

        # Initialize DB
        db_engine = get_db_engine()
        Base.metadata.create_all(db_engine)

        # Setup browser based on blueprint config
        extraction_config = bp.get("extraction", {})
        ssl_verify = extraction_config.get("ssl_verify", True)
        http_client = extraction_config.get("http_client", "")

        from src.core.browser import BrowserClient
        if http_client == "curl_cffi":
            browser = BrowserClient(use_curl_cffi=True, ssl_verify=ssl_verify)
        elif not extraction_config.get("requires_js", True):
            browser = BrowserClient(use_httpx=True, ssl_verify=ssl_verify)
        else:
            browser = BrowserClient(use_httpx=True, ssl_verify=ssl_verify)

        # Discover URLs
        discoverer = ProductDiscoverer(browser=browser)
        discovered = discoverer.discover(bp)
        _jobs[job_id]["discovered"] = len(discovered)
        logger.info("Discovered %d URLs for %s", len(discovered), brand)

        if not discovered:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["scrape_result"] = {"discovered": 0, "extracted": 0, "verified": 0}
            return

        url_dicts = [{"url": d.url} for d in discovered]

        # Check existing verified count BEFORE scrape (for safety comparison)
        from src.storage.orm_models import ProductORM
        with SASession(db_engine) as session:
            existing_verified = (
                session.query(ProductORM)
                .filter(
                    ProductORM.brand_slug == brand,
                    ProductORM.verification_status == "verified_inci",
                )
                .count()
            )
        _jobs[job_id]["existing_verified"] = existing_verified

        # Run coverage engine
        _jobs[job_id]["status"] = "scraping"
        with SASession(db_engine) as session:
            cov_engine = CoverageEngine(session=session, browser=browser)
            report = cov_engine.process_brand(brand, bp, url_dicts)

        _jobs[job_id]["scrape_result"] = {
            "discovered": report.discovered_total,
            "extracted": report.extracted_total,
            "verified": report.verified_inci_total,
            "verified_rate": f"{report.verified_inci_rate:.1%}",
            "catalog_only": report.catalog_only_total,
            "quarantined": report.quarantined_total,
            "previous_verified": existing_verified,
        }

        # Safety check: warn if scrape resulted in fewer verified products
        if report.verified_inci_total < existing_verified:
            logger.warning(
                "SAFETY: scrape for %s resulted in FEWER verified products (%d -> %d). "
                "Existing data preserved by never-downgrade rule.",
                brand, existing_verified, report.verified_inci_total,
            )

        # Run labels
        if run_labels:
            _jobs[job_id]["status"] = "labeling"
            logger.info("Running labels for %s (job %s)", brand, job_id)

            from src.core.label_engine import LabelEngine
            from src.storage.repository import ProductRepository

            with SASession(db_engine) as session:
                repo = ProductRepository(session)
                products = repo.get_products(brand_slug=brand)
                label_engine = LabelEngine()
                updated = 0
                for p in products:
                    if p.inci_ingredients:
                        labels = label_engine.detect(
                            description=p.description,
                            product_name=p.product_name,
                            benefits_claims=p.benefits_claims,
                            usage_instructions=p.usage_instructions,
                            inci_ingredients=p.inci_ingredients,
                        )
                        repo.update_product_labels(p.id, labels.to_dict())
                        updated += 1
                session.commit()
                _jobs[job_id]["labels_updated"] = updated

        _jobs[job_id]["status"] = "done"
        logger.info("Job %s complete for %s", job_id, brand)

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
        logger.error("Job %s failed for %s: %s", job_id, brand, e, exc_info=True)


@router.post("/scrape")
def trigger_scrape(req: ScrapeRequest):
    """Trigger a scrape for a brand. Runs in background."""
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    job_id = f"{req.brand}-{int(time.time())}"

    if any(j["brand"] == req.brand and j["status"] in ("scraping", "labeling", "discovering")
           for j in _jobs.values()):
        raise HTTPException(status_code=409, detail=f"Scrape already running for {req.brand}")

    # Safety guard: require force=true for brands with existing verified data
    if not req.force:
        from src.storage.database import get_engine as _get_engine
        from src.storage.orm_models import Base as _Base, ProductORM as _ProductORM
        from sqlalchemy.orm import Session as _Session
        _eng = _get_engine()
        _Base.metadata.create_all(_eng)
        with _Session(_eng) as _sess:
            _existing = _sess.query(_ProductORM).filter(
                _ProductORM.brand_slug == req.brand,
                _ProductORM.verification_status == "verified_inci",
            ).count()
        if _existing > 50:
            raise HTTPException(
                status_code=400,
                detail=f"Brand {req.brand} has {_existing} verified products. "
                       f"Use force=true to re-scrape. Never-downgrade rule is active.",
            )

    _jobs[job_id] = {
        "brand": req.brand,
        "status": "queued",
        "started_at": time.time(),
        "run_labels": req.run_labels,
    }

    thread = threading.Thread(target=_run_scrape, args=(job_id, req.brand, req.run_labels), daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "queued", "brand": req.brand}


@router.post("/scrape/status")
def scrape_status(req: JobStatus):
    """Check status of scrape jobs."""
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    if req.job_id:
        job = _jobs.get(req.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"job_id": req.job_id, **job}

    # Return all jobs
    return {"jobs": {k: v for k, v in _jobs.items()}}


class MigrateRequest(BaseModel):
    secret: str
    products: list[dict]


@router.post("/migrate")
def migrate_products(req: MigrateRequest):
    """Import products from JSON payload into production DB."""
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    from datetime import datetime, timezone
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    from src.storage.orm_models import ProductORM, BrandCoverageORM

    engine = get_engine()
    datetime_cols = {"extracted_at", "created_at", "updated_at"}
    inserted = 0
    updated = 0
    skipped = 0

    with SASession(engine) as session:
        with session.no_autoflush:
            for row in req.products:
                product_id = row.get("id")
                if not product_id:
                    continue

                try:
                    existing = (
                        session.query(ProductORM).filter(ProductORM.id == product_id).first()
                        or session.query(ProductORM).filter(
                            ProductORM.product_url == row.get("product_url")
                        ).first()
                    )
                except Exception:
                    existing = None

                if existing:
                    if existing.verification_status == "verified_inci":
                        skipped += 1
                        continue
                    for key, val in row.items():
                        if key in ("id", "created_at"):
                            continue
                        if key in datetime_cols and isinstance(val, str):
                            try:
                                val = datetime.fromisoformat(val)
                            except (ValueError, TypeError):
                                val = None
                        setattr(existing, key, val)
                    updated += 1
                else:
                    for key in datetime_cols:
                        val = row.get(key)
                        if isinstance(val, str):
                            try:
                                row[key] = datetime.fromisoformat(val)
                            except (ValueError, TypeError):
                                row[key] = None
                    for key in datetime_cols:
                        if key in row and row[key] is None:
                            del row[key]
                    product = ProductORM(**row)
                    session.merge(product)
                    inserted += 1

                if (inserted + updated) % 100 == 0:
                    session.flush()

        session.commit()

        # Update coverage
        brand_slugs = list({r["brand_slug"] for r in req.products if r.get("brand_slug")})
        for slug in brand_slugs:
            total = session.query(ProductORM).filter(ProductORM.brand_slug == slug).count()
            verified = session.query(ProductORM).filter(
                ProductORM.brand_slug == slug,
                ProductORM.verification_status == "verified_inci",
            ).count()
            catalog = session.query(ProductORM).filter(
                ProductORM.brand_slug == slug,
                ProductORM.verification_status == "catalog_only",
            ).count()

            coverage = session.query(BrandCoverageORM).filter(
                BrandCoverageORM.brand_slug == slug
            ).first()
            if coverage:
                coverage.extracted_total = total
                coverage.verified_inci_total = verified
                coverage.catalog_only_total = catalog
                coverage.verified_inci_rate = verified / total if total > 0 else 0
                coverage.last_run = datetime.now(timezone.utc)
            else:
                coverage = BrandCoverageORM(
                    brand_slug=slug,
                    extracted_total=total,
                    verified_inci_total=verified,
                    catalog_only_total=catalog,
                    verified_inci_rate=verified / total if total > 0 else 0,
                    status="done",
                )
                session.add(coverage)
            session.commit()

    return {"inserted": inserted, "updated": updated, "skipped": skipped, "brands": brand_slugs}


class MigrateExternalInciRequest(BaseModel):
    secret: str
    records: list[dict]


@router.post("/migrate-external-inci")
def migrate_external_inci(req: MigrateExternalInciRequest):
    """Import external INCI records from JSON payload."""
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    from datetime import datetime
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    from src.storage.orm_models import ExternalInciORM

    engine = get_engine()
    inserted = 0
    skipped = 0

    with SASession(engine) as session:
        for row in req.records:
            record_id = row.get("id")
            if not record_id:
                continue

            existing = session.query(ExternalInciORM).filter(ExternalInciORM.id == record_id).first()
            if existing:
                skipped += 1
                continue

            for key in ("scraped_at", "updated_at"):
                val = row.get(key)
                if isinstance(val, str):
                    try:
                        row[key] = datetime.fromisoformat(val)
                    except (ValueError, TypeError):
                        row[key] = None

            session.merge(ExternalInciORM(**row))
            inserted += 1

        session.commit()

    return {"inserted": inserted, "skipped": skipped}
