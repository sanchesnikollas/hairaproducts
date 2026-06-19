# src/core/firecrawl_client.py
"""Firecrawl fallback fetcher — managed scrape API (renders JS, bypasses WAFs).

Used ONLY as a fallback when the native fetch (curl_cffi / httpx / Playwright)
fails or returns an empty page, and ONLY when FIRECRAWL_API_KEY is set. Fully
dormant (zero cost, zero behaviour change) without the key. This is the surgical
reinforcement for the ~25% of fetches that fail and for WAF/JS-tab brands —
never the default path, because Firecrawl is billed per page.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_FIRECRAWL_ENDPOINT = os.environ.get(
    "FIRECRAWL_ENDPOINT", "https://api.firecrawl.dev/v1/scrape"
)


def firecrawl_available() -> bool:
    """True when a Firecrawl API key is configured."""
    return bool(os.environ.get("FIRECRAWL_API_KEY", "").strip())


def firecrawl_fetch_html(url: str, *, timeout: float = 60.0) -> str | None:
    """Fetch a URL's rendered HTML via Firecrawl. Returns None when unavailable/fails.

    Never raises — a fallback must not break the caller; on any problem it returns
    None so the caller keeps whatever the native fetch produced.
    """
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        return None
    try:
        import httpx

        resp = httpx.post(
            _FIRECRAWL_ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["html"], "onlyMainContent": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        html = (data.get("data") or {}).get("html")
        if html:
            logger.info("Firecrawl fetched %s (%d bytes)", url, len(html))
            return html
        logger.warning("Firecrawl returned no html for %s: %s", url, data.get("error") or "(empty)")
        return None
    except Exception as e:  # noqa: BLE001 — fallback must never raise
        logger.warning("Firecrawl fetch failed for %s: %s", url, e)
        return None
