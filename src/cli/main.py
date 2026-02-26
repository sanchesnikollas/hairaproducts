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

        # Discover URLs
        discoverer = ProductDiscoverer(browser=browser)
        discovered = discoverer.discover(bp)
        click.echo(f"  Discovered: {len(discovered)} URLs")

        if not discovered:
            click.echo(f"  No URLs found, skipping.")
            continue

        # Convert DiscoveredURL to dicts for coverage engine
        url_dicts = [{"url": d.url} for d in discovered]

        # Run coverage engine
        with SASession(engine) as session:
            cov_engine = CoverageEngine(session=session, browser=browser)
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


if __name__ == "__main__":
    cli()
