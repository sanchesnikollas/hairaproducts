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
            # requires_js: true → usar Playwright (sem use_httpx) para
            # marcas com SPA/Next.js (Pantene, Granado deco.cx).
            browser = BrowserClient(
                headless=extraction_config.get("headless", True),
                ssl_verify=ssl_verify,
            )

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

        # Refresh the denormalised counter so the /api/brands list view shows
        # the new numbers immediately. Routes by storage mode: central
        # BrandDatabaseORM when multi-DB, BrandCoverageORM when single-DB.
        # (See HAIRA-143 comment 2026-06-01 — reviewers saw "tabela 27, link
        # 112" before this hook existed.)
        try:
            from src.api.dependencies import is_multi_db as _is_multi_db
            from src.storage.central_sync import (
                sync_brand_counters,
                sync_brand_coverage,
            )

            if _is_multi_db():
                from src.api.dependencies import get_router as _get_router
                sync_result = sync_brand_counters(_get_router(), brand)
            else:
                with SASession(db_engine) as _sync_sess:
                    sync_result = sync_brand_coverage(_sync_sess, brand)
            _jobs[job_id]["central_sync"] = {
                "previous_count": sync_result.previous_count,
                "new_count": sync_result.new_count,
                "previous_rate": round(sync_result.previous_rate, 4),
                "new_rate": round(sync_result.new_rate, 4),
                "changed": sync_result.changed,
                "error": sync_result.error,
            }
        except Exception as sync_exc:  # never block a successful scrape
            logger.warning("counter sync skipped for %s: %s", brand, sync_exc)
            _jobs[job_id]["central_sync"] = {"error": str(sync_exc)}

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


class CleanupRequest(BaseModel):
    secret: str
    dry_run: bool = False  # when True, retorna preview sem aplicar UPDATE


