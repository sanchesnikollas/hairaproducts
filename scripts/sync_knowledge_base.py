#!/usr/bin/env python3
"""Push the local Doutoras KB (knowledge_chunks table) to prod via the admin endpoint.

The content stays out of git; this is how it gets to Railway.

Usage:
    MIGRATION_SECRET=... python scripts/sync_knowledge_base.py
    MIGRATION_SECRET=... RAILWAY_URL=... python scripts/sync_knowledge_base.py
"""
from __future__ import annotations

import os
import sys

import httpx

from src.storage.database import get_engine
from src.storage.knowledge_models import KnowledgeChunkORM


BASE = os.environ.get("RAILWAY_URL", "https://haira-app-production-deb8.up.railway.app")
SECRET = os.environ.get("MIGRATION_SECRET", "")


def main() -> None:
    if not SECRET:
        print("Set MIGRATION_SECRET")
        sys.exit(1)

    from sqlalchemy.orm import Session
    with Session(get_engine()) as s:
        rows = s.query(KnowledgeChunkORM).all()
        chunks = [{"source": r.source, "content": r.content} for r in rows]
    if not chunks:
        print("No local chunks to sync. Run scripts/ingest_knowledge.py first.")
        sys.exit(1)

    total_chars = sum(len(c["content"]) for c in chunks)
    print(f"Syncing {len(chunks)} chunks ({total_chars} chars) → {BASE}")
    resp = httpx.post(
        f"{BASE}/api/admin/sync-knowledge-base",
        json={"secret": SECRET, "chunks": chunks, "replace": True},
        timeout=120,
    )
    print(f"HTTP {resp.status_code} · {resp.json()}")


if __name__ == "__main__":
    main()
