from __future__ import annotations

from src.enrichment.orchestrator import run_gold_rollout


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeBrowser:
    def close(self):
        pass


def _factories():
    return dict(
        llm_factory=lambda cap: object(),
        browser_factory=lambda brand: _FakeBrowser(),
    )


def test_rollout_aggregates_per_brand_and_totals(monkeypatch):
    # before/after gold per brand (recompute called twice per brand)
    seq = iter([
        {"gold": 10, "total": 100},  # A before
        {"gold": 16, "total": 100},  # A after
        {"gold": 5, "total": 50},    # B before
        {"gold": 8, "total": 50},    # B after
    ])
    monkeypatch.setattr("src.enrichment.orchestrator.recompute_brand_gold", lambda s, b: next(seq))

    def fake_enrich(session, brand, *, llm, browser, limit, log):
        n = 6 if brand == "A" else 3
        return {"usage_found": n, "inci_found": 0, "fetch_failed": 1, "cost": {"total_calls": n}}

    monkeypatch.setattr("src.enrichment.enricher.enrich_brand", fake_enrich)

    report = run_gold_rollout(lambda: _FakeSession(), brands=["A", "B"], **_factories())

    assert report["brands"][0]["delta"] == 6
    assert report["brands"][1]["delta"] == 3
    assert report["totals"]["gold_delta"] == 9
    assert report["totals"]["usage_found"] == 9
    assert report["totals"]["total_calls"] == 9
    assert report["totals"]["fetch_failed"] == 2
    assert report["totals"]["brands_processed"] == 2


def test_global_budget_stops_rollout(monkeypatch):
    seq = iter([{"gold": 10, "total": 100}, {"gold": 16, "total": 100}])
    monkeypatch.setattr("src.enrichment.orchestrator.recompute_brand_gold", lambda s, b: next(seq))
    monkeypatch.setattr(
        "src.enrichment.enricher.enrich_brand",
        lambda session, brand, **k: {"usage_found": 6, "inci_found": 0, "fetch_failed": 0, "cost": {"total_calls": 6}},
    )

    report = run_gold_rollout(lambda: _FakeSession(), brands=["A", "B"], total_call_budget=5, **_factories())

    # A runs (uses 6, over budget), B is skipped before processing
    assert report["stopped_at_budget"] == "B"
    assert len(report["brands"]) == 1


def test_one_brand_error_does_not_abort(monkeypatch):
    monkeypatch.setattr("src.enrichment.orchestrator.recompute_brand_gold", lambda s, b: {"gold": 10, "total": 100})

    def fake_enrich(session, brand, **k):
        if brand == "A":
            raise RuntimeError("boom")
        return {"usage_found": 2, "inci_found": 0, "fetch_failed": 0, "cost": {"total_calls": 2}}

    monkeypatch.setattr("src.enrichment.enricher.enrich_brand", fake_enrich)

    report = run_gold_rollout(lambda: _FakeSession(), brands=["A", "B"], **_factories())

    assert report["brands"][0].get("error")
    assert "error" not in report["brands"][1]
    assert report["totals"]["brands_errored"] == 1
    assert report["totals"]["brands_processed"] == 1
