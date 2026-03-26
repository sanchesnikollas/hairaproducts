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
    """Run scrape + labels in background thread.

    Mirrors the CLI scrape command flow: load blueprint, discover URLs,
    create browser, run coverage engine, optionally run labels.
    """
    try:
        _jobs[job_id]["status"] = "discovering"
        logger.info("Starting scrape for %s (job %s)", brand, job_id)

        from pathlib import Path
        from sqlalchemy.orm import Session as SASession

        from src.core.blueprint import load_blueprint
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
        }

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
        logger.error("Job %s failed for %s: %s", job_id, brand, e, exc_info=True)


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
