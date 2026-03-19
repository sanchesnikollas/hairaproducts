"""
Generic brand extraction pipeline.
Reads discovered URLs, extracts products, runs QA, saves to DB.
Usage: python scripts/extract_brand.py --brand <slug> [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.browser import BrowserClient
from src.discovery.blueprint_engine import load_blueprint
from src.pipeline.coverage_engine import CoverageEngine
from src.storage.database import get_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def load_urls(path: Path, limit: int | None = None) -> list[str]:
    urls = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    if limit:
        urls = urls[:limit]
    return urls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of URLs")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
    args = parser.parse_args()

    brand_slug = args.brand
    urls_file = Path(f"data/{brand_slug}_all_urls.txt")

    if not urls_file.exists():
        logger.error(f"URLs file not found: {urls_file}")
        return

    urls = load_urls(urls_file, args.limit)
    logger.info(f"Loaded {len(urls)} URLs for {brand_slug}")

    if args.dry_run:
        for u in urls[:10]:
            print(u)
        if len(urls) > 10:
            print(f"... and {len(urls) - 10} more")
        return

    blueprint = load_blueprint(brand_slug)
    if not blueprint:
        logger.error(f"No blueprint found for {brand_slug}")
        return

    headless = blueprint.get("extraction", {}).get("headless", True)
    delay = blueprint.get("extraction", {}).get("delay_seconds", 3)
    requires_js = blueprint.get("extraction", {}).get("requires_js", True)
    use_httpx = not requires_js
    browser = BrowserClient(headless=headless, delay_seconds=delay, use_httpx=use_httpx)

    try:
        session = get_session()
        engine = CoverageEngine(session=session, browser=browser)

        discovered = [{"url": u} for u in urls]

        report = engine.process_brand(
            brand_slug=brand_slug,
            blueprint=blueprint,
            discovered_urls=discovered,
        )

        print(f"\n{'='*60}")
        print(f"{brand_slug} Extraction Report")
        print(f"{'='*60}")
        print(f"Discovered: {report.discovered_total}")
        print(f"Hair relevant: {report.hair_total}")
        print(f"Extracted: {report.extracted_total}")
        print(f"Verified INCI: {report.verified_inci_total} ({report.verified_inci_rate:.1%})")
        print(f"Catalog only: {report.catalog_only_total}")
        print(f"Quarantined: {report.quarantined_total}")
        if report.errors:
            print(f"Errors: {len(report.errors)}")
            for e in report.errors[:5]:
                print(f"  - {e}")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
