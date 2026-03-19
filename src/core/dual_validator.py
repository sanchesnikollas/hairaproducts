from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class FieldComparison:
    field_name: str
    pass_1_value: str | None
    pass_2_value: str | None
    matches: bool
    resolution: str  # auto_matched, pending


@dataclass
class InciComparison:
    matches: bool
    mismatches: list[tuple[int, str | None, str | None]]


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def compare_inci_lists(list_a: list[str], list_b: list[str]) -> InciComparison:
    norm_a = [normalize_text(x) for x in list_a]
    norm_b = [normalize_text(x) for x in list_b]

    if len(norm_a) != len(norm_b):
        mismatches = [(i, norm_a[i] if i < len(norm_a) else None, norm_b[i] if i < len(norm_b) else None)
                      for i in range(max(len(norm_a), len(norm_b)))]
        return InciComparison(matches=False, mismatches=mismatches)

    mismatches = []
    for i, (a, b) in enumerate(zip(norm_a, norm_b)):
        if a != b:
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio < 0.85:
                mismatches.append((i, a, b))

    return InciComparison(matches=len(mismatches) == 0, mismatches=mismatches)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def compare_fields(field_name: str, val_1: str | None, val_2: str | None) -> FieldComparison:
    if val_1 is None and val_2 is None:
        return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    if val_1 is None or val_2 is None:
        return FieldComparison(field_name, val_1, val_2, matches=False, resolution="pending")

    # Price: numeric tolerance ±1%
    if field_name == "price":
        try:
            p1, p2 = float(val_1), float(val_2)
            if p1 == 0 and p2 == 0:
                return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")
            if p1 > 0 and abs(p1 - p2) / p1 <= 0.01:
                return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")
        except (ValueError, ZeroDivisionError):
            pass
        return FieldComparison(field_name, val_1, val_2, matches=False, resolution="pending")

    norm_1 = normalize_text(val_1)
    norm_2 = normalize_text(val_2)

    if norm_1 == norm_2:
        return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    # Similarity for text fields
    if field_name in ("description", "composition", "care_usage"):
        if _similarity(val_1, val_2) >= 0.90:
            return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    # URL comparison
    if field_name == "image_url_main":
        clean_1 = re.sub(r"^https?://", "", norm_1).rstrip("/")
        clean_2 = re.sub(r"^https?://", "", norm_2).rstrip("/")
        if clean_1 == clean_2:
            return FieldComparison(field_name, val_1, val_2, matches=True, resolution="auto_matched")

    return FieldComparison(field_name, val_1, val_2, matches=False, resolution="pending")
