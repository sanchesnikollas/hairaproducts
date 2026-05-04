"""Batch-onboard pending brands using template blueprints by platform.

Reads config/brands_triage.json (output of triage_pending_brands.py) and
processes brands marked as tier_1_easy or tier_2_check.

For each candidate:
  1. Generate blueprint from platform template (Shopify/WooCommerce/Nuvemshop/VTEX/Tray)
  2. Run scrape (haira scrape --brand <slug>)
  3. Run cleanup_non_product_urls.py
  4. Run labels + classify
  5. Report coverage

Usage:
  python scripts/batch_onboard_brands.py --tier tier_1_easy --limit 5 --dry-run
  python scripts/batch_onboard_brands.py --tier tier_1_easy --limit 5
  python scripts/batch_onboard_brands.py --tier tier_1_easy --limit 5 --skip-existing
  python scripts/batch_onboard_brands.py --slug bemgloria

The --dry-run mode only generates blueprints (no scrape).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sqlite3
import sys
from pathlib import Path

import yaml

DB = "haira.db"
TRIAGE_FILE = "config/brands_triage.json"
BLUEPRINTS_DIR = Path("config/blueprints")
LOGS_DIR = Path("logs")

PLATFORM_TEMPLATES = {
    "shopify": {
        "platform": "shopify",
        "discovery_strategy": "sitemap_first",
        "sitemap_paths": ["/sitemap.xml", "/sitemap_products_1.xml"],
        "product_url_pattern": r"^{root}/products/[\w-]+$",
        "name_selectors": ["h1.product-title", "h1.product__title", "h1.product-meta__title", "h1"],
        "image_selectors": ["img[src*='cdn.shopify.com']", ".product-image img", ".product__media img"],
        "price_selectors": [".product-price", "[class*='price']", "sale-price", ".price-item"],
        "inci_selectors": ["details.accordion .accordion__content .prose", ".product-description"],
        "section_label_map": {
            "description": ["descrição", "detalhes", "sobre o produto", "o produto"],
            "care_usage": ["como usar", "modo de uso", "modo de usar", "aplicação"],
            "composition": ["composição", "fórmula", "principais ingredientes"],
            "ingredients_inci": ["ingredientes", "ingredients", "inci", "composição completa"],
            "benefits": ["benefícios", "resultado", "resultados esperados"],
        },
        "requires_js": False,
    },
    "woocommerce": {
        "platform": "woocommerce",
        "discovery_strategy": "sitemap_first",
        "sitemap_paths": ["/product-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"],
        "product_url_pattern": r"^{root}/(?:produto|product)/[\w-]+/?$",
        "name_selectors": ["h1.product_title", "h1.entry-title", "h1"],
        "image_selectors": [".woocommerce-product-gallery__image img", "img.wp-post-image"],
        "price_selectors": ["p.price", "span.price", ".woocommerce-Price-amount"],
        "inci_selectors": [".woocommerce-product-details__short-description", ".woocommerce-tabs .panel"],
        "section_label_map": {
            "description": ["descrição", "detalhes", "sobre"],
            "care_usage": ["como usar", "modo de uso", "modo de usar", "aplicação", "como aplicar"],
            "composition": ["composição", "fórmula", "ingredientes ativos"],
            "ingredients_inci": ["ingredientes", "ingredients", "inci"],
            "benefits": ["benefícios", "resultado"],
        },
        "requires_js": False,
    },
    "nuvemshop": {
        "platform": "nuvemshop",
        "discovery_strategy": "sitemap_first",
        "sitemap_paths": ["/sitemap.xml", "/sitemap-products.xml"],
        "product_url_pattern": r"^{root}/produto[s]?/[\w-]+",
        "name_selectors": ["h1.product-name", "h1.js-product-name", "h1"],
        "image_selectors": [".js-product-slides img", ".product-image img"],
        "price_selectors": [".js-price-display", ".price", ".js-product-price"],
        "inci_selectors": [".js-product-description", ".user-content", ".product-description"],
        "section_label_map": {
            "description": ["descrição", "detalhes", "sobre"],
            "care_usage": ["como usar", "modo de uso", "aplicação"],
            "composition": ["composição", "fórmula", "ativos"],
            "ingredients_inci": ["ingredientes", "ingredients", "inci"],
            "benefits": ["benefícios", "resultado"],
        },
        "requires_js": False,
    },
    "vtex": {
        "platform": "vtex",
        "discovery_strategy": "sitemap_first",
        "sitemap_paths": ["/sitemap.xml", "/sitemap-1.xml", "/sitemap-product-1.xml"],
        "product_url_pattern": r"^{root}/[\w-]+/p$",
        "name_selectors": ["h1.vtex-store-components-3-x-productNameContainer", "h1.product-name", "h1"],
        "image_selectors": ["img.vtex-store-components-3-x-productImageTag", ".product-image img"],
        "price_selectors": ["span.vtex-product-price", ".vtex-product-price-1-x-sellingPrice", ".price"],
        "inci_selectors": [".vtex-store-components-3-x-productDescriptionText", ".product-description"],
        "section_label_map": {
            "description": ["descrição", "sobre", "detalhes"],
            "care_usage": ["como usar", "modo de uso", "aplicação"],
            "composition": ["composição", "fórmula"],
            "ingredients_inci": ["ingredientes", "ingredients", "inci"],
            "benefits": ["benefícios", "resultado"],
        },
        "requires_js": False,
    },
    "tray": {
        "platform": "tray",
        "discovery_strategy": "sitemap_first",
        "sitemap_paths": ["/sitemap.xml", "/sitemapProdutos.xml"],
        "product_url_pattern": r"^{root}/produto/[\w-]+",
        "name_selectors": ["h1.product_name", "h1.titulo", "h1"],
        "image_selectors": [".product-image img", ".carousel-image img"],
        "price_selectors": [".product_price", ".price"],
        "inci_selectors": [".description", ".product-description"],
        "section_label_map": {
            "description": ["descrição", "detalhes"],
            "care_usage": ["como usar", "modo de uso"],
            "composition": ["composição", "fórmula"],
            "ingredients_inci": ["ingredientes", "ingredients"],
            "benefits": ["benefícios"],
        },
        "requires_js": False,
    },
}


def url_root(url: str) -> str:
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else url


def make_blueprint(brand: dict) -> dict:
    slug = brand["brand_slug"]
    name = brand["brand_name"]
    url = brand["official_url_root"]
    platform = brand.get("platform_guess")

    if platform not in PLATFORM_TEMPLATES:
        raise ValueError(f"No template for platform: {platform}")

    tpl = PLATFORM_TEMPLATES[platform]
    root = url_root(url)
    domain = root.replace("https://", "").replace("http://", "").rstrip("/")

    pattern = tpl["product_url_pattern"].replace("{root}", re.escape(root))

    bp = {
        "brand_slug": slug,
        "brand_name": name,
        "platform": tpl["platform"],
        "domain": domain,
        "allowed_domains": [domain],
        "entrypoints": [url],
        "discovery": {
            "strategy": tpl["discovery_strategy"],
            "sitemap_urls": [f"{root}{p}" for p in tpl["sitemap_paths"]],
            "product_url_pattern": pattern,
            "max_pages": 500,
            "pagination": {"type": "none", "max_pages": 1},
        },
        "extraction": {
            "requires_js": tpl["requires_js"],
            "headless": True,
            "delay_seconds": 2,
            "name_selectors": tpl["name_selectors"],
            "image_selectors": tpl["image_selectors"],
            "price_selectors": tpl["price_selectors"],
            "inci_selectors": tpl["inci_selectors"],
            "section_label_map": {
                k: {"labels": v} for k, v in tpl["section_label_map"].items()
            },
            "use_llm_fallback": False,
        },
        "notes": {
            "auto_generated": True,
            "platform_detail": platform,
            "inci_available": "unknown",
            "inci_note": "Auto-generated blueprint; review after first scrape.",
            "triage_tier": brand.get("tier"),
        },
        "version": 1,
    }
    return bp


def write_blueprint(bp: dict) -> Path:
    slug = bp["brand_slug"]
    path = BLUEPRINTS_DIR / f"{slug}.yaml"
    BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(bp, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def run_cmd(cmd: list[str], log_file: Path) -> int:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    return proc.returncode


def coverage_for_brand(slug: str) -> dict:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        """SELECT COUNT(*),
            SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != '[]' AND inci_ingredients != 'null' THEN 1 ELSE 0 END),
            SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN care_usage IS NOT NULL AND care_usage != '' THEN 1 ELSE 0 END)
            FROM products WHERE brand_slug=?""",
        (slug,),
    )
    t, i, p, care = c.fetchone()
    conn.close()
    return {"total": t or 0, "inci": i or 0, "price": p or 0, "care_usage": care or 0}


def already_in_db(slug: str) -> bool:
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products WHERE brand_slug=? LIMIT 1", (slug,))
    n = c.fetchone()[0]
    conn.close()
    return n > 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="tier_1_easy", help="Triage tier to process")
    ap.add_argument("--limit", type=int, default=5, help="Max brands per run")
    ap.add_argument("--slug", help="Process a single brand by slug")
    ap.add_argument("--dry-run", action="store_true", help="Generate blueprints only")
    ap.add_argument("--skip-existing", action="store_true", help="Skip brands already in DB")
    ap.add_argument("--scrape", action="store_true", default=True, help="Run scrape (default)")
    ap.add_argument("--no-scrape", dest="scrape", action="store_false")
    args = ap.parse_args()

    with open(TRIAGE_FILE) as f:
        triage = json.load(f)

    if args.slug:
        candidates = [b for b in triage if b["brand_slug"] == args.slug]
        if not candidates:
            print(f"Slug {args.slug} not in triage")
            sys.exit(1)
    else:
        candidates = [b for b in triage if b["tier"] == args.tier]
        if args.skip_existing:
            candidates = [b for b in candidates if not already_in_db(b["brand_slug"])]
        candidates = candidates[: args.limit]

    print(f"Processing {len(candidates)} brands")

    results = []
    for brand in candidates:
        slug = brand["brand_slug"]
        platform = brand.get("platform_guess")
        print(f"\n=== {slug} ({platform}) ===")

        # Skip if blueprint already exists (don't overwrite manual work)
        bp_path = BLUEPRINTS_DIR / f"{slug}.yaml"
        if bp_path.exists():
            print(f"  Blueprint already exists at {bp_path}, skipping creation")
        else:
            try:
                bp = make_blueprint(brand)
                bp_path = write_blueprint(bp)
                print(f"  Wrote blueprint: {bp_path}")
            except Exception as e:
                print(f"  Error generating blueprint: {e}")
                results.append({"slug": slug, "status": "blueprint_failed", "error": str(e)})
                continue

        if args.dry_run:
            results.append({"slug": slug, "status": "blueprint_only"})
            continue

        if not args.scrape:
            results.append({"slug": slug, "status": "blueprint_only"})
            continue

        # Run scrape
        log_file = LOGS_DIR / f"{slug}_onboard_$(date +%H%M%S).log"
        log_file = LOGS_DIR / f"{slug}_onboard.log"
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        # Read .env
        if Path(".env").exists():
            for line in Path(".env").read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env.setdefault(k, v)

        cmd = [sys.executable, "-m", "src.cli.main", "scrape", "--brand", slug]
        print(f"  Running: {' '.join(cmd)} > {log_file}")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("w") as f:
            rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
        print(f"  Scrape rc={rc}")

        if rc != 0:
            results.append({"slug": slug, "status": "scrape_failed", "rc": rc})
            continue

        # Cleanup non-product URLs
        cmd = [sys.executable, "scripts/cleanup_non_product_urls.py", slug]
        subprocess.call(cmd, env=env)

        # Coverage
        cov = coverage_for_brand(slug)
        if cov["total"] == 0:
            print(f"  No products extracted")
            results.append({"slug": slug, "status": "no_products", "coverage": cov})
            continue

        # Labels + classify
        for sub in ("labels", "classify"):
            cmd = [sys.executable, "-m", "src.cli.main", sub, "--brand", slug]
            subprocess.call(cmd, env=env)

        results.append({"slug": slug, "status": "ok", "coverage": cov})

    # Summary
    print("\n=== SUMMARY ===")
    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"OK: {ok_count}/{len(results)}")
    for r in results:
        if r["status"] == "ok":
            cov = r["coverage"]
            t = cov["total"]
            print(
                f"  {r['slug']:30s} total={t:4d} INCI={100*cov['inci']/t:.0f}% "
                f"price={100*cov['price']/t:.0f}% care={100*cov['care_usage']/t:.0f}%"
            )
        else:
            print(f"  {r['slug']:30s} {r['status']}")

    # Save results
    out = LOGS_DIR / f"batch_onboard_{args.tier}_{len(results)}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    main()
