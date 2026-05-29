"""Doutoras knowledge base — loaded once per process from the
`knowledge_chunks` DB table, injected as Moon's cached system context.

DB is the source of truth (the repo is public; proprietary content never
touches git). Local ingestion: `scripts/ingest_knowledge.py`. Prod sync:
`scripts/sync_knowledge_base.py` -> `/api/admin/sync-knowledge-base`.

The loader returns:
  - `system_block`: a single string ready to be injected into the system
    prompt, with each source preceded by `### Fonte: <name>` so the LLM can
    cite which document it relied on.
  - `sources`: list of original filenames (for the `kb_sources` field in
    chat responses and for an ops review screen later).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

logger = logging.getLogger("haira.kb")


@dataclass
class KnowledgeBase:
    system_block: str
    sources: list[str]
    char_count: int


_CACHED: KnowledgeBase | None = None


def load_knowledge_base() -> KnowledgeBase:
    """Cached at process scope. Call `reset_kb_cache()` after sync to refresh."""
    global _CACHED
    if _CACHED is not None:
        return _CACHED

    from src.storage.database import get_engine
    from src.storage.knowledge_models import KnowledgeChunkORM

    try:
        with Session(get_engine()) as s:
            rows = (
                s.query(KnowledgeChunkORM)
                .order_by(KnowledgeChunkORM.source.asc())
                .all()
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("knowledge_chunks unavailable (%s) — Moon runs without proprietary KB", e)
        _CACHED = KnowledgeBase(system_block="", sources=[], char_count=0)
        return _CACHED

    parts: list[str] = []
    sources: list[str] = []
    for r in rows:
        text = (r.content or "").strip()
        if not text:
            continue
        sources.append(r.source)
        parts.append(f"### Fonte: {r.source}\n{text}")

    system_block = (
        "[CONHECIMENTO PROPRIETÁRIO HAIRA — material das Doutoras]\n\n"
        + "\n\n---\n\n".join(parts)
    ) if parts else ""

    _CACHED = KnowledgeBase(
        system_block=system_block,
        sources=sources,
        char_count=len(system_block),
    )
    logger.info(
        "Moon KB loaded: %d sources, %d chars (~%d tokens)",
        len(sources), len(system_block), len(system_block) // 4,
    )
    return _CACHED


def reset_kb_cache() -> None:
    """For tests or after re-syncing."""
    global _CACHED
    _CACHED = None
