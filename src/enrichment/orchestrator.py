"""Gold rollout orchestrator — the per-brand workflow, loopable across the catalog.

For each brand: measure Gold (before) → enrich (recover INCI + 'como usar' from the
product's own page) → recompute the Gold gate (after) → record the delta. Runs with
a global LLM-call budget so the whole rollout is cost-bounded. Produces a per-brand
+ aggregate "guarantee report" (Gold gained / still-blocked / cost) so nothing is
left in a silent limbo.

The Gate (evaluate_gold) stays the single source of truth — the orchestrator never
flips a status by hand; it only re-runs the gate after enrichment changes the data.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func

from src.core.gold_gate import evaluate_gold
from src.core.models import GoldStatus
from src.storage.orm_models import ProductORM

_GOLD_KEYS = ["gold", "gold_candidate", "catalog", "raw", "gold_rejected"]


def recompute_brand_gold(session, brand_slug: str) -> dict[str, int]:
    """Re-run the Gold gate for every product of a brand, persist, return counts.

    A human `gold_rejected` verdict is terminal and never overwritten.
    """
    products = session.query(ProductORM).filter(ProductORM.brand_slug == brand_slug).all()
    now = datetime.now(timezone.utc)
    counts: Counter = Counter()
    for p in products:
        ev = evaluate_gold(p, session=session)
        preserved = p.gold_status == GoldStatus.GOLD_REJECTED.value
        if not preserved:
            p.gold_status = ev.gold_status.value
            p.gold_blockers = ev.blockers_as_dicts()
            p.gold_evaluated_at = now
        eff = GoldStatus.GOLD_REJECTED.value if preserved else ev.gold_status.value
        counts[eff] += 1
    session.commit()
    out = {k: counts.get(k, 0) for k in _GOLD_KEYS}
    out["total"] = sum(counts.values())
    return out


def list_enrichable_brands(session) -> list[str]:
    """Brands with catalog (not-yet-Gold real-hair) products, busiest first."""
    rows = (
        session.query(ProductORM.brand_slug, func.count(ProductORM.id))
        .filter(ProductORM.gold_status == "catalog")
        .group_by(ProductORM.brand_slug)
        .order_by(func.count(ProductORM.id).desc())
        .all()
    )
    return [b for b, _ in rows]


def run_gold_rollout(
    session_factory: Callable[[], Any],
    *,
    llm_factory: Callable[[int], Any],
    browser_factory: Callable[[str], Any],
    brands: list[str] | None = None,
    per_brand_limit: int = 0,
    per_brand_cap: int = 300,
    total_call_budget: int | None = None,
    log: Callable[[str], None] = lambda _m: None,
) -> dict[str, Any]:
    """Run the enrich→regate funnel across brands within a global call budget.

    A fresh session per brand keeps memory bounded over a long batch. Returns a
    per-brand + aggregate report. One brand failing never aborts the rollout.
    """
    if brands is None:
        with session_factory() as s:
            brands = list_enrichable_brands(s)

    report: dict[str, Any] = {"brands": [], "stopped_at_budget": None}
    calls_used = 0

    for brand in brands:
        if total_call_budget is not None and calls_used >= total_call_budget:
            report["stopped_at_budget"] = brand
            log(f"budget reached ({calls_used} calls) — stopping before {brand}")
            break

        remaining = None if total_call_budget is None else max(0, total_call_budget - calls_used)
        cap = per_brand_cap if remaining is None else min(per_brand_cap, remaining)

        try:
            with session_factory() as session:
                before = recompute_brand_gold(session, brand)["gold"]
                llm = llm_factory(cap)
                browser = browser_factory(brand)
                try:
                    from src.enrichment.enricher import enrich_brand
                    stats = enrich_brand(
                        session, brand, llm=llm, browser=browser,
                        limit=per_brand_limit, log=log,
                    )
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass
                after = recompute_brand_gold(session, brand)
            used = (stats.get("cost") or {}).get("total_calls", 0)
            calls_used += used
            entry = {
                "brand": brand,
                "gold_before": before,
                "gold_after": after["gold"],
                "delta": after["gold"] - before,
                "usage_found": stats.get("usage_found", 0),
                "inci_found": stats.get("inci_found", 0),
                "fetch_failed": stats.get("fetch_failed", 0),
                "calls": used,
            }
            report["brands"].append(entry)
            log(f"{brand}: gold {before}->{after['gold']} (+{after['gold'] - before}); {used} calls; total {calls_used}")
        except Exception as e:  # noqa: BLE001 — one bad brand must not kill the rollout
            report["brands"].append({"brand": brand, "error": str(e)})
            log(f"{brand}: ERROR {e}")

    ok = [b for b in report["brands"] if "error" not in b]
    report["totals"] = {
        "brands_processed": len(ok),
        "brands_errored": len(report["brands"]) - len(ok),
        "gold_delta": sum(b["delta"] for b in ok),
        "usage_found": sum(b["usage_found"] for b in ok),
        "inci_found": sum(b["inci_found"] for b in ok),
        "fetch_failed": sum(b["fetch_failed"] for b in ok),
        "total_calls": calls_used,
    }
    return report
