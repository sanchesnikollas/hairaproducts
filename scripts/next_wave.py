"""Motor do workflow de cobertura — escolhe a próxima leva de marcas pra onboardar.

Lê config/brands.json + data/triagem-2026-05-12.json + estado atual do haira.db
e retorna as próximas N marcas a processar, priorizando por probabilidade de
sucesso:

  1. tier_1 com blueprint, 0 produtos        (auto-blueprint pronto)
  2. tier_2 com blueprint, 0 produtos        (blueprint manual já existe)
  3. tier_1 com 1-9 produtos                 (re-scrape, blueprint existe)
  4. tier_2 SEM blueprint, 0 produtos        (precisa `haira blueprint` antes)

Cada item vem com flag `needs_blueprint`. O loop usa essa lista pra rodar
`haira blueprint` (se preciso) + `haira scrape` + `haira labels`.

Uso:
    python scripts/next_wave.py                 # resumo do backlog (humano)
    python scripts/next_wave.py --size 8 --json # próxima leva como JSON (loop)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
TERMINAL = {"out_of_scope", "blocked", "no_source"}


def load_state():
    existing = {f[:-5] for f in os.listdir(ROOT / "config/blueprints") if f.endswith(".yaml")}
    c = sqlite3.connect(str(ROOT / "haira.db"))
    counts = dict(c.execute("SELECT brand_slug, COUNT(*) FROM products GROUP BY brand_slug").fetchall())
    c.close()
    brands = json.load(open(ROOT / "config/brands.json", encoding="utf-8"))
    status = {b["brand_slug"]: b.get("status") for b in brands}
    triagem = json.load(open(ROOT / "data/triagem-2026-05-12.json", encoding="utf-8"))
    tier = {r["brand_slug"]: r["tier"] for r in triagem["results"]}
    return existing, counts, status, tier, brands


def build_queue(existing, counts, status, tier):
    """Ordered list of (slug, tier, needs_blueprint) for brands still to do."""
    def n(slug):
        return counts.get(slug, 0)

    def active(slug):
        return status.get(slug) not in TERMINAL

    buckets = {
        "tier1_bp_zero": [],   # tier_1, has blueprint, 0 products
        "tier2_bp_zero": [],   # tier_2, has blueprint, 0 products
        "tier1_low": [],       # tier_1, 1-9 products (re-scrape)
        "tier2_nobp_zero": [], # tier_2, no blueprint, 0 products
    }
    for slug, tr in tier.items():
        if not active(slug):
            continue
        cnt = n(slug)
        has_bp = slug in existing
        if cnt >= 10:
            continue  # already covered
        if tr == "tier_1_easy" and has_bp and cnt == 0:
            buckets["tier1_bp_zero"].append(slug)
        elif tr == "tier_2_medium" and has_bp and cnt == 0:
            buckets["tier2_bp_zero"].append(slug)
        elif tr == "tier_1_easy" and 0 < cnt < 10:
            buckets["tier1_low"].append(slug)
        elif tr == "tier_2_medium" and not has_bp and cnt == 0:
            buckets["tier2_nobp_zero"].append(slug)

    # Priority order tuned from waves 1-7: tier_2 com blueprint é o maior poço
    # inexplorado (51, nunca rodadas). tier_1 zeradas restantes (17) já foram
    # tentadas e voltaram 0/quarantined nas waves 6-7 → vão pro fim.
    queue = []
    for slug in sorted(buckets["tier2_bp_zero"]):
        queue.append((slug, "tier_2_medium", False))
    for slug in sorted(buckets["tier1_low"]):
        queue.append((slug, "tier_1_easy", False))
    for slug in sorted(buckets["tier2_nobp_zero"]):
        queue.append((slug, "tier_2_medium", True))
    for slug in sorted(buckets["tier1_bp_zero"]):
        queue.append((slug, "tier_1_easy", False))
    return queue, buckets


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=8, help="tamanho da leva")
    ap.add_argument("--json", action="store_true", help="emite a próxima leva como JSON")
    args = ap.parse_args()

    existing, counts, status, tier, brands = load_state()
    queue, buckets = build_queue(existing, counts, status, tier)

    with_ge10 = sum(1 for s, cnt in counts.items() if cnt >= 10)
    with_any = len(counts)

    if args.json:
        batch = queue[: args.size]
        print(json.dumps({
            "batch": [{"slug": s, "tier": t, "needs_blueprint": nb} for s, t, nb in batch],
            "queue_remaining": len(queue),
            "brands_ge10": with_ge10,
            "brands_any": with_any,
            "target_ge10": 250,
            "deficit_ge10": max(0, 250 - with_ge10),
        }, ensure_ascii=False, indent=2))
        return

    # Human summary
    print("=== Backlog de cobertura (rumo a 250 marcas com >=10 produtos) ===\n")
    print(f"Marcas com produtos:     {with_any}")
    print(f"Marcas com >=10 produtos: {with_ge10}  (faltam {max(0, 250 - with_ge10)} p/ meta 250)\n")
    print("Fila priorizada de onboarding:")
    print(f"  1. tier_1 c/ blueprint, 0 prod:   {len(buckets['tier1_bp_zero'])}")
    print(f"  2. tier_2 c/ blueprint, 0 prod:   {len(buckets['tier2_bp_zero'])}")
    print(f"  3. tier_1 com 1-9 prod (rescrape): {len(buckets['tier1_low'])}")
    print(f"  4. tier_2 SEM blueprint, 0 prod:  {len(buckets['tier2_nobp_zero'])}")
    print(f"\n  TOTAL na fila: {len(queue)}")
    print(f"\nPróxima leva (size {args.size}):")
    for s, t, nb in queue[: args.size]:
        flag = " [+blueprint]" if nb else ""
        print(f"  - {s}  ({t}){flag}")


if __name__ == "__main__":
    main()
