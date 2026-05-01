# src/cli/main.py
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from src.core.models import Brand

logger = logging.getLogger("haira")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_brand_from_registry(brand_slug: str) -> Brand | None:
    """Load a brand from config/brands.json by slug."""
    path = Path("config/brands.json")
    if not path.exists():
        return None
    with open(path) as f:
        brands_data = json.load(f)
    for b in brands_data:
        if b.get("brand_slug") == brand_slug:
            return Brand(**b)
    return None


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
def cli(log_level: str):
    """HAIRA v2 — Hair Product Intelligence Platform"""
    _setup_logging(log_level)


@cli.command("reset-password")
@click.option("--email", required=True, help="User email")
@click.option("--new-password", prompt=True, hide_input=True, confirmation_prompt=True, help="New password")
def reset_password(email: str, new_password: str):
    """Reset a user's password (admin or reviewer)."""
    import bcrypt as _bcrypt
    from src.storage.database import get_engine
    from sqlalchemy.orm import Session as SASession
    from src.storage.ops_models import UserORM

    engine = get_engine()
    with SASession(engine) as session:
        user = session.query(UserORM).filter(UserORM.email == email).first()
        if not user:
            click.echo(f"User {email} not found.")
            return
        user.password_hash = _bcrypt.hashpw(new_password.encode(), _bcrypt.gensalt()).decode()
        session.commit()
        click.echo(f"Password reset for {user.name} ({email}).")


@cli.command()
@click.option("--input", "input_path", required=True, help="Path to Excel file")
@click.option("--output", "output_path", default="config/brands.json", help="Output JSON path")
def registry(input_path: str, output_path: str):
    """Import brand registry from Excel spreadsheet."""
    from src.registry.excel_loader import load_brands_from_excel, export_brands_json

    brands = load_brands_from_excel(input_path)
    export_brands_json(brands, output_path)
    click.echo(f"Exported {len(brands)} brands to {output_path}")

    # Summary stats
    with_site = sum(1 for b in brands if b.official_url_root)
    with_priority = sum(1 for b in brands if b.priority is not None)
    click.echo(f"  With official site: {with_site}")
    click.echo(f"  Priority brands: {with_priority}")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
@click.option("--regenerate", is_flag=True, help="Force regenerate blueprint")
def blueprint(brand: str, regenerate: bool):
    """Generate or update blueprint YAML for a brand."""
    from src.discovery.blueprint_engine import (
        generate_blueprint,
        save_blueprint,
        load_blueprint,
    )

    # Check for existing blueprint
    if not regenerate:
        existing = load_blueprint(brand)
        if existing:
            click.echo(f"Blueprint already exists for {brand} (version {existing.get('version', '?')})")
            click.echo(f"  Platform: {existing.get('platform')}")
            click.echo(f"  Domain: {existing.get('domain')}")
            click.echo(f"  Entrypoints: {len(existing.get('entrypoints', []))}")
            click.echo("Use --regenerate to overwrite.")
            return

    # Load brand from registry
    brand_model = _load_brand_from_registry(brand)
    if not brand_model:
        click.echo(f"Brand '{brand}' not found in config/brands.json", err=True)
        click.echo("Run 'haira registry' first to import brands.", err=True)
        sys.exit(1)

    bp = generate_blueprint(brand_model)
    filepath = save_blueprint(bp)
    click.echo(f"Blueprint saved to {filepath}")
    click.echo(f"  Platform: {bp['platform']}")
    click.echo(f"  Domain: {bp['domain']}")
    click.echo(f"  Entrypoints: {len(bp['entrypoints'])}")
    click.echo(f"  INCI selectors: {len(bp['extraction']['inci_selectors'])}")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
@click.option("--max-urls", type=int, default=50, help="Max URLs to discover")
def recon(brand: str, max_urls: int):
    """Run discovery + small sample extraction for a brand."""
    from src.discovery.blueprint_engine import load_blueprint
    from src.discovery.product_discoverer import ProductDiscoverer
    from src.discovery.url_classifier import classify_url
    from src.storage.database import get_engine
    from src.storage.orm_models import Base

    bp = load_blueprint(brand)
    if not bp:
        click.echo(f"No blueprint found for {brand}. Run 'haira blueprint --brand {brand}' first.", err=True)
        sys.exit(1)

    click.echo(f"Running recon for {brand} ({bp['domain']})...")

    # Initialize DB
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Discover URLs
    discoverer = ProductDiscoverer()
    discovered = discoverer.discover(bp)

    click.echo(f"\nDiscovery results: {len(discovered)} URLs found")

    # Classify and show summary
    type_counts: dict[str, int] = {}
    for url_info in discovered[:max_urls]:
        url_type = classify_url(url_info.url)
        type_counts[url_type.value] = type_counts.get(url_type.value, 0) + 1

    for url_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        click.echo(f"  {url_type}: {count}")

    # Show sample URLs
    click.echo(f"\nSample product URLs:")
    sample = [u for u in discovered if not u.is_kit][:10]
    for u in sample:
        click.echo(f"  {u.url}")


