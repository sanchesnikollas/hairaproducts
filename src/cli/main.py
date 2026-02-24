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
    click.echo(f"Blueprint for {brand} (regenerate={regenerate}) — not yet implemented")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
def recon(brand: str):
    """Run discovery + small sample extraction for a brand."""
    click.echo(f"Recon for {brand} — not yet implemented")


@cli.command()
@click.option("--brand", help="Brand slug (single brand)")
@click.option("--priority", type=int, help="Run brands with this priority level")
@click.option("--max-brands", type=int, default=10, help="Max brands to process")
def scrape(brand: str | None, priority: int | None, max_brands: int):
    """Run full scrape pipeline for brand(s)."""
    click.echo(f"Scrape — not yet implemented")


@cli.command()
@click.option("--brand", required=True, help="Brand slug")
def audit(brand: str):
    """Run QA audit on existing data for a brand."""
    click.echo(f"Audit for {brand} — not yet implemented")


@cli.command()
@click.option("--brand", help="Brand slug")
@click.option("--all-brands", "all_brands", is_flag=True, help="Report for all brands")
def report(brand: str | None, all_brands: bool):
    """Generate coverage report."""
    click.echo(f"Report — not yet implemented")


if __name__ == "__main__":
    cli()