@router.post("/cleanup/junk-products")
def cleanup_junk_products(req: CleanupRequest):
    """Quarentena retroativa de produtos com nomes lixo (artigos, hashtags,
    erros HTTP, acessórios, embalagens).

    Reflete os filtros do qa_gate.GARBAGE_NAMES + GARBAGE_PATTERNS +
    taxonomy.EXCLUDE_KEYWORDS aplicados aos produtos já existentes em
    banco que entraram antes do filtro ser deployado.
    """
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    from sqlalchemy import text
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine

    # Proteção: não quarentenar produtos que têm CLARAMENTE palavra-chave de
    # cabelo + indicador de produto (volume, kit, combo com cabelo) — evita
    # falso positivo em linhas masculinas (Malbec/Zaad/Arbo) que têm sub-produtos
    # capilares legítimos junto com perfume/desodorante na mesma linha.
    safe_clause = """
      NOT (
        product_name ~* '\\b(shampoo|xampu|condicionador|m[aá]scara\\s+(capilar|para\\s+cabelo|hidrat|nutri|reconstr)|leave-?in|creme\\s+(para|de)\\s+pentear|[óo]leo\\s+(capilar|para\\s+cabelo)|finalizador|defrizante|reconstrutor)\\b'
        AND product_name ~* '\\d+\\s*(ml|g|kg|l)\\b'
      )
    """
    where_clause = f"""
      verification_status <> 'quarantined'
      AND {safe_clause}
      AND (
           product_name LIKE '#%'
        OR product_name ~* '\\m\\d+\\s+dicas?\\M'
        OR product_name ~* '^\\s*como\\s+(tratar|fazer|cuidar|usar|hidratar|escolher|aplicar)'
        OR product_name ~* '^\\s*(vai|posso|devo|deve|pode|quem|qual)\\M.*\\?\\s*$'
        OR product_name ~* '^\\s*(shampoos|condicionadores|m[aá]scaras|cremes|[óo]leos|tratamentos|finalizadores|modeladores|leave-?ins|tonicos|t[oô]nicos|produtos|esmaltes|kits)\\s+'
        OR product_name ~* '^\\s*(linha|cole[çc][aã]o|s[ée]rie)\\s+'
        OR product_name ~* '^\\s*(brinde|amostra|sample|teste)\\M'
        OR product_name ~* 'venda\\s+proibida'
        OR product_name ~* '^\\s*pr[ée]-?venda\\s*$'
        -- Padrões novos: validate_product_name_quality em SQL
        OR product_name ~ '[✨🌟💫⭐🎁💝🌸💚🔥🎉😍]'
        OR product_name ~* '^\\s*(crie|descubra|conhe[çc]a|aproveite|garanta|adquira|compre)\\s+'
        OR product_name ~ '^\\s*[a-z][a-zçãáéíóúâêôõà\\s]+$'  -- tudo lower (extração suja)
        OR product_name ~* '^\\s*(cronograma|rotina|pr[ée]\\s*/\\s*p[oó]s|pr[ée]\\s+p[oó]s)\\b'
        OR product_name ~* '\\bou\\s+(cacheamento|alisamento|loiro|liso|crespo|ondulado)\\b'
        OR LOWER(product_name) = 'oral care'
        OR (product_name ~ '\\?\\s*$' AND LENGTH(product_name) < 50)  -- pergunta curta
        OR (product_name ~ '!\\s*$' AND LENGTH(product_name) < 35)    -- exclamação curta (CTA)
        -- Não-capilares (faciais, unhas, acessórios, perfumes)
        OR LOWER(product_name) LIKE '%lenço%' OR LOWER(product_name) LIKE '%lenco %'
        OR LOWER(product_name) LIKE '%tesoura%' OR LOWER(product_name) LIKE '%navalhete%'
        OR LOWER(product_name) LIKE '%navalha%' OR LOWER(product_name) LIKE '%alicate%'
        OR LOWER(product_name) LIKE '% unha%' OR LOWER(product_name) LIKE '%unhas%'
        OR LOWER(product_name) LIKE '%esmalte%' OR LOWER(product_name) LIKE '%cílio%'
        OR LOWER(product_name) LIKE '%cilio%' OR LOWER(product_name) LIKE '%roupão%'
        OR LOWER(product_name) LIKE '%roupao%' OR LOWER(product_name) LIKE '%frasqueira%'
        OR LOWER(product_name) LIKE '%mochila%' OR LOWER(product_name) LIKE '%malbec%'
        OR LOWER(product_name) LIKE '%glam by camila%' OR LOWER(product_name) LIKE '%by camila queiroz%'
        OR LOWER(product_name) LIKE '%talco%' OR LOWER(product_name) LIKE '%antitranspirante%'
        OR LOWER(product_name) LIKE '%deo col%'
        OR LOWER(product_name) LIKE '%palito%'
        OR LOWER(product_name) LIKE '%sobrancelha%' OR LOWER(product_name) LIKE '%maquiagem%'
        OR LOWER(product_name) LIKE '%batom%' OR LOWER(product_name) LIKE '%rimel%'
        OR LOWER(product_name) LIKE '%rímel%' OR LOWER(product_name) LIKE '%blush%'
        OR LOWER(product_name) LIKE '%sombra %'
        -- Acessórios de salão e equipamentos (Belliz/Vertix/Ricca)
        OR LOWER(product_name) LIKE '%capa de corte%' OR LOWER(product_name) LIKE '%capa para corte%'
        OR LOWER(product_name) LIKE 'pincel %' OR LOWER(product_name) LIKE '%pinceis%'
        OR LOWER(product_name) LIKE '%lip oil%' OR LOWER(product_name) LIKE '%magic lip%'
        OR LOWER(product_name) LIKE '%labial%'
        OR LOWER(product_name) LIKE '%difusor de cachos%'
        OR LOWER(product_name) LIKE '%chapa de cabelo%' OR LOWER(product_name) LIKE '%chapa profissional%'
        OR LOWER(product_name) LIKE '%lixa %' OR LOWER(product_name) LIKE '%lixas %'
        OR LOWER(product_name) LIKE 'grampo %' OR LOWER(product_name) LIKE '%piranha %'
        OR LOWER(product_name) LIKE '%piranha ricca%' OR LOWER(product_name) LIKE '%piranhas %'
        OR LOWER(product_name) LIKE '%lamina%' OR LOWER(product_name) LIKE '%lâmina%'
        OR LOWER(product_name) LIKE '%bruma corporal%' OR LOWER(product_name) LIKE '%ice mist%'
        OR LOWER(product_name) LIKE '%creme desodorante%' OR LOWER(product_name) LIKE '%creme das mãos%'
        OR LOWER(product_name) LIKE '%hand cream%' OR LOWER(product_name) LIKE '%creme para mãos%'
        OR LOWER(product_name) LIKE 'elastico %' OR LOWER(product_name) LIKE 'elasticos%'
        OR LOWER(product_name) LIKE 'elástico %' OR LOWER(product_name) LIKE 'elásticos%'
        OR LOWER(product_name) LIKE '%cuba flexivel%' OR LOWER(product_name) LIKE '%cuba flexível%'
        OR LOWER(product_name) LIKE 'esc %' OR LOWER(product_name) LIKE 'esc.%'
        OR LOWER(product_name) LIKE '%rede de cabelo%'
        OR LOWER(product_name) LIKE '%álbum%' OR LOWER(product_name) LIKE '%álbums%'
        OR LOWER(product_name) LIKE '%agua micelar%' OR LOWER(product_name) LIKE '%água micelar%'
        -- Categorias genéricas (só uma palavra ou começa com termo coletivo)
        OR LOWER(product_name) = 'tratamentos'
        OR LOWER(product_name) = 'tratamento'
        OR LOWER(product_name) ~ '^cuidado(s)?\\s+para\\s+(os?\\s+)?cabelos?$'
        OR LOWER(product_name) ~ '^(festivais?|festas?|verão|inverno|primavera|outono)\\s+(e|com|para)\\s+cabelos?$'
        OR LOWER(product_name) ~ '^(blonde|loiro)\\s+hair$'
        OR product_name ~* '^[A-Z\\s]{3,}\\s*$' AND LENGTH(TRIM(product_name)) < 25
            AND product_name !~* '\\d+\\s*(ml|g|kg)\\b'  -- maiúsculas curtas sem volume
        -- Nome é apenas o nome da marca
        OR LOWER(product_name) = LOWER(brand_slug)
        OR LOWER(product_name) = REPLACE(LOWER(brand_slug), '-', ' ')
        OR LOWER(product_name) = 'o boticario'
        OR LOWER(product_name) = 'o boticário'
        OR LOWER(product_name) LIKE '%bad gateway%'
        OR LOWER(product_name) LIKE '%error code%'
        OR LOWER(product_name) LIKE '% 502%'
        OR LOWER(product_name) LIKE '% 503%'
        OR LOWER(product_name) LIKE '% 504%'
        OR LOWER(product_name) = 'recargas'
        OR LOWER(product_name) LIKE '%tiara%'
        OR LOWER(product_name) LIKE '%touca%'
        OR LOWER(product_name) LIKE '%bandana%'
        OR LOWER(product_name) LIKE '%presilha%'
        OR LOWER(product_name) LIKE '%pente %'
        OR LOWER(product_name) LIKE '%escova %'
        OR LOWER(product_name) LIKE '%secador%'
        OR LOWER(product_name) LIKE '%babyliss%'
        OR LOWER(product_name) LIKE '%chapinha%'
        OR LOWER(product_name) LIKE '%prancha%'
        OR LOWER(product_name) LIKE '%nécessaire%'
        OR LOWER(product_name) LIKE '%necessaire%'
        OR LOWER(product_name) LIKE '%bolsa%'
        OR LOWER(product_name) LIKE '%estojo%'
        -- URLs com query string de filtro de categoria (não são produtos)
        OR product_url LIKE '%?%nota-da-avaliacao=%'
        OR product_url LIKE '%?%condicao-dos-fios=%'
        OR product_url LIKE '%?%tipos-de-cabelo=%'
        OR product_url LIKE '%?%propriedades=%'
        OR product_url LIKE '%?%departamento-categoria=%'
        OR product_url LIKE '%?%indexar=falso%'
      )
    """
    engine = get_engine()
    with SASession(engine) as session:
        count = session.execute(
            text(f"SELECT COUNT(*) FROM products WHERE {where_clause}")
        ).scalar()
        sample_rows = session.execute(
            text(f"SELECT brand_slug, product_name FROM products WHERE {where_clause} LIMIT 30")
        ).fetchall()
        sample = [{"brand_slug": r[0], "product_name": r[1]} for r in sample_rows]

        if req.dry_run:
            return {
                "dry_run": True,
                "to_quarantine": count,
                "sample": sample,
            }

        result = session.execute(
            text(
                f"UPDATE products SET verification_status='quarantined' "
                f"WHERE {where_clause}"
            )
        )
        session.commit()

        # Status counts after
        rows = session.execute(
            text("SELECT verification_status, COUNT(*) FROM products GROUP BY 1 ORDER BY 2 DESC")
        ).fetchall()
        status_counts = {r[0]: r[1] for r in rows}

        return {
            "dry_run": False,
            "quarantined": result.rowcount,
            "sample_before": sample,
            "status_counts_after": status_counts,
        }