@cli.command()
@click.option("--brand", help="Brand slug (single brand)")
@click.option("--priority", type=int, help="Run brands with this priority level")
@click.option("--max-brands", type=int, default=10, help="Max brands to process")
@click.option("--headless/--no-headless", default=True, help="Run browser headless")
def scrape(brand: str | None, priority: int | None, max_brands: int, headless: bool):
    """Run full scrape pipeline for brand(s)."""
    from src.discovery.blueprint_engine import load_blueprint
    from src.discovery.product_discoverer import ProductDiscoverer
    from src.pipeline.coverage_engine import CoverageEngine
    from src.storage.database import get_engine
    from src.storage.orm_models import Base
    from sqlalchemy.orm import Session as SASession

    # Initialize DB
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Determine which brands to run
    brand_slugs: list[str] = []
    if brand:
        brand_slugs = [brand]
    elif priority is not None:
        path = Path("config/brands.json")
        if not path.exists():
            click.echo("config/brands.json not found. Run 'haira registry' first.", err=True)
            sys.exit(1)
        with open(path) as f:
            brands_data = json.load(f)
        brand_slugs = [
            b["brand_slug"]
            for b in brands_data
            if b.get("priority") is not None and b["priority"] <= priority
        ][:max_brands]
    else:
        click.echo("Specify --brand or --priority", err=True)
        sys.exit(1)

    click.echo(f"Processing {len(brand_slugs)} brand(s): {', '.join(brand_slugs)}")

    # Try to set up browser
    browser = None
    try:
        from src.core.browser import BrowserClient
        browser = BrowserClient(headless=headless)
        click.echo("Browser initialized")
    except Exception as e:
        click.echo(f"Warning: Browser not available ({e}). Running without extraction.")

    # Process each brand
    for slug in brand_slugs:
        click.echo(f"\n{'='*60}")
        click.echo(f"Processing: {slug}")
        click.echo(f"{'='*60}")

        bp = load_blueprint(slug)
        if not bp:
            click.echo(f"  No blueprint for {slug}, skipping.")
            continue

        # Use httpx when blueprint says JS is not required (avoids WAF/CAPTCHA blocks)
        extraction_config = bp.get("extraction", {})
        ssl_verify = extraction_config.get("ssl_verify", True)
        http_client = extraction_config.get("http_client", "")
        brand_browser = browser
        if http_client == "curl_cffi":
            from src.core.browser import BrowserClient as BC
            brand_browser = BC(use_curl_cffi=True, ssl_verify=ssl_verify)
            click.echo("  Using curl_cffi (WAF bypass)")
        elif not extraction_config.get("requires_js", True) and extraction_config.get("headless") is False:
            from src.core.browser import BrowserClient as BC
            brand_browser = BC(use_httpx=True, ssl_verify=ssl_verify)
            click.echo("  Using httpx (requires_js=false)")
        elif not ssl_verify and browser:
            from src.core.browser import BrowserClient as BC
            brand_browser = BC(use_httpx=True, ssl_verify=False)
            click.echo("  Using httpx with ssl_verify=false")

        # Discover URLs
        discoverer = ProductDiscoverer(browser=brand_browser)
        discovered = discoverer.discover(bp)
        click.echo(f"  Discovered: {len(discovered)} URLs")

        if not discovered:
            click.echo(f"  No URLs found, skipping.")
            continue

        # Convert DiscoveredURL to dicts for coverage engine
        url_dicts = [{"url": d.url} for d in discovered]

        # Run coverage engine
        with SASession(engine) as session:
            cov_engine = CoverageEngine(session=session, browser=brand_browser)
            report = cov_engine.process_brand(slug, bp, url_dicts)

        click.echo(f"\n  Results for {slug}:")
        click.echo(f"    Discovered:    {report.discovered_total}")
        click.echo(f"    Hair products: {report.hair_total}")
        click.echo(f"    Extracted:     {report.extracted_total}")
        click.echo(f"    Verified INCI: {report.verified_inci_total} ({report.verified_inci_rate:.1%})")
        click.echo(f"    Catalog only:  {report.catalog_only_total}")
        click.echo(f"    Quarantined:   {report.quarantined_total}")
        if report.errors:
            click.echo(f"    Errors: {len(report.errors)}")
            for err in report.errors[:5]:
                click.echo(f"      - {err}")

    # Cleanup browser
    if browser:
        try:
            browser.close()
        except Exception:
            pass

    click.echo(f"\nDone.")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
def audit(brand: str):
    """Run QA audit on existing data for a brand."""
    from src.storage.database import get_engine
    from src.storage.orm_models import Base
    from src.storage.repository import ProductRepository
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    with SASession(engine) as session:
        repo = ProductRepository(session)
        products = repo.get_products(brand_slug=brand)
        coverage = repo.get_brand_coverage(brand)

    if not products and not coverage:
        click.echo(f"No data found for {brand}. Run 'haira scrape --brand {brand}' first.")
        return

    click.echo(f"Audit for {brand}:")
    click.echo(f"  Total products in DB: {len(products)}")

    if coverage:
        click.echo(f"  Coverage status: {coverage.status or 'unknown'}")
        click.echo(f"  Discovered: {coverage.discovered_total or 0}")
        click.echo(f"  Extracted: {coverage.extracted_total or 0}")
        click.echo(f"  Verified INCI: {coverage.verified_inci_total or 0}")
        rate = coverage.verified_inci_rate or 0
        click.echo(f"  Verification rate: {rate:.1%}")

    # Status breakdown
    status_counts: dict[str, int] = {}
    for p in products:
        status = p.verification_status or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    if status_counts:
        click.echo(f"  Status breakdown:")
        for status, count in sorted(status_counts.items()):
            click.echo(f"    {status}: {count}")


