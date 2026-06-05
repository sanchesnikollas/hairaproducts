"""Triagem das marcas pendentes para o roadmap 0→100%.

Para cada marca em `config/brands.json` que não tem ≥10 produtos no DB e cujo
`status` não é terminal (out_of_scope/blocked/no_source), avalia:

  - GET `official_url_root` → status, redirect, presença de plataforma conhecida
    (VTEX, Shopify, WooCommerce, Wix, ou JSON-LD com Product)
  - Busca o `brand_name` em distribuidores (Beleza na Web; Época opcional)

Tier resultante:
  - tier_1_easy        — site 2xx + plataforma conhecida
  - tier_2_medium      — site 2xx + plataforma custom (precisa blueprint manual)
  - tier_3_distributor — site falha ou platform=unknown, mas ≥3 hits em distribuidor
  - tier_4_inviable    — site falha e sem hits em distribuidor

Saída: JSON em stdout. Concorrência via ThreadPoolExecutor (default 10 workers).

Uso:
    python scripts/triagem_pendentes.py > data/triagem-2026-05-12.json
    python scripts/triagem_pendentes.py --workers 20 --limit 30   # subset rápido
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    from curl_cffi import requests as cc_requests  # type: ignore
except ImportError:
    cc_requests = None
import httpx


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

PLATFORM_SIGNATURES = [
    ("vtex", re.compile(r"vtex\.com|portal\.vtex|vtex\.js|/api/catalog_system/", re.I)),
    ("shopify", re.compile(r"cdn\.shopify\.com|Shopify\.theme|/products\.json", re.I)),
    ("woocommerce", re.compile(r"woocommerce|wp-content/plugins/woocommerce", re.I)),
    ("wix", re.compile(r"wixstatic\.com|static\.wixstatic", re.I)),
    ("nuvemshop", re.compile(r"tiendanube|nuvemshop\.com\.br", re.I)),
    ("magento", re.compile(r"Mage\.Cookies|/static/version\d+/", re.I)),
    ("json_ld_product", re.compile(r'"@type"\s*:\s*"Product"', re.I)),
]

BUSCA_BELEZANAWEB = "https://www.belezanaweb.com.br/busca/?q={query}"
PRODUCT_CARD_PATTERN = re.compile(r'data-pid|data-id-product|product-card|product-tile', re.I)


def fetch(url: str, timeout: float = 10.0) -> tuple[int, str, str]:
    """Return (status_code, final_url, body). Uses curl_cffi if available, falls back to httpx."""
    try:
        if cc_requests is not None:
            r = cc_requests.get(url, headers=HEADERS, timeout=timeout, impersonate="chrome", allow_redirects=True)
            return r.status_code, str(r.url), r.text[:200_000]
        with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as c:
            r = c.get(url)
            return r.status_code, str(r.url), r.text[:200_000]
    except Exception as e:  # noqa: BLE001
        return 0, url, f"__ERROR__: {type(e).__name__}: {e}"


def detect_platform(body: str) -> str:
    for name, pattern in PLATFORM_SIGNATURES:
        if pattern.search(body):
            return name
    return "unknown"


def belezanaweb_hits(brand_name: str) -> int:
    url = BUSCA_BELEZANAWEB.format(query=quote_plus(brand_name))
    status, _final, body = fetch(url, timeout=15.0)
    if status != 200 or body.startswith("__ERROR__"):
        return -1
    return len(PRODUCT_CARD_PATTERN.findall(body))


def triagem_brand(brand: dict[str, Any]) -> dict[str, Any]:
    slug = brand["brand_slug"]
    name = brand["brand_name"]
    url = brand.get("official_url_root") or ""

    out: dict[str, Any] = {
        "brand_slug": slug,
        "brand_name": name,
        "official_url_root": url,
        "site": {"status_code": None, "final_url": None, "platform": None},
        "distributors": {"belezanaweb_hits": None},
        "tier": None,
        "recommended_action": None,
    }

    site_ok = False
    platform = "unknown"
    if url:
        status, final_url, body = fetch(url, timeout=12.0)
        out["site"]["status_code"] = status
        out["site"]["final_url"] = final_url
        if 200 <= status < 400 and not body.startswith("__ERROR__"):
            platform = detect_platform(body)
            site_ok = True
        out["site"]["platform"] = platform

    if not site_ok:
        out["distributors"]["belezanaweb_hits"] = belezanaweb_hits(name)

    if site_ok and platform != "unknown":
        out["tier"] = "tier_1_easy"
        out["recommended_action"] = (
            f"brand-onboarding agent: blueprint usando platform_adapter '{platform}'"
        )
    elif site_ok and platform == "unknown":
        out["tier"] = "tier_2_medium"
        out["recommended_action"] = (
            "brand-onboarding agent: blueprint manual (HTML estático + seletores)"
        )
    elif (out["distributors"]["belezanaweb_hits"] or 0) >= 3:
        out["tier"] = "tier_3_distributor"
        out["recommended_action"] = (
            "inci-enricher agent: source-scrape via belezanaweb"
        )
    else:
        out["tier"] = "tier_4_inviable"
        out["recommended_action"] = (
            "Marcar status='no_source' em brands.json; documentar em notes"
        )

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=10, help="threads concorrentes")
    parser.add_argument("--limit", type=int, default=0, help="0 = todas; >0 = subset")
    parser.add_argument("--db", default="haira.db", help="caminho do haira.db")
    parser.add_argument(
        "--brands-json", default="config/brands.json", help="caminho do brands.json"
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    brands_path = repo_root / args.brands_json
    db_path = repo_root / args.db

    brands: list[dict[str, Any]] = json.load(open(brands_path, encoding="utf-8"))

    c = sqlite3.connect(str(db_path))
    with_10 = {
        r[0]
        for r in c.execute(
            "SELECT brand_slug FROM products GROUP BY brand_slug HAVING COUNT(*) >= 10"
        )
    }
    c.close()

    terminal_statuses = {"out_of_scope", "blocked", "no_source"}
    candidates = [
        b
        for b in brands
        if b["brand_slug"] not in with_10
        and b.get("status") not in terminal_statuses
    ]
    if args.limit > 0:
        candidates = candidates[: args.limit]

    sys.stderr.write(
        f"Triagem de {len(candidates)} marcas pendentes (de {len(brands)} totais). "
        f"Workers: {args.workers}\n"
    )

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(triagem_brand, b): b for b in candidates}
        done = 0
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001
                b = futures[fut]
                results.append(
                    {
                        "brand_slug": b["brand_slug"],
                        "brand_name": b["brand_name"],
                        "tier": "tier_4_inviable",
                        "recommended_action": f"erro: {type(e).__name__}: {e}",
                    }
                )
            done += 1
            if done % 25 == 0:
                sys.stderr.write(f"  ... {done}/{len(candidates)}\n")

    results.sort(key=lambda r: (r.get("tier") or "zzz", r["brand_slug"]))

    from collections import Counter

    summary = Counter(r["tier"] for r in results)
    sys.stderr.write(f"\nDistribuição por tier:\n")
    for tier in ("tier_1_easy", "tier_2_medium", "tier_3_distributor", "tier_4_inviable"):
        sys.stderr.write(f"  {tier}: {summary.get(tier, 0)}\n")

    payload = {
        "snapshot_date": "2026-05-12",
        "total_brands_in_registry": len(brands),
        "total_with_ge10_products": len(with_10),
        "total_candidates": len(candidates),
        "summary": dict(summary),
        "results": results,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