class SyncCoverageRequest(BaseModel):
    secret: str


@router.post("/sync-brand-coverage")
def sync_brand_coverage_endpoint(req: SyncCoverageRequest):
    """Refresh os contadores cached da tabela brand_coverage.

    A tabela brand_coverage é atualizada por sync_brand_coverage() depois
    de cada scrape, mas cleanups manuais (POST /cleanup/junk-products) e
    edits ops não disparam refresh. Esse endpoint força sync de todas as
    marcas pra contagem ficar coerente com products real.
    """
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    from src.storage.central_sync import sync_all_coverage

    engine = get_engine()
    with SASession(engine) as session:
        results = sync_all_coverage(session)
        session.commit()
        summary = {
            "brands_synced": len(results),
            "total_changed": sum(1 for r in results if getattr(r, "changed", False)),
            "errors": [getattr(r, "error", None) for r in results if getattr(r, "error", None)],
        }
        return summary


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


class MigrateGenericRequest(BaseModel):
    secret: str
    table: str  # "evidence" or "quarantine"
    records: list[dict]


@router.post("/migrate-generic")
def migrate_generic(req: MigrateGenericRequest):
    """Import evidence or quarantine records from JSON payload."""
    if not MIGRATION_SECRET or req.secret != MIGRATION_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    from datetime import datetime
    from sqlalchemy.orm import Session as SASession
    from src.storage.database import get_engine
    from src.storage.orm_models import ProductEvidenceORM, QuarantineDetailORM

    table_map = {
        "evidence": ProductEvidenceORM,
        "quarantine": QuarantineDetailORM,
    }
    Model = table_map.get(req.table)
    if not Model:
        raise HTTPException(status_code=400, detail=f"Unknown table: {req.table}")

    engine = get_engine()
    inserted = 0
    skipped = 0

    datetime_cols = {c.key for c in Model.__table__.columns if "datetime" in str(c.type).lower() or c.key.endswith("_at")}

    with SASession(engine) as session:
        with session.no_autoflush:
            for row in req.records:
                record_id = row.get("id")
                if not record_id:
                    continue

                for key in datetime_cols:
                    val = row.get(key)
                    if isinstance(val, str):
                        try:
                            row[key] = datetime.fromisoformat(val)
                        except (ValueError, TypeError):
                            row[key] = None

                session.merge(Model(**row))
                inserted += 1

                if inserted % 500 == 0:
                    session.flush()

        session.commit()

    return {"table": req.table, "inserted": inserted, "skipped": skipped}
