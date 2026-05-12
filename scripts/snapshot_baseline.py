"""Snapshot baseline metrics for the 0→100% roadmap.

Writes a JSON snapshot of the current state to stdout. Captures:
- total products, distinct brands with products
- verification_status distribution
- field coverage % (price, care_usage, inci_ingredients, description) overall
- per-brand coverage breakdown
- top-10 brands with most quarantined items
- sum of discovered_total across brands

Usage:
    python scripts/snapshot_baseline.py > data/baselines/2026-05-12-baseline.json
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).parent.parent / "haira.db"
    if not db_path.exists():
        sys.stderr.write(f"haira.db not found at {db_path}\n")
        sys.exit(1)

    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row

    snapshot: dict = {
        "snapshot_date": datetime.now().isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "totals": {},
        "verification_status": {},
        "coverage_pct": {},
        "per_brand_coverage": [],
        "top_quarantined_brands": [],
        "discovered_total_sum": 0,
    }

    snapshot["totals"]["products"] = c.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]
    snapshot["totals"]["distinct_brands_with_products"] = c.execute(
        "SELECT COUNT(DISTINCT brand_slug) FROM products"
    ).fetchone()[0]

    for row in c.execute(
        "SELECT verification_status, COUNT(*) AS n FROM products GROUP BY verification_status ORDER BY n DESC"
    ):
        snapshot["verification_status"][row["verification_status"] or "null"] = row["n"]

    cov = c.execute(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) AS with_price,
          SUM(CASE WHEN care_usage IS NOT NULL AND length(care_usage) > 0 THEN 1 ELSE 0 END) AS with_care_usage,
          SUM(CASE WHEN inci_ingredients IS NOT NULL AND length(inci_ingredients) > 5 THEN 1 ELSE 0 END) AS with_inci,
          SUM(CASE WHEN description IS NOT NULL AND length(description) > 0 THEN 1 ELSE 0 END) AS with_description,
          SUM(CASE WHEN product_labels IS NOT NULL AND length(product_labels) > 5 THEN 1 ELSE 0 END) AS with_labels
        FROM products
        """
    ).fetchone()
    total = cov["total"] or 1
    snapshot["coverage_pct"] = {
        "price": round(100 * cov["with_price"] / total, 2),
        "care_usage": round(100 * cov["with_care_usage"] / total, 2),
        "inci_ingredients": round(100 * cov["with_inci"] / total, 2),
        "description": round(100 * cov["with_description"] / total, 2),
        "product_labels": round(100 * cov["with_labels"] / total, 2),
    }

    for row in c.execute(
        """
        SELECT
          brand_slug,
          COUNT(*) AS total,
          SUM(CASE WHEN inci_ingredients IS NOT NULL AND length(inci_ingredients) > 5 THEN 1 ELSE 0 END) AS with_inci,
          SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) AS with_price,
          SUM(CASE WHEN care_usage IS NOT NULL AND length(care_usage) > 0 THEN 1 ELSE 0 END) AS with_care
        FROM products
        GROUP BY brand_slug
        ORDER BY total DESC
        """
    ):
        n = row["total"] or 1
        snapshot["per_brand_coverage"].append(
            {
                "brand_slug": row["brand_slug"],
                "total": row["total"],
                "inci_pct": round(100 * row["with_inci"] / n, 1),
                "price_pct": round(100 * row["with_price"] / n, 1),
                "care_usage_pct": round(100 * row["with_care"] / n, 1),
            }
        )

    for row in c.execute(
        """
        SELECT brand_slug, COUNT(*) AS n
        FROM products
        WHERE verification_status = 'quarantined'
        GROUP BY brand_slug
        ORDER BY n DESC
        LIMIT 10
        """
    ):
        snapshot["top_quarantined_brands"].append(
            {"brand_slug": row["brand_slug"], "quarantined": row["n"]}
        )

    try:
        for row in c.execute(
            "SELECT SUM(discovered_total) AS s FROM brand_coverage"
        ):
            snapshot["discovered_total_sum"] = row["s"] or 0
    except sqlite3.OperationalError:
        snapshot["discovered_total_sum"] = None

    c.close()
    json.dump(snapshot, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
