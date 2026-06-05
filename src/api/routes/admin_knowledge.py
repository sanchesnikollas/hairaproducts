"""Admin endpoints for managing the Doutoras knowledge base.

- GET    /api/admin/knowledge                   list chunks (summary)
- GET    /api/admin/knowledge/{source}          read full content
- POST   /api/admin/knowledge/upload            upload .docx/.pdf (multipart)
- DELETE /api/admin/knowledge/{source}          remove a chunk
- POST   /api/admin/knowledge/reingest          re-read data/knowledge_base/ from disk (dev)

All require admin role. Every write invalidates the in-process KB cache so the
next /moon/chat reloads from the DB.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_ops_session
from src.core.document_extraction import extract_text
from src.core.kb_crypto import decrypt_content, encrypt_content, is_enabled as kb_crypto_enabled
from src.core.knowledge_base import reset_kb_cache
from src.storage.knowledge_models import KnowledgeChunkORM

router = APIRouter(prefix="/admin/knowledge", tags=["admin"])


def _chunk_summary(row: KnowledgeChunkORM) -> dict:
    return {
        "source": row.source,
        "char_count": row.char_count,
        "token_estimate": (row.char_count or 0) // 4,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def list_chunks(admin: dict = Depends(require_admin),
                session: Session = Depends(get_ops_session)):
    rows = session.query(KnowledgeChunkORM).order_by(KnowledgeChunkORM.source.asc()).all()
    total_chars = sum(r.char_count or 0 for r in rows)
    return {
        "chunks": [_chunk_summary(r) for r in rows],
        "total_sources": len(rows),
        "total_chars": total_chars,
        "total_tokens_estimate": total_chars // 4,
    }


@router.get("/{source}")
def read_chunk(source: str,
               admin: dict = Depends(require_admin),
               session: Session = Depends(get_ops_session)):
    row = session.get(KnowledgeChunkORM, source)
    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {**_chunk_summary(row), "content": decrypt_content(row.content)}


@router.post("/upload")
async def upload_chunk(file: UploadFile = File(...),
                       admin: dict = Depends(require_admin),
                       session: Session = Depends(get_ops_session)):
    """Receive a .docx or .pdf, extract + upsert by filename, invalidate cache."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    fn = file.filename
    data = await file.read()
    try:
        text = extract_text(fn, data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not text.strip():
        raise HTTPException(status_code=400, detail="Extracted text is empty")

    stored = encrypt_content(text)
    row = session.get(KnowledgeChunkORM, fn)
    if row:
        row.content = stored
        row.char_count = len(text)  # plaintext char count, não o ciphertext
        action = "updated"
    else:
        row = KnowledgeChunkORM(source=fn, content=stored, char_count=len(text))
        session.add(row)
        action = "created"
    session.commit()
    reset_kb_cache()
    return {"action": action, **_chunk_summary(row), "encrypted": kb_crypto_enabled()}


@router.delete("/{source}")
def delete_chunk(source: str,
                 admin: dict = Depends(require_admin),
                 session: Session = Depends(get_ops_session)):
    row = session.get(KnowledgeChunkORM, source)
    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")
    session.delete(row)
    session.commit()
    reset_kb_cache()
    return {"deleted": source}


@router.post("/reingest")
def reingest_from_disk(admin: dict = Depends(require_admin),
                       session: Session = Depends(get_ops_session)):
    """Re-read every file in data/knowledge_base/ and upsert. Dev convenience —
    in prod the source folder is empty; use /upload instead."""
    import os
    from pathlib import Path as _P
    folder = _P("data/knowledge_base")
    if not folder.exists():
        raise HTTPException(status_code=400, detail="data/knowledge_base/ not found on this instance")
    SKIP = {"Haira - regras 2.pdf"}
    upserted = 0
    for fn in sorted(os.listdir(folder)):
        if fn in SKIP:
            continue
        path = folder / fn
        if not path.is_file() or not (fn.endswith(".docx") or fn.endswith(".pdf")):
            continue
        text = extract_text(fn, path=path)
        if not text.strip():
            continue
        stored = encrypt_content(text)
        row = session.get(KnowledgeChunkORM, fn)
        if row:
            row.content = stored
            row.char_count = len(text)
        else:
            session.add(KnowledgeChunkORM(source=fn, content=stored, char_count=len(text)))
        upserted += 1
    session.commit()
    reset_kb_cache()
    return {"upserted": upserted, "encrypted": kb_crypto_enabled()}
