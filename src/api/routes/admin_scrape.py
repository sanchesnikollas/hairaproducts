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


class JobStatus(BaseModel):
    secret: str
    job_id: str | None = None


def _run_scrape(job_id: str, brand: str, run_labels: bool) -> None:
    """Run scrape + labels in background thread."""
    try:
        _jobs[job_id]["status"] = "scraping"
        logger.info("Starting scrape for %s (job %s)", brand, job_id)

        from src.pipeline.coverage_engine import CoverageEngine
        engine = CoverageEngine()
        result = engine.process_brand(brand)

        _jobs[job_id]["scrape_result"] = {
            "extracted": result.get("extracted", 0),
            "verified": result.get("verified_inci", 0),
            "catalog_only": result.get("catalog_only", 0),
            "quarantined": result.get("quarantined", 0),
        }

        if run_labels:
            _jobs[job_id]["status"] = "labeling"
            logger.info("Running labels for %s (job %s)", brand, job_id)

            from src.core.label_engine import LabelEngine
            from src.storage.database import get_engine as get_db_engine
            from src.storage.repository import ProductRepository
            from sqlalchemy.orm import Session

            db_engine = get_db_engine()
            with Session(db_engine) as session:
                repo = ProductRepository(session)
                products = repo.get_products(brand_slug=brand)
                label_engine = LabelEngine()
                updated = 0
                for p in products:
                    if p.inci_ingredients:
                        labels = label_engine.detect_labels(p)
                        repo.update_product_labels(p.id, labels)
                        updated += 1
                session.commit()
                _jobs[job_id]["labels_updated"] = updated

        _jobs[job_id]["status"] = "done"
        logger.info("Job %s complete for %s", job_id, brand)

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
        logger.error("Job %s failed for %s: %s", job_id, brand, e)


@router.post("/scrape")
def trigger_scrape(req: ScrapeRequest):
    """Trigger a scrape for a brand. Runs in background."""
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    job_id = f"{req.brand}-{int(time.time())}"

    if any(j["brand"] == req.brand and j["status"] in ("scraping", "labeling")
           for j in _jobs.values()):
        raise HTTPException(status_code=409, detail=f"Scrape already running for {req.brand}")

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
