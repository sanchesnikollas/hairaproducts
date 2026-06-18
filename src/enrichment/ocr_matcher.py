"""Match a physical product (read by OCR) to the HAIRA catalog.

Cascade, stop at the first confident tier:
  0. EAN/barcode exact            -> confidence 1.0
  1. brand + name fuzzy           -> SequenceMatcher (4 variants), volume tiebreak
  2. back-label INCI verification -> Jaccard overlap confirms/flags a name match

Pure functions over candidate dicts so the matcher is unit-testable without a DB.
The /moon/identify endpoint fetches candidates and calls match_ocr.
Reuses normalize_name from src/enrichment/matcher.py.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from src.enrichment.matcher import normalize_name

AUTO_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.75
INCI_CONFIRM = 0.60      # Jaccard >= -> confirmed
INCI_MISMATCH = 0.30     # Jaccard <  -> mismatch (possible reformulation in between)

_VOL_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|l|lt|g|kg|oz)\b", re.IGNORECASE)
_VOL_FACTOR = {"ml": 1.0, "l": 1000.0, "lt": 1000.0, "g": 1.0, "kg": 1000.0, "oz": 30.0}


def _norm_ean(ean: str | None) -> str:
    return re.sub(r"\D", "", ean or "")


def _name_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    tok = SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()
    return max(seq, tok)


def _volume_units(text: str | None) -> float | None:
    if not text:
        return None
    m = _VOL_RE.search(text.lower())
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    return value * _VOL_FACTOR.get(m.group(2).lower(), 1.0)


def _inci_jaccard(a: list[str] | None, b: list[str] | None) -> float | None:
    sa = {normalize_name(x) for x in (a or []) if x}
    sb = {normalize_name(x) for x in (b or []) if x}
    if not sa or not sb:
        return None
    union = len(sa | sb)
    return (len(sa & sb) / union) if union else 0.0


def _inci_verdict(jaccard: float | None) -> dict | None:
    if jaccard is None:
        return None
    if jaccard >= INCI_CONFIRM:
        verdict = "confirmed"
    elif jaccard < INCI_MISMATCH:
        verdict = "mismatch"
    else:
        verdict = "possible_reformulation"
    return {"overlap_pct": round(jaccard, 3), "verdict": verdict}


def _candidate_brief(cand: dict, confidence: float) -> dict:
    return {
        "product_id": cand.get("id"),
        "product_name": cand.get("product_name"),
        "brand_slug": cand.get("brand_slug"),
        "match_confidence": round(confidence, 3),
    }


def _match(cand: dict, method: str, confidence: float, back_label_inci: list[str] | None) -> dict:
    return {
        "product_id": cand.get("id"),
        "product_name": cand.get("product_name"),
        "brand_slug": cand.get("brand_slug"),
        "match_method": method,
        "match_confidence": round(confidence, 3),
        "is_gold": cand.get("gold_status") == "gold",
        "inci_verification": _inci_verdict(_inci_jaccard(back_label_inci, cand.get("inci_ingredients"))),
    }


def match_ocr(
    *,
    candidates: list[dict],
    ean: str | None = None,
    brand_text: str | None = None,
    product_name_text: str | None = None,
    volume_text: str | None = None,
    back_label_inci: list[str] | None = None,
) -> dict:
    """Match OCR'd fields to a catalog product.

    candidates: dicts with id, product_name, ean, size_volume, inci_ingredients,
    gold_status, brand_slug. Returns {match, candidates, not_in_base, is_gold}.
    """
    # Tier 0 — EAN exact
    qean = _norm_ean(ean)
    if qean:
        for c in candidates:
            if _norm_ean(c.get("ean")) == qean:
                m = _match(c, "ean", 1.0, back_label_inci)
                return {"match": m, "candidates": [], "not_in_base": False, "is_gold": m["is_gold"]}

    # Tier 1 — brand + name fuzzy (with volume tiebreak)
    if product_name_text:
        qn = normalize_name(product_name_text)
        qn_s = normalize_name(product_name_text, strip_brand=brand_text) if brand_text else qn
        qvol = _volume_units(volume_text) or _volume_units(product_name_text)

        scored: list[tuple[float, dict]] = []
        for c in candidates:
            cname = c.get("product_name") or ""
            cn = normalize_name(cname)
            cn_s = normalize_name(cname, strip_brand=brand_text) if brand_text else cn
            ratio = max(_name_ratio(qn, cn), _name_ratio(qn_s, cn_s),
                        _name_ratio(qn, cn_s), _name_ratio(qn_s, cn))
            # Volume conflict caps the score below auto -> forces review/candidate.
            cvol = _volume_units(c.get("size_volume")) or _volume_units(cname)
            if qvol and cvol and abs(qvol - cvol) > 1e-6:
                ratio = min(ratio, AUTO_THRESHOLD - 0.01)
            scored.append((ratio, c))

        scored.sort(key=lambda x: -x[0])
        if scored:
            best_ratio, best = scored[0]
            extras = [_candidate_brief(c, r) for r, c in scored[1:4] if r >= REVIEW_THRESHOLD]
            if best_ratio >= AUTO_THRESHOLD:
                m = _match(best, "name_fuzzy", best_ratio, back_label_inci)
                return {"match": m, "candidates": extras, "not_in_base": False, "is_gold": m["is_gold"]}
            if best_ratio >= REVIEW_THRESHOLD:
                cands = [_candidate_brief(best, best_ratio)] + extras
                return {"match": None, "candidates": cands, "not_in_base": False, "is_gold": False}

    return {"match": None, "candidates": [], "not_in_base": True, "is_gold": False}