@cli.command(name="audit-inci")
@click.option("--brand", default=None, help="Filter by brand slug (omit for all brands)")
def audit_inci(brand: str | None):
    """Audit INCI extraction coverage and classify failure types."""
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductORM
    from sqlalchemy.orm import Session as SASession
    from collections import defaultdict

    engine = get_engine()
    Base.metadata.create_all(engine)

    with SASession(engine) as session:
        query = session.query(ProductORM)
        if brand:
            query = query.filter(ProductORM.brand_slug == brand)
        products = query.all()

        categories = {
            "already_verified": [],
            "extracted_rejected": [],
            "extraction_missed": [],
            "no_inci_on_page": [],
        }

        for p in products:
            if p.verification_status == "verified_inci" and p.inci_ingredients:
                categories["already_verified"].append(p)
            elif p.inci_ingredients:
                # Has INCI but not verified — validator rejected
                categories["extracted_rejected"].append(p)
            elif p.composition:
                # Has composition text but no INCI — extraction missed
                categories["extraction_missed"].append(p)
            else:
                categories["no_inci_on_page"].append(p)

        # Group by brand + collect sample URLs
        brand_stats = defaultdict(lambda: defaultdict(int))
        brand_samples = defaultdict(lambda: defaultdict(list))
        for cat, prods in categories.items():
            for p in prods:
                brand_stats[p.brand_slug][cat] += 1
                if len(brand_samples[p.brand_slug][cat]) < 3:
                    brand_samples[p.brand_slug][cat].append(p.product_url)

        total = len(products)
        click.echo(f"\n{'='*60}")
        click.echo(f"INCI AUDIT — {total} products")
        click.echo(f"{'='*60}\n")

        for cat, prods in categories.items():
            pct = len(prods) / total * 100 if total else 0
            click.echo(f"  {cat}: {len(prods)} ({pct:.1f}%)")

        # Recoverable products summary
        recoverable = len(categories["extracted_rejected"]) + len(categories["extraction_missed"])
        click.echo(f"\n  Recoverable (validator fix + extraction fix): {recoverable}")

        click.echo(f"\n{'─'*60}")
        click.echo("Per brand:\n")

        for b_slug in sorted(brand_stats.keys()):
            stats = brand_stats[b_slug]
            b_total = sum(stats.values())
            click.echo(f"  {b_slug} ({b_total} products):")
            for cat in ["already_verified", "extracted_rejected", "extraction_missed", "no_inci_on_page"]:
                count = stats.get(cat, 0)
                pct = count / b_total * 100 if b_total else 0
                click.echo(f"    {cat}: {count} ({pct:.0f}%)")
                # Show sample URLs for actionable categories
                if cat != "already_verified":
                    for url in brand_samples[b_slug].get(cat, []):
                        click.echo(f"      -> {url}")
            click.echo()


