"""Split a single description blob into its real sections.

Many sites (Bio-instinto, Avatim, alphahall, ...) dump ALL product copy into one
description field with inline markers ("Modo de uso:", "Composição:",
"Ingredientes:"). The section_classifier only fires on distinct DOM headings, so
on those pages `usage_instructions` stays blank and the "como usar" text pollutes
the description (exactly the client feedback of 2026-06).

This is a conservative text-level fallback: it only treats a phrase as a section
header when it is anchored (start / after a sentence-end / bullet / newline) AND
immediately followed by a separator (':', '-', '—'). That avoids matching the
phrase inside marketing prose ("aprenda como usar o produto") and never corrupts
a description that has no real markers (returns {} → caller leaves it untouched).
"""
from __future__ import annotations

import re

# field -> header phrases. ingredients_inci is listed before composition so that
# "composição completa" wins over plain "composição" at the same position.
_MARKERS: list[tuple[str, list[str]]] = [
    ("care_usage", [
        r"modo de uso", r"modo de usar", r"como usar", r"como aplicar",
        r"forma de uso", r"forma de aplica[çc][aã]o", r"instru[çc][õo]es de uso",
        r"aplica[çc][aã]o",
    ]),
    ("ingredients_inci", [
        r"ingredientes", r"composi[çc][aã]o completa", r"inci",
    ]),
    ("composition", [
        r"composi[çc][aã]o", r"princ[íi]pios ativos", r"ativos principais",
    ]),
    ("benefits", [
        r"benef[íi]cios", r"benefits",
    ]),
]

# Header must be anchored and followed by a separator. The leading separator char
# is consumed by the match, so segment slicing stays clean.
_SEP_BEFORE = r"(?:^|[\n\r\.;•·•\)\]])\s*"
_SEP_AFTER = r"\s*[:\-–—]\s*"


def _compile(pat: str) -> re.Pattern:
    return re.compile(_SEP_BEFORE + r"(?:" + pat + r")" + _SEP_AFTER, re.IGNORECASE)


_COMPILED: list[tuple[str, re.Pattern]] = [
    (field, _compile(pat)) for field, pats in _MARKERS for pat in pats
]


def split_description_blob(text: str | None) -> dict[str, str]:
    """Return {field: content} for inline sections found in a description blob.

    Keys may include: description (text before the first marker), care_usage,
    composition, ingredients_inci, benefits. First occurrence per field wins.
    Returns {} when no anchored marker is found (caller must leave fields as-is).
    """
    if not text or not isinstance(text, str):
        return {}

    hits: list[tuple[int, int, str]] = []
    for field, rx in _COMPILED:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), field))
    if not hits:
        return {}

    hits.sort(key=lambda h: h[0])
    # Drop overlapping markers (keep the earliest at each position).
    pruned: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, field in hits:
        if start >= last_end:
            pruned.append((start, end, field))
            last_end = end

    result: dict[str, str] = {}
    head = text[: pruned[0][0]].strip(" \n\r\t:-–—•·")
    if head:
        result["description"] = head
    for i, (start, end, field) in enumerate(pruned):
        seg_end = pruned[i + 1][0] if i + 1 < len(pruned) else len(text)
        seg = text[end:seg_end].strip(" \n\r\t:-–—•·")
        if seg and field not in result:
            result[field] = seg
    return result
