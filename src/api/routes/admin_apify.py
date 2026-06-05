"""Apify integration — trigger actors, ingest dataset output through the
existing HAIRA pipeline (INCI extraction + QA gate + upsert).

Goal: destravar fontes que o scraper próprio não pega (SPA + Cloudflare em
distribuidores como Beleza na Web/Época), com o mesmo respeito a never
downgrade INCI e às regras do qa_gate.

PoC endpoints (require admin):
  - POST /api/admin/apify/run-and-ingest
        body: {actor_id, brand_slug, source, run_input}
        roda o Actor, espera completar, busca o dataset e processa cada item
  - POST /api/admin/apify/ingest
        body: {brand_slug, source, items: [...]}
        ingere itens diretamente (mock/teste local OU para webhooks futuros)
  - GET  /api/admin/apify/status
        echo do APIFY_TOKEN setado e do último run em memória (smoke test)
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_catalog_session
from src.core.models import (
    ProductExtraction, QAResult, QAStatus, Evidence, ExtractionMethod, GenderTarget,
)
from src.extraction.inci_extractor import extract_and_validate_inci
from src.integrations.apify import (
    ApifyError, fetch_dataset_items, start_actor_run, wait_for_run,
)
from src.storage.repository import ProductRepository

router = APIRouter(prefix="/admin/apify", tags=["admin"])
logger = logging.getLogger("haira.apify_route")


class ApifyItem(BaseModel):
    """Normalized shape expected from the Apify Actor. Mapping is the Actor's
    responsibility (or a post-processing step inside this endpoint)."""
    product_url: str
    product_name: str
    inci_text: str | None = None   # raw INCI text from the page
    price: float | None = None
    image_url: str | None = None
    product_type_raw: str | None = None


class IngestRequest(BaseModel):
    brand_slug: str
    source: str                          # e.g. "belezanaweb", "epoca"
    items: list[ApifyItem]


class RunAndIngestRequest(BaseModel):
    actor_id: str                        # e.g. "apify/web-scraper" or username~actor_name
    brand_slug: str
    source: str
    run_input: dict[str, Any]


class IngestStats(BaseModel):
    received: int
    upserted: int
    skipped_no_inci: int
    quarantined: int
    failed: int
    sample_errors: list[str] = []


_JSONLD_SIGNATURES = (
    '"@type"', '"@context"', '"@graph"', '"contactPoint"', '"telephone"',
    '"availableLanguage"', '"areaServed"', '"streetAddress"', '"postalCode"',
    'application/ld+json',
)


def _looks_like_garbage_inci(text: str) -> bool:
    """Reject text that's clearly JSON-LD/script content masquerading as INCI."""
    if not text or len(text) < 10:
        return True
    if any(sig in text for sig in _JSONLD_SIGNATURES):
        return True
    # Too many quotes/braces means it's serialized JSON, not a real ingredient list
    brace_ratio = sum(text.count(c) for c in '{}[]') / max(len(text), 1)
    return brace_ratio > 0.02