@cli.command()
@click.option("--brand", help="Brand slug")
@click.option("--all-brands", "all_brands", is_flag=True, help="Report for all brands")
def report(brand: str | None, all_brands: bool):
    """Generate coverage report."""
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, BrandCoverageORM
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    with SASession(engine) as session:
        if brand:
            coverages = session.query(BrandCoverageORM).filter_by(brand_slug=brand).all()
        elif all_brands:
            coverages = session.query(BrandCoverageORM).all()
        else:
            click.echo("Specify --brand or --all-brands", err=True)
            sys.exit(1)

    if not coverages:
        click.echo("No coverage data found.")
        return

    click.echo(f"\n{'Brand':<30} {'Status':<10} {'Disc':>6} {'Extr':>6} {'Verif':>6} {'Rate':>8}")
    click.echo("-" * 72)

    total_extracted = 0
    total_verified = 0

    for c in sorted(coverages, key=lambda x: x.brand_slug):
        rate = c.verified_inci_rate or 0
        click.echo(
            f"{c.brand_slug:<30} {c.status or '':<10} "
            f"{c.discovered_total or 0:>6} {c.extracted_total or 0:>6} "
            f"{c.verified_inci_total or 0:>6} {rate:>7.1%}"
        )
        total_extracted += c.extracted_total or 0
        total_verified += c.verified_inci_total or 0

    click.echo("-" * 72)
    overall_rate = total_verified / total_extracted if total_extracted > 0 else 0
    click.echo(
        f"{'TOTAL':<30} {'':<10} "
        f"{'':>6} {total_extracted:>6} "
        f"{total_verified:>6} {overall_rate:>7.1%}"
    )


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
@click.option("--limit", type=int, default=0, help="Max products to process (0 = all)")
@click.option("--dry-run", is_flag=True, help="Show results without saving to database")
def labels(brand: str, limit: int, dry_run: bool):
    """Detect product quality seals (labels) for a brand's products."""
    from src.core.label_engine import LabelEngine
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductEvidenceORM
    from src.storage.repository import ProductRepository
    from sqlalchemy.orm import Session as SASession

    engine_db = get_engine()
    Base.metadata.create_all(engine_db)
    label_engine = LabelEngine()

    with SASession(engine_db) as session:
        repo = ProductRepository(session)
        products = repo.get_products(brand_slug=brand, limit=limit if limit > 0 else 10000)

        if not products:
            click.echo(f"No products found for '{brand}'. Run 'haira scrape --brand {brand}' first.")
            return

        click.echo(f"Processing {len(products)} products for {brand}...")
        if dry_run:
            click.echo("(DRY RUN — no changes will be saved)\n")

        total = len(products)
        with_detected = 0
        with_inferred = 0
        seal_counts: dict[str, int] = {}

        for product in products:
            result = label_engine.detect(
                description=product.description,
                product_name=product.product_name,
                benefits_claims=product.benefits_claims,
                usage_instructions=product.usage_instructions,
                inci_ingredients=product.inci_ingredients,
            )

            all_seals = result.detected + result.inferred
            if result.detected:
                with_detected += 1
            if result.inferred:
                with_inferred += 1
            for seal in all_seals:
                seal_counts[seal] = seal_counts.get(seal, 0) + 1

            if dry_run:
                if all_seals:
                    click.echo(f"  {product.product_name[:60]}")
                    if result.detected:
                        click.echo(f"    detected: {', '.join(result.detected)}")
                    if result.inferred:
                        click.echo(f"    inferred: {', '.join(result.inferred)}")
                    click.echo(f"    confidence: {result.confidence}")
            else:
                repo.update_product_labels(product.id, result.to_dict())
                # Delete old label evidence to avoid duplicates on re-run
                session.query(ProductEvidenceORM).filter(
                    ProductEvidenceORM.product_id == product.id,
                    ProductEvidenceORM.field_name.like("label:%"),
                ).delete(synchronize_session=False)
                for ev in result.evidence_entries():
                    evidence_orm = ProductEvidenceORM(
                        product_id=product.id,
                        field_name=ev["field_name"],
                        source_url=product.product_url,
                        evidence_locator=ev["evidence_locator"],
                        raw_source_text=ev["raw_source_text"],
                        extraction_method=ev["extraction_method"],
                    )
                    session.add(evidence_orm)

        if not dry_run:
            session.commit()

        click.echo(f"\n{'='*60}")
        click.echo(f"Label Detection Report — {brand}")
        click.echo(f"{'='*60}")
        click.echo(f"Total products:       {total}")
        click.echo(f"With detected seals:  {with_detected} ({with_detected/total:.0%})")
        click.echo(f"With inferred seals:  {with_inferred} ({with_inferred/total:.0%})")
        click.echo(f"\nSeal distribution:")
        for seal, count in sorted(seal_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {seal:<30} {count:>4} ({count/total:.0%})")

        if not dry_run:
            click.echo(f"\nResults saved to database.")
        else:
            click.echo(f"\n(DRY RUN — nothing was saved)")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
@click.option("--limit", type=int, default=0, help="Max products to process (0 = all)")
@click.option("--dry-run", is_flag=True, help="Show what would be enriched without saving")
def enrich(brand: str, limit: int, dry_run: bool):
    """Re-process catalog_only products to find INCI via LLM fallback."""
    from src.core.llm import LLMClient
    from src.extraction.deterministic import extract_product_deterministic
    from src.extraction.inci_extractor import extract_and_validate_inci
    from src.core.taxonomy import normalize_category
    from src.storage.database import get_engine
    from src.storage.orm_models import Base
    from src.storage.repository import ProductRepository
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Try to set up browser
    browser = None
    try:
        from src.core.browser import BrowserClient
        browser = BrowserClient(headless=True)
        click.echo("Browser initialized")
    except Exception as e:
        click.echo(f"Warning: Browser not available ({e}). Will use LLM only.")

    # Set up LLM client
    try:
        llm = LLMClient()
        if not llm._client:
            click.echo("Error: ANTHROPIC_API_KEY not set. LLM fallback requires an API key.", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error initializing LLM: {e}", err=True)
        sys.exit(1)

    with SASession(engine) as session:
        repo = ProductRepository(session)
        products = repo.get_products_without_inci(brand)

        if not products:
            click.echo(f"No catalog_only products without INCI found for '{brand}'.")
            return

        if limit > 0:
            products = products[:limit]

        click.echo(f"Found {len(products)} catalog_only products without INCI for {brand}")
        if dry_run:
            click.echo("(DRY RUN — no changes will be saved)\n")

        enriched = 0
        desc_added = 0
        failed = 0

        for i, product in enumerate(products, 1):
            click.echo(f"  [{i}/{len(products)}] {product.product_name[:60]}...")

            if not llm.can_call:
                click.echo(f"  LLM budget exhausted after {i-1} products.")
                break

            html = None
            if browser:
                try:
                    html = browser.fetch_page(product.product_url)
                except Exception as e:
                    click.echo(f"    Fetch failed: {e}")

            if not html:
                failed += 1
                continue

            # Try deterministic first (may have improved selectors)
            det_result = extract_product_deterministic(html=html, url=product.product_url)
            inci_raw = det_result.get("inci_raw")
            inci_list = None

            if inci_raw:
                inci_result = extract_and_validate_inci(inci_raw)
                if inci_result.valid:
                    inci_list = inci_result.cleaned
                    click.echo(f"    Found INCI via deterministic ({len(inci_list)} ingredients)")

            # LLM fallback if deterministic failed
            if inci_list is None:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()
                    page_text = soup.get_text(separator="\n", strip=True)

                    prompt = (
                        "Extract the following fields from this hair product page.\n"
                        f"Product: {product.product_name}\n\n"
                        "Return JSON with these fields:\n"
                        "- inci_ingredients: list of individual INCI ingredient names (strings), or null if not found\n"
                        "- description: product description text, or null if not found\n\n"
                        "IMPORTANT: Only extract INCI ingredients if you find a complete ingredient list "
                        "(typically starting with 'Aqua' or 'Water'). Do NOT guess or infer ingredients."
                    )
                    llm_result = llm.extract_structured(page_text=page_text, prompt=prompt, max_tokens=2048)

                    if llm_result and llm_result.get("inci_ingredients"):
                        raw_llm = ", ".join(llm_result["inci_ingredients"])
                        inci_val = extract_and_validate_inci(raw_llm)
                        if inci_val.valid:
                            inci_list = inci_val.cleaned
                            click.echo(f"    Found INCI via LLM ({len(inci_list)} ingredients)")

                    if not product.description and llm_result and llm_result.get("description"):
                        if not dry_run:
                            product.description = llm_result["description"]
                        desc_added += 1
                except Exception as e:
                    click.echo(f"    LLM error: {e}")

            if inci_list:
                enriched += 1
                if dry_run:
                    click.echo(f"    Would update: {len(inci_list)} ingredients")
                else:
                    product.inci_ingredients = inci_list
                    product.verification_status = "verified_inci"
                    product.confidence = 0.85
                    product.extraction_method = "llm_grounded"
                    # Update category if missing
                    if not product.product_category:
                        product.product_category = normalize_category(
                            product.product_type_normalized, product.product_name
                        )
            else:
                failed += 1
                click.echo(f"    No INCI found")

        if not dry_run:
            session.commit()

    # Cleanup browser
    if browser:
        try:
            browser.close()
        except Exception:
            pass

    click.echo(f"\n{'='*60}")
    click.echo(f"Enrich Report — {brand}")
    click.echo(f"{'='*60}")
    click.echo(f"Total processed:    {len(products)}")
    click.echo(f"INCI found:         {enriched}")
    click.echo(f"Description added:  {desc_added}")
    click.echo(f"No INCI found:      {failed}")
    click.echo(f"LLM budget:         {llm.cost_summary}")

    if not dry_run and enriched > 0:
        click.echo(f"\n{enriched} products updated to verified_inci.")
    elif dry_run:
        click.echo(f"\n(DRY RUN — nothing was saved)")


@cli.command()
@click.option("--brand", required=True, help="Brand slug to validate")
@click.option("--limit", type=int, default=None, help="Limit products to validate")
@click.option("--dry-run", is_flag=True, help="Show what would be validated")
@click.option("--max-llm-calls", type=int, default=300, help="Max LLM calls for this brand")
def validate(brand: str, limit: int | None, dry_run: bool, max_llm_calls: int):
    """Run dual validation (Pass 1 vs Pass 2 LLM-grounded re-extraction).

    Pass 1 = stored extraction (deterministic via JSON-LD + CSS selectors).
    Pass 2 = LLM re-reads the same page and extracts fields independently.
    Divergences create entries in review_queue for human resolution.
    """
    import json as _json
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductORM
    from src.storage.repository import ProductRepository
    from src.core.dual_validator import compare_fields, compare_inci_lists
    from src.core.llm import LLMClient
    from src.extraction.llm_pass2 import extract_pass2_llm
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Initialize LLM client
    try:
        llm = LLMClient(max_calls_per_brand=max_llm_calls)
        if not llm._client:
            click.echo("Error: ANTHROPIC_API_KEY not set. Pass 2 requires LLM.", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error initializing LLM: {e}", err=True)
        sys.exit(1)

    # Initialize browser for re-fetch
    browser = None
    try:
        from src.core.browser import BrowserClient
        # Load brand blueprint for fetch options
        from src.discovery.blueprint_engine import load_blueprint
        try:
            bp = load_blueprint(brand) or {}
            extr = bp.get("extraction", {})
            browser = BrowserClient(
                delay_seconds=extr.get("delay_seconds", 2.0),
                use_curl_cffi=extr.get("http_client") == "curl_cffi",
                headless=True,
            )
        except Exception:
            browser = BrowserClient(delay_seconds=2.0, headless=True)
        click.echo(f"Browser initialized for re-fetch")
    except Exception as e:
        click.echo(f"Error: cannot initialize browser ({e})", err=True)
        sys.exit(1)

    with SASession(engine) as session:
        repo = ProductRepository(session)

        products = session.query(ProductORM).filter_by(brand_slug=brand).all()
        if limit:
            products = products[:limit]

        click.echo(f"Validating {len(products)} products for {brand}")

        if dry_run:
            for p in products[:5]:
                click.echo(f"  Would re-fetch + Pass 2: {p.product_name[:60]}")
            if len(products) > 5:
                click.echo(f"  ... and {len(products) - 5} more")
            return

        fields_to_compare = ["product_name", "price", "description", "composition", "care_usage"]
        total_comparisons = 0
        total_divergences = 0
        fetch_failures = 0
        llm_failures = 0

        for idx, p in enumerate(products):
            click.echo(f"  [{idx+1}/{len(products)}] {p.product_name[:55]}...")

            # Re-fetch HTML
            try:
                html = browser.fetch_page(p.product_url)
            except Exception as e:
                logger.warning(f"Fetch failed: {e}")
                fetch_failures += 1
                continue

            if not html or len(html) < 200:
                fetch_failures += 1
                continue

            # Pass 2 LLM
            pass2 = extract_pass2_llm(html, p.product_url, llm)
            if not pass2:
                llm_failures += 1
                continue

            # Compare each field
            for field in fields_to_compare:
                pass_1 = getattr(p, field, None)
                pass_2 = pass2.get(field)
                if pass_1 is None and pass_2 is None:
                    continue  # both null, skip
                str_1 = str(pass_1) if pass_1 is not None else None
                str_2 = str(pass_2) if pass_2 is not None else None
                result = compare_fields(field, str_1, str_2)
                vc = repo.save_validation_comparison(
                    product_id=p.id, field_name=field,
                    pass_1_value=str_1, pass_2_value=str_2,
                    resolution=result.resolution,
                )
                total_comparisons += 1
                if result.resolution != "auto_matched":
                    repo.create_review_queue_item(p.id, vc.id, field)
                    total_divergences += 1
                    click.echo(f"    DIVERGENCE in {field}")

            # Compare INCI lists
            if p.inci_ingredients and pass2.get("inci_ingredients"):
                pass_1_inci = p.inci_ingredients if isinstance(p.inci_ingredients, list) else []
                pass_2_inci = pass2["inci_ingredients"] if isinstance(pass2["inci_ingredients"], list) else []
                inci_result = compare_inci_lists(pass_1_inci, pass_2_inci)
                vc = repo.save_validation_comparison(
                    product_id=p.id, field_name="inci_ingredients",
                    pass_1_value=_json.dumps(pass_1_inci[:10]),
                    pass_2_value=_json.dumps(pass_2_inci[:10]),
                    resolution="auto_matched" if inci_result.matches else "pending",
                )
                total_comparisons += 1
                if not inci_result.matches:
                    repo.create_review_queue_item(p.id, vc.id, "inci_ingredients")
                    total_divergences += 1
                    click.echo(f"    DIVERGENCE in inci_ingredients ({len(inci_result.mismatches)} mismatches)")

            # Mark product as dual_validated if all fields matched
            if total_divergences == 0:
                # Could update product.verification_status here if desired
                pass

        session.commit()

    click.echo(f"\n{'='*60}")
    click.echo(f"Dual Validation Report — {brand}")
    click.echo(f"{'='*60}")
    click.echo(f"Products processed:  {len(products) - fetch_failures - llm_failures}/{len(products)}")
    click.echo(f"Fetch failures:      {fetch_failures}")
    click.echo(f"LLM failures:        {llm_failures}")
    click.echo(f"Total comparisons:   {total_comparisons}")
    click.echo(f"Auto-matched:        {total_comparisons - total_divergences}")
    click.echo(f"Divergences:         {total_divergences} ({total_divergences/max(total_comparisons,1):.0%})")
    click.echo(f"\nLLM cost: {llm.cost_summary}")


@cli.command(name="source-scrape")
@click.option("--source", required=True, help="Source slug (e.g., belezanaweb)")
@click.option("--brand", default=None, help="Filter by brand slug")
def source_scrape(source: str, brand: str | None):
    """Scrape external source for INCI data."""
    from src.enrichment.source_scraper import scrape_source
    from src.storage.database import get_engine
    from src.storage.orm_models import Base
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    click.echo(f"Scraping source: {source}" + (f" (brand: {brand})" if brand else ""))

    with SASession(engine) as session:
        stats = scrape_source(session, source, brand_filter=brand)

    click.echo(f"\nResults:")
    click.echo(f"  Discovered: {stats['discovered']}")
    click.echo(f"  Scraped:    {stats['scraped']}")
    click.echo(f"  With INCI:  {stats['with_inci']}")
    click.echo(f"  Skipped:    {stats['skipped']}")


@cli.command(name="enrich-external")
@click.option("--brand", default=None, help="Filter by brand slug")
@click.option("--dry-run", is_flag=True, help="Show matches without applying")
@click.option("--threshold", type=float, default=0.90, help="Auto-apply threshold")
def enrich_external(brand: str | None, dry_run: bool, threshold: float):
    """Match catalog_only products with external INCI sources."""
    from src.enrichment.matcher import match_products
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductORM, ExternalInciORM, EnrichmentQueueORM, ProductEvidenceORM
    from src.core.models import ExtractionMethod
    from sqlalchemy.orm import Session as SASession

    engine = get_engine()
    Base.metadata.create_all(engine)

    with SASession(engine) as session:
        query = session.query(ProductORM).filter(
            ProductORM.verification_status == "catalog_only"
        )
        if brand:
            query = query.filter(ProductORM.brand_slug == brand)
        products = query.all()

        click.echo(f"Found {len(products)} catalog_only products" +
                   (f" for {brand}" if brand else ""))

        auto_applied = 0
        queued = 0
        no_match = 0

        # Pre-load candidates by brand
        brand_slugs = {p.brand_slug for p in products}
        candidates_by_brand = {}
        for slug in brand_slugs:
            cands = (
                session.query(ExternalInciORM)
                .filter(
                    ExternalInciORM.brand_slug == slug,
                    ExternalInciORM.inci_ingredients.isnot(None),
                )
                .all()
            )
            candidates_by_brand[slug] = [
                {
                    "id": c.id,
                    "product_name": c.product_name,
                    "brand_slug": c.brand_slug,
                    "inci_ingredients": c.inci_ingredients,
                    "source": c.source,
                    "source_url": c.source_url,
                }
                for c in cands
            ]

        for product in products:
            cand_dicts = candidates_by_brand.get(product.brand_slug, [])

            if not cand_dicts:
                no_match += 1
                continue

            matches = match_products(
                product_name=product.product_name or "",
                product_brand=product.brand_slug,
                candidates=cand_dicts,
                auto_threshold=threshold,
            )

            if not matches:
                no_match += 1
                continue

            best = matches[0]

            if dry_run:
                click.echo(
                    f"  [{best['action']}] {product.product_name[:50]} "
                    f"<> {best['cand_name'][:50]} (score={best['score']:.2f})"
                )
                if best["action"] == "auto_apply":
                    auto_applied += 1
                else:
                    queued += 1
                continue

            if best["action"] == "auto_apply":
                product.inci_ingredients = best["inci_ingredients"]
                product.verification_status = "verified_inci"
                product.confidence = 0.85
                product.extraction_method = ExtractionMethod.EXTERNAL_ENRICHMENT.value
                # Create evidence row for audit trail
                evidence = ProductEvidenceORM(
                    product_id=product.id,
                    field_name="inci_ingredients",
                    source_url=best.get("source_url", ""),
                    evidence_locator=f"external_enrichment:{best['source']}",
                    raw_source_text=str(best["inci_ingredients"])[:500],
                    extraction_method=ExtractionMethod.EXTERNAL_ENRICHMENT.value,
                )
                session.add(evidence)
                auto_applied += 1
            else:
                queue_entry = EnrichmentQueueORM(
                    product_id=product.id,
                    external_inci_id=best["external_id"],
                    match_score=best["score"],
                    match_details={
                        "name_ratio": best["score"],
                        "type_match": best["type_match"],
                        "cand_name": best["cand_name"],
                    },
                )
                session.add(queue_entry)
                queued += 1

        if not dry_run:
            session.commit()

        click.echo(f"\nResults:")
        click.echo(f"  Auto-applied: {auto_applied}")
        click.echo(f"  Queued:       {queued}")
        click.echo(f"  No match:     {no_match}")


@cli.command()
@click.option("--brand", help="Brand slug (omit + use --all-brands for full backfill)")
@click.option("--all-brands", "all_brands", is_flag=True, help="Run for all brands")
@click.option("--limit", type=int, default=0, help="Max products to process (0 = all)")
@click.option("--dry-run", is_flag=True, help="Preview classification without saving")
@click.option("--min-confidence", type=float, default=0.0, help="Skip writing fields with confidence below this threshold")
@click.option("--with-validation", is_flag=True, help="Run Pass 2 LLM and create review queue for divergences")
@click.option("--max-llm-calls", type=int, default=200, help="Max LLM calls (only with --with-validation)")
def classify(brand: str | None, all_brands: bool, limit: int, dry_run: bool, min_confidence: float, with_validation: bool, max_llm_calls: int):
    """Apply heuristic classification (hair_type, audience_age, function_objective) to products."""
    from src.core.classifier import classify_product
    from src.storage.database import get_engine
    from src.storage.orm_models import Base, ProductEvidenceORM
    from src.storage.repository import ProductRepository
    from sqlalchemy.orm import Session as SASession

    # Pass 2 LLM (optional)
    llm_client = None
    classify_llm_fn = None
    if with_validation:
        from src.core.llm import LLMClient
        from src.core.classifier_llm import classify_with_llm as classify_llm_fn
        try:
            llm_client = LLMClient(max_calls_per_brand=max_llm_calls)
            if not llm_client._client:
                click.echo("Error: ANTHROPIC_API_KEY not set. --with-validation requires LLM.", err=True)
                sys.exit(1)
        except Exception as e:
            click.echo(f"Error initializing LLM: {e}", err=True)
            sys.exit(1)

    if not brand and not all_brands:
        click.echo("Error: provide --brand <slug> or --all-brands.", err=True)
        sys.exit(2)

    engine_db = get_engine()
    Base.metadata.create_all(engine_db)

    with SASession(engine_db) as session:
        repo = ProductRepository(session)
        if all_brands:
            products = repo.get_products(limit=limit if limit > 0 else 100000)
        else:
            products = repo.get_products(brand_slug=brand, limit=limit if limit > 0 else 100000)

        if not products:
            click.echo(f"No products found.")
            return

        click.echo(f"Classifying {len(products)} products...")
        if dry_run:
            click.echo("(DRY RUN — no changes will be saved)\n")

        total = len(products)
        with_function = 0
        with_hair_type = 0
        with_age_specific = 0  # not adult
        function_counts: dict[str, int] = {}
        age_counts: dict[str, int] = {}
        hair_type_counts: dict[str, int] = {}
        # Validation counters (only used with --with-validation)
        pass2_count = 0
        comparisons = 0
        divergences = 0
        import json

        for product in products:
            result = classify_product(
                product_name=product.product_name,
                description=product.description,
                product_category=product.product_category,
                inci_ingredients=product.inci_ingredients if isinstance(product.inci_ingredients, list) else None,
            )

            if result.function_objective and result.confidence_per_field.get("function_objective", 0) >= min_confidence:
                with_function += 1
                function_counts[result.function_objective] = function_counts.get(result.function_objective, 0) + 1

            if result.hair_type:
                with_hair_type += 1
                for ht in result.hair_type:
                    hair_type_counts[ht] = hair_type_counts.get(ht, 0) + 1

            age = result.audience_age or "adult"
            age_counts[age] = age_counts.get(age, 0) + 1
            if age != "adult":
                with_age_specific += 1

            # Pass 2 LLM (optional)
            if with_validation and llm_client and not dry_run and llm_client.can_call:
                pass2 = classify_llm_fn(
                    product_name=product.product_name,
                    description=product.description,
                    inci_ingredients=product.inci_ingredients if isinstance(product.inci_ingredients, list) else None,
                    product_category=product.product_category,
                    llm=llm_client,
                )
                if pass2:
                    pass2_count += 1
                    # Compare each field; create ValidationComparisonORM + ReviewQueueORM on diverge
                    for field_name, p1_val, p2_val in [
                        ("function_objective", result.function_objective, pass2.function_objective),
                        ("audience_age", result.audience_age, pass2.audience_age),
                        ("hair_type", sorted(result.hair_type) if result.hair_type else None,
                                       sorted(pass2.hair_type) if pass2.hair_type else None),
                    ]:
                        matches = (p1_val == p2_val) or (not p1_val and not p2_val)
                        resolution = "auto_matched" if matches else "pending"
                        s1 = json.dumps(p1_val) if p1_val is not None else None
                        s2 = json.dumps(p2_val) if p2_val is not None else None
                        vc = repo.save_validation_comparison(
                            product_id=product.id, field_name=field_name,
                            pass_1_value=s1, pass_2_value=s2, resolution=resolution,
                        )
                        comparisons += 1
                        if not matches:
                            repo.create_review_queue_item(product.id, vc.id, field_name)
                            divergences += 1

            if dry_run:
                if result.function_objective or result.hair_type or (age != "adult"):
                    click.echo(f"  {product.product_name[:60]}")
                    click.echo(
                        f"    function: {result.function_objective} (conf={result.confidence_per_field.get('function_objective', 0):.2f})"
                        f" | age: {age} (conf={result.confidence_per_field.get('audience_age', 0):.2f})"
                        f" | hair: {result.hair_type or '—'} (conf={result.confidence_per_field.get('hair_type', 0):.2f})"
                    )
            else:
                # Apply only fields meeting min_confidence
                if result.confidence_per_field.get("function_objective", 0) >= min_confidence:
                    product.function_objective = result.function_objective
                if result.confidence_per_field.get("audience_age", 0) >= min_confidence:
                    product.audience_age = result.audience_age
                if result.confidence_per_field.get("hair_type", 0) >= min_confidence and result.hair_type:
                    product.hair_type = result.hair_type

                # Evidence entries
                for field_name, value, conf in [
                    ("function_objective", result.function_objective, result.confidence_per_field.get("function_objective", 0)),
                    ("audience_age", result.audience_age, result.confidence_per_field.get("audience_age", 0)),
                    ("hair_type", result.hair_type, result.confidence_per_field.get("hair_type", 0)),
                ]:
                    if value and conf >= min_confidence:
                        # Remove prior classifier evidence for this field
                        session.query(ProductEvidenceORM).filter(
                            ProductEvidenceORM.product_id == product.id,
                            ProductEvidenceORM.field_name == field_name,
                            ProductEvidenceORM.extraction_method == "classifier_heuristic",
                        ).delete(synchronize_session=False)
                        kws = result.matched_keywords.get(field_name, [])
                        ev = ProductEvidenceORM(
                            product_id=product.id,
                            field_name=field_name,
                            source_url=product.product_url or "",
                            evidence_locator=f"classifier:heuristic conf={conf:.2f}",
                            raw_source_text=f"matched: {', '.join(kws) if kws else 'default'}",
                            extraction_method="classifier_heuristic",
                        )
                        session.add(ev)

        if not dry_run:
            session.commit()

        click.echo(f"\n{'='*60}")
        click.echo(f"Classification Report")
        click.echo(f"{'='*60}")
        click.echo(f"Total products:        {total}")
        click.echo(f"With function:         {with_function} ({with_function/total:.0%})")
        click.echo(f"With hair_type:        {with_hair_type} ({with_hair_type/total:.0%})")
        click.echo(f"With specific age:     {with_age_specific} ({with_age_specific/total:.0%})")

        click.echo(f"\nFunction distribution:")
        for func, count in sorted(function_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {func:<20} {count:>5} ({count/total:.0%})")

        click.echo(f"\nAudience age distribution:")
        for age, count in sorted(age_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {age:<20} {count:>5} ({count/total:.0%})")

        click.echo(f"\nHair type distribution (multi-valor):")
        for ht, count in sorted(hair_type_counts.items(), key=lambda x: -x[1])[:15]:
            click.echo(f"  {ht:<20} {count:>5} ({count/total:.0%})")

        if with_validation and llm_client:
            click.echo(f"\n--- Dual Validation (Pass 1 heuristic vs Pass 2 LLM) ---")
            click.echo(f"Products with Pass 2:  {pass2_count}")
            click.echo(f"Total comparisons:     {comparisons}")
            click.echo(f"Auto-matched:          {comparisons - divergences}")
            click.echo(f"Divergences (review):  {divergences} ({divergences/max(comparisons,1):.0%})")
            click.echo(f"LLM cost:              {llm_client.cost_summary}")

        if not dry_run:
            click.echo(f"\nResults saved to database.")
        else:
            click.echo(f"\n(DRY RUN — nothing was saved)")


if __name__ == "__main__":
    cli()
