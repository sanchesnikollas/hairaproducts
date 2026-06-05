"""Minimal Apify REST client. We use Apify to scrape sources our in-house
crawler can't reach (SPA + Cloudflare on distributors like Beleza na Web),
then pipe the output through the existing HAIRA pipeline.

Why not the official SDK: keeps the dep surface small (httpx is already in
the project) and the surface we need is tiny — run an actor, wait for
completion, fetch the dataset.

Required env: APIFY_TOKEN (set on Railway + .env).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("haira.apify")

BASE_URL = "https://api.apify.com/v2"
DEFAULT_TIMEOUT = 30
POLL_INTERVAL = 5
MAX_WAIT_SECONDS = 60 * 10  # 10 min cap for the PoC


class ApifyError(RuntimeError):
    pass


def _token() -> str:
    t = os.environ.get("APIFY_TOKEN", "").strip()
    if not t:
        raise ApifyError("APIFY_TOKEN not configured")
    return t


def start_actor_run(actor_id: str, run_input: dict[str, Any]) -> dict:
    """Trigger an actor run. Returns the run object (includes id, defaultDatasetId)."""
    url = f"{BASE_URL}/acts/{actor_id}/runs"
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as c:
        r = c.post(url, params={"token": _token()}, json=run_input)
        if r.status_code >= 300:
            raise ApifyError(f"start_actor_run {r.status_code}: {r.text[:300]}")
        return r.json().get("data", {})


def get_run(run_id: str) -> dict:
    url = f"{BASE_URL}/actor-runs/{run_id}"
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as c:
                r = c.get(url, params={"token": _token()})
                if r.status_code >= 300:
                    raise ApifyError(f"get_run {r.status_code}: {r.text[:300]}")
                return r.json().get("data", {})
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
            last_exc = e
            time.sleep(2 ** attempt)  # backoff: 1, 2, 4, 8s
    raise ApifyError(f"get_run failed after retries: {last_exc}")


def wait_for_run(run_id: str, max_seconds: int = MAX_WAIT_SECONDS) -> dict:
    """Poll until the run leaves the RUNNING/READY state. Returns the final run object.
    Tolerates transient poll failures (network blips) without aborting the wait."""
    waited = 0
    consecutive_failures = 0
    while waited < max_seconds:
        try:
            run = get_run(run_id)
            consecutive_failures = 0
            status = run.get("status")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                return run
        except ApifyError as e:
            consecutive_failures += 1
            if consecutive_failures >= 5:
                raise ApifyError(f"too many consecutive poll failures: {e}")
            logger.warning("poll failure %d for run %s: %s", consecutive_failures, run_id, e)
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
    raise ApifyError(f"run {run_id} did not finish within {max_seconds}s")


def fetch_dataset_items(dataset_id: str, limit: int = 1000) -> list[dict]:
    """Fetch up to `limit` items from a dataset."""
    url = f"{BASE_URL}/datasets/{dataset_id}/items"
    with httpx.Client(timeout=60) as c:
        r = c.get(url, params={"token": _token(), "limit": limit, "format": "json"})
        if r.status_code >= 300:
            raise ApifyError(f"fetch_dataset {r.status_code}: {r.text[:300]}")
        return r.json() or []
