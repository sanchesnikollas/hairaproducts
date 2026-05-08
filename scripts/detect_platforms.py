"""Re-detect platforms for failed/pending brands.

Scans the homepage HTML for platform signatures (generator meta, JS files,
URL patterns). Reports brands whose triage platform_guess is wrong.
"""
import asyncio
import json
import re
import sys

import httpx

SIGNATURES = {
    "loja_integrada": [
        r'name="generator"\s+content="Loja Integrada"',
        r'/static/loja_integrada/',
        r'lojaintegrada\.com\.br',
    ],
    "wake": [
        r'fbits-',
        r'cdn\.awsli\.com\.br',
        r'mage_redirect.*wake',
    ],
    "shopify": [
        r'cdn\.shopify\.com',
        r'Shopify\.theme',
        r'/products\.json',
    ],
    "vtex": [
        r'vtex\.com\.br',
        r'__RUNTIME__.*vtex',
    ],
    "woocommerce": [
        r'wp-content/plugins/woocommerce',
        r'/wp-content/uploads',
        r'WooCommerce',
    ],
    "tray": [
        r'tcdn\.com\.br',
        r'tray-corp',
    ],
    "magento": [
        r'Magento',
        r'/skin/frontend/',
        r'mage/cookies',
    ],
    "nuvemshop": [
        r'tiendanube',
        r'nuvemshop',
    ],
    "wix": [
        r'static\.wixstatic\.com',
        r'wix\.com',
    ],
    "prestashop": [
        r'PrestaShop',
        r'/img/p/',
    ],
}


async def detect(client, slug, url):
    try:
        r = await client.get(url, timeout=8.0, follow_redirects=True)
        if r.status_code >= 400:
            return slug, None, f'http {r.status_code}', str(r.url)
        text = r.text
        # Get redirect URL too
        final_url = str(r.url)
        scores = {}
        for plat, sigs in SIGNATURES.items():
            scores[plat] = sum(1 for s in sigs if re.search(s, text, re.IGNORECASE))
        best = max(scores.items(), key=lambda x: x[1])
        if best[1] == 0:
            return slug, None, "unknown", final_url
        return slug, best[0], best[1], final_url
    except Exception as e:
        return slug, None, f'err: {str(e)[:40]}', url


async def main():
    with open('config/brands_triage.json') as f:
        triage = json.load(f)
    import os
    bp = {f.replace('.yaml', '') for f in os.listdir('config/blueprints') if f.endswith('.yaml')}
    # Brands without blueprint
    pending = [b for b in triage if b['brand_slug'] not in bp]

    # Limit: first 80 with priority/has_sitemap
    candidates = [b for b in pending if b.get('http_status') == 200][:80]

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [detect(client, b['brand_slug'], b['official_url_root']) for b in candidates]
        for coro in asyncio.as_completed(tasks):
            slug, plat, score, final = await coro
            old = next((b['platform_guess'] for b in triage if b['brand_slug']==slug), None)
            mismatch = '*' if plat and plat != old else ' '
            print(f'{mismatch} {slug:<30} old={old or "-":<15} → detected={plat or "-":<15} (score={score}) final={final[:60]}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
