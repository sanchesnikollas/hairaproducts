"""Triage pending brands from brands.json — classify each by viability for direct scrape.

For each brand without products in DB:
  1. Probe official_url_root with httpx (GET, follow redirects, 15s timeout)
  2. Detect platform from response headers/HTML markers
  3. Check sitemap.xml availability (best-effort)
  4. Assign tier:
     - tier_1_easy: known platform (Shopify/VTEX/Wake/Nuvemshop/WooCommerce) + sitemap responsive
     - tier_2_check: known platform + sitemap missing OR INCI flag=não
     - tier_3_custom: site responds but no recognized platform
     - tier_4_no_site: domain dead, 404, 5xx, or no useful response
     - tier_5_waf: 403 or anti-bot blocking (still potentially scrapable via curl_cffi/playwright)
     - tier_skip: status=blocked/blocked_maintenance/no_source

Output: writes config/brands_triage.json with full triage data.
"""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)

DB = "haira.db"
BRANDS_JSON = "config/brands.json"
OUTPUT = "config/brands_triage.json"
CONCURRENCY = 15
TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

PLATFORM_MARKERS = {
    "shopify": [
        r"cdn\.shopify\.com",
        r"Shopify\.theme",
        r"shopify-section",
        r"window\.Shopify",
    ],
    "vtex": [
        r"vtexassets\.com",
        r"vtex-store",
        r'data-id="vtex-store"',
        r"vtex-render-runtime",
    ],
    "wake": [
        r"fbits-componente",
        r"fbits-produto",
        r"wakecommerce",
    ],
    "nuvemshop": [
        r"nuvemshop\.com",
        r"tiendanube\.com",
        r"data-store-id",
    ],
    "woocommerce": [
        r"woocommerce-",
        r"wp-content/plugins/woocommerce",
        r"wc-block-",
    ],
    "demandware": [
        r"demandware\.static",
        r"demandware\.com",
        r"dw\.demandware",
    ],
    "magento": [
        r"Mage\.Cookies",
        r"Magento_",
        r"mage/cookies",
    ],
    "salesforce_b2c": [
        r"sfcc-",
        r"sfra/",
    ],
    "tray": [
        r"tray\.com",
        r"trayapps",
    ],
    "loja_integrada": [
        r"lojaintegrada\.com",
    ],
}


def detect_platform(html: str, headers: dict) -> str | None:
    text_to_check = html[:30000]
    for plat, patterns in PLATFORM_MARKERS.items():
        for p in patterns:
            if re.search(p, text_to_check, re.IGNORECASE):
                return plat
    server = (headers.get("server") or "").lower()
    if "shopify" in server:
        return "shopify"
    if "cloudflare" in server:
        return None
    return None


def detect_anti_bot(status_code: int, html: str) -> bool:
    if status_code == 403:
        return True
    if status_code == 429:
        return True
    text = html[:5000].lower()
    markers = [
        "just a moment",
        "cf-challenge",
        "cf-turnstile",
        "challenges.cloudflare.com",
        "_cf_chl_opt",
        "akamai",
        "bot detection",
    ]
    return any(m in text for m in markers)


async def probe_brand(client: httpx.AsyncClient, brand: dict) -> dict:
    slug = brand["brand_slug"]
    url = brand.get("official_url_root") or ""
    notes = (brand.get("notes") or "").lower()
    inci_flag = "yes" if "inci_on_site=sim" in notes else "no" if "inci_on_site=não" in notes else "unknown"

    result = {
        "brand_slug": slug,
        "brand_name": brand.get("brand_name"),
        "official_url_root": url,
        "priority": brand.get("priority"),
        "inci_flag": inci_flag,
        "tier": None,
        "platform_guess": None,
        "http_status": None,
        "html_length": None,
        "has_sitemap": False,
        "anti_bot": False,
        "error": None,
    }

    # Skip if blocked
    if brand.get("status") in ("blocked", "blocked_maintenance", "no_source"):
        result["tier"] = "tier_skip"
        result["error"] = f"status={brand.get('status')}"
        return result

    if not url or not url.startswith("http"):
        result["tier"] = "tier_4_no_site"
        result["error"] = "no_official_url"
        return result

    try:
        r = await client.get(url, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        result["http_status"] = r.status_code
        result["html_length"] = len(r.text)

        if r.status_code >= 500:
            result["tier"] = "tier_4_no_site"
            result["error"] = f"http_{r.status_code}"
            return result

        if detect_anti_bot(r.status_code, r.text):
            result["anti_bot"] = True
            result["tier"] = "tier_5_waf"
            result["error"] = "anti_bot_detected"
            # Continue to detect platform anyway
            result["platform_guess"] = detect_platform(r.text, dict(r.headers))
            return result

        if r.status_code == 404:
            result["tier"] = "tier_4_no_site"
            result["error"] = "http_404"
            return result

        if len(r.text) < 1000:
            result["tier"] = "tier_4_no_site"
            result["error"] = "html_too_short"
            return result

        platform = detect_platform(r.text, dict(r.headers))
        result["platform_guess"] = platform

        # Try sitemap
        try:
            domain_root = re.match(r"(https?://[^/]+)", url).group(1)
            sm = await client.get(f"{domain_root}/sitemap.xml", follow_redirects=True, headers={"User-Agent": USER_AGENT}, timeout=10.0)
            result["has_sitemap"] = sm.status_code == 200 and len(sm.text) > 100
        except Exception:
            result["has_sitemap"] = False

        # Tier assignment
        known_platforms = {"shopify", "vtex", "wake", "nuvemshop", "woocommerce", "tray", "loja_integrada"}
        if platform in known_platforms and result["has_sitemap"] and inci_flag != "no":
            result["tier"] = "tier_1_easy"
        elif platform in known_platforms:
            result["tier"] = "tier_2_check"
        elif platform:
            result["tier"] = "tier_3_custom"
        else:
            result["tier"] = "tier_3_custom"

    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadTimeout) as e:
        result["tier"] = "tier_4_no_site"
        result["error"] = f"connection: {type(e).__name__}"
    except Exception as e:
        result["tier"] = "tier_4_no_site"
        result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
    return result


async def main_async() -> None:
    with open(BRANDS_JSON) as f:
        all_brands = json.load(f)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT brand_slug FROM products")
    in_db = {r[0] for r in cur.fetchall()}
    conn.close()

    pending = [b for b in all_brands if b["brand_slug"] not in in_db]
    print(f"Total brands: {len(all_brands)}, in DB: {len(in_db)}, pending to triage: {len(pending)}")

    sem = asyncio.Semaphore(CONCURRENCY)

    async def bounded_probe(client, brand):
        async with sem:
            res = await probe_brand(client, brand)
            tier = res["tier"]
            slug = res["brand_slug"]
            extra = res.get("platform_guess") or res.get("error") or ""
            print(f"  [{tier}] {slug:30s} {extra}")
            return res

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        results = await asyncio.gather(*(bounded_probe(client, b) for b in pending))

    # Summary
    from collections import Counter
    tiers = Counter(r["tier"] for r in results)
    platforms = Counter(r.get("platform_guess") or "?" for r in results)
    print("\n=== TIERS ===")
    for t, n in tiers.most_common():
        print(f"  {t}: {n}")
    print("\n=== PLATFORMS ===")
    for p, n in platforms.most_common():
        print(f"  {p}: {n}")

    out = Path(OUTPUT)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nWritten {len(results)} entries to {out}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