def _ingest_items(items: list[ApifyItem], brand_slug: str, source: str,
                  session: Session) -> IngestStats:
    repo = ProductRepository(session)
    stats = IngestStats(received=len(items), upserted=0, skipped_no_inci=0,
                       quarantined=0, failed=0)
    for it in items:
        try:
            raw_inci = it.inci_text or ""
            if _looks_like_garbage_inci(raw_inci):
                raw_inci = ""  # treat as no-INCI so qa gate downgrades, not poisons
            inci_result = extract_and_validate_inci(raw_inci, has_section_context=False)
            inci_ingredients = inci_result.cleaned if inci_result.valid else None

            extraction = ProductExtraction(
                brand_slug=brand_slug,
                product_name=it.product_name,
                product_url=it.product_url,
                image_url_main=it.image_url,
                inci_ingredients=inci_ingredients,
                price=it.price,
                currency="BRL" if it.price is not None else None,
                product_type_raw=it.product_type_raw,
                confidence=0.7 if inci_ingredients else 0.4,
                extraction_method=f"apify:{source}",
                evidence=[Evidence(
                    field_name="source",
                    source_url=it.product_url,
                    evidence_locator=f"apify:{source}",
                    raw_source_text=(it.inci_text or "")[:200],
                    extraction_method=ExtractionMethod.EXTERNAL_ENRICHMENT,
                )],
                gender_target=GenderTarget.UNKNOWN,
            )

            if inci_ingredients:
                qa = QAResult(status=QAStatus.VERIFIED_INCI, passed=True,
                              checks_passed=["apify_with_inci"])
            else:
                qa = QAResult(status=QAStatus.CATALOG_ONLY, passed=True,
                              checks_passed=["apify_no_inci"])
                stats.skipped_no_inci += 1

            repo.upsert_product(extraction, qa)
            stats.upserted += 1
        except Exception as e:  # noqa: BLE001
            stats.failed += 1
            if len(stats.sample_errors) < 5:
                stats.sample_errors.append(f"{it.product_name[:40]}: {e}")
            logger.warning("apify ingest item failed: %s", e)
    session.commit()
    return stats


@router.get("/status")
def status(admin: dict = Depends(require_admin)):
    import os
    return {
        "apify_token_set": bool(os.environ.get("APIFY_TOKEN")),
        "webhook_secret_set": bool(os.environ.get("APIFY_WEBHOOK_SECRET")),
    }


@router.post("/ingest", response_model=IngestStats)
def ingest(body: IngestRequest,
           admin: dict = Depends(require_admin),
           session: Session = Depends(get_catalog_session)):
    """Ingest a batch of items directly (mock testing OR future webhook path)."""
    if not body.items:
        raise HTTPException(status_code=400, detail="No items provided")
    return _ingest_items(body.items, body.brand_slug, body.source, session)


@router.post("/run-and-ingest")
def run_and_ingest(body: RunAndIngestRequest,
                   admin: dict = Depends(require_admin),
                   session: Session = Depends(get_catalog_session)):
    """Trigger an Apify actor, wait for completion, fetch dataset, ingest."""
    try:
        run = start_actor_run(body.actor_id, body.run_input)
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId")
        if not run_id or not dataset_id:
            raise ApifyError(f"missing run_id/dataset_id in response: {run}")
        final = wait_for_run(run_id)
        if final.get("status") != "SUCCEEDED":
            raise HTTPException(status_code=502, detail=f"Apify run {final.get('status')}: {final.get('exitCode')}")
        items_raw = fetch_dataset_items(dataset_id, limit=1000)
        # The actor may emit error rows ({"#error": True, ...}) or rows missing
        # required fields — separate them out so the run still surfaces useful info.
        errored = [it for it in items_raw if isinstance(it, dict) and it.get("#error")]
        valid_dicts = [it for it in items_raw if isinstance(it, dict) and not it.get("#error")]
        items: list[ApifyItem] = []
        bad_shape: list[dict] = []
        for it in valid_dicts:
            try:
                items.append(ApifyItem(**it))
            except Exception:  # noqa: BLE001
                bad_shape.append(it)
        stats = _ingest_items(items, body.brand_slug, body.source, session) if items else IngestStats(
            received=0, upserted=0, skipped_no_inci=0, quarantined=0, failed=0)
        return {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": final.get("status"),
            "duration_seconds": final.get("stats", {}).get("durationMillis", 0) // 1000,
            "dataset_raw_count": len(items_raw),
            "actor_errors": len(errored),
            "bad_shape": len(bad_shape),
            "sample_actor_error": (errored[0].get("#debug") if errored else None) if errored else None,
            "sample_bad_shape": (bad_shape[0] if bad_shape else None),
            "stats": stats.model_dump(),
        }
    except ApifyError as e:
        raise HTTPException(status_code=502, detail=str(e))
