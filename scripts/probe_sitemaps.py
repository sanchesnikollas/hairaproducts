"""Concurrent sitemap probe for failed wave 9b brands."""
import asyncio
import re
import httpx

FAILED = {
    'barba-urbana': ('wake', 'burb.com.br'),
    'begonia-cosmeticos': ('shopify', 'begoniacosmeticos.com.br'),
    'beudose': ('shopify', 'beudose.com.br'),
    'cadiveu-professional': ('shopify', 'cadiveu.com.br'),
    'coiffer': ('woocommerce', 'coiffercosmeticos.com.br'),
    'glatten-professional': ('wake', 'glatten.com.br'),
    'kiron-cosmeticos': ('shopify', 'kironcosmeticos.com.br'),
    'magic-science': ('wake', 'magicscience.com.br'),
    'meu-q': ('shopify', 'meuq.com.br'),
    'mojo': ('wake', 'mojo.com.br'),
    'natuhair': ('wake', 'natuhair.com.br'),
    'petre-cosmetics': ('wake', 'petrecosmetics.com.br'),
    'wbeauty-cosmeticos': ('wake', 'wbeautycosmeticos.com.br'),
}
PATHS = ['/sitemap.xml', '/sitemap_index.xml', '/sitemap-products.xml',
         '/produtos.xml', '/sitemap_products_1.xml', '/wp-sitemap.xml',
         '/wp-sitemap-posts-product-1.xml']


async def probe_one(client, slug, plat, domain):
    found = []
    # Try robots first
    try:
        r = await client.get(f'https://{domain}/robots.txt', timeout=4.0, follow_redirects=True)
        if r.status_code == 200:
            for line in r.text.split('\n'):
                if line.strip().lower().startswith('sitemap:'):
                    sm_url = line.split(':', 1)[1].strip()
                    found.append(('robots', sm_url))
    except Exception:
        pass

    # Try standard paths
    for p in PATHS:
        for prefix in ['', 'www.']:
            url = f'https://{prefix}{domain}{p}'
            try:
                r = await client.get(url, timeout=4.0, follow_redirects=True)
                if r.status_code == 200 and ('xml' in r.headers.get('content-type', '') or
                                              '<urlset' in r.text[:500] or
                                              '<sitemapindex' in r.text[:500]):
                    urls = re.findall(r'<loc>([^<]+)</loc>', r.text)
                    found.append((p, url, len(urls), urls[0][:100] if urls else ''))
                    break
            except Exception:
                pass
        if found and isinstance(found[-1], tuple) and len(found[-1]) >= 3:
            break

    return slug, plat, domain, found


async def main():
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        tasks = [probe_one(client, s, p, d) for s, (p, d) in FAILED.items()]
        for coro in asyncio.as_completed(tasks):
            slug, plat, domain, found = await coro
            print(f'=== {slug} ({plat}) {domain} ===', flush=True)
            if not found:
                print('  NO sitemap found', flush=True)
            else:
                for f in found:
                    if isinstance(f, tuple) and len(f) >= 3:
                        print(f'  FOUND: {f[1]} ({f[2]} URLs)', flush=True)
                        if len(f) >= 4 and f[3]:
                            print(f'    sample: {f[3]}', flush=True)
                    else:
                        print(f'  hint: {f}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
