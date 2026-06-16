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

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_core_session
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


@router.post("/replace-all")
def replace_all_from_iamoon(admin: dict = Depends(require_admin),
                            session: Session = Depends(get_core_session)):
    """Substitui TODO o knowledge base pelo conteúdo da pasta `iamoon/`.

    Definido ANTES de `/{source}` pra evitar conflito de roteamento — caso
    contrário FastAPI matcha `replace-all` em `/{source}` (com GET) e retorna 405.

    Limpa knowledge_chunks e ingere os documentos canônicos do iamoon/:
    - COMPÊNDIO HAIRA (Layer 0)
    - Inteligência Haira by Fernanda Torres (Layer 0.5)
    - Perguntas e Respostas - Daniel (Layer 2)
    - Rotinas e Produtos para Moon (Layer 2)
    - Dica do Dia (Layer 3)
    - Você Sabia (Layer 3)

    Skipa: HAIRA - FAQ (vai pra docs/), Personalidade Moon (em código), duplicatas (1).
    """
    import os
    from pathlib import Path as _P
    folder = _P("iamoon")
    if not folder.exists():
        raise HTTPException(status_code=400, detail="iamoon/ not found on this instance")

    SKIP_PREFIXES = ("HAIRA - FAQ", "Personalidade da Moon")
    SKIP_DUPLICATES = ("(1)",)

    deleted = session.query(KnowledgeChunkORM).delete()
    session.flush()

    upserted = 0
    skipped = []
    files_processed = []
    for fn in sorted(os.listdir(folder)):
        path = folder / fn
        if not path.is_file():
            continue
        if any(fn.startswith(p) for p in SKIP_PREFIXES):
            skipped.append(fn)
            continue
        if any(d in fn for d in SKIP_DUPLICATES):
            skipped.append(fn)
            continue
        if not (fn.endswith(".md") or fn.endswith(".docx") or fn.endswith(".pdf")):
            continue
        try:
            text = extract_text(fn, path=path)
        except Exception as e:
            skipped.append(f"{fn} (extract error: {e})")
            continue
        if not text.strip():
            skipped.append(f"{fn} (empty)")
            continue
        stored = encrypt_content(text)
        session.add(KnowledgeChunkORM(source=fn, content=stored, char_count=len(text)))
        upserted += 1
        files_processed.append({"file": fn, "chars": len(text)})

    session.commit()
    reset_kb_cache()

    return {
        "deleted_old": deleted,
        "upserted": upserted,
        "files_processed": files_processed,
        "skipped": skipped,
        "encrypted": kb_crypto_enabled(),
    }


@router.get("")
def list_chunks(admin: dict = Depends(require_admin),
                session: Session = Depends(get_core_session)):
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
               session: Session = Depends(get_core_session)):
    row = session.get(KnowledgeChunkORM, source)
    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {**_chunk_summary(row), "content": decrypt_content(row.content)}


@router.post("/upload")
async def upload_chunk(request: Request,
                       file: UploadFile = File(...),
                       admin: dict = Depends(require_admin),
                       session: Session = Depends(get_core_session)):
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
        before_chars = row.char_count
        row.content = stored
        row.char_count = len(text)
        action = "updated"
    else:
        before_chars = 0
        row = KnowledgeChunkORM(source=fn, content=stored, char_count=len(text))
        session.add(row)
        action = "created"
    session.commit()
    reset_kb_cache()

    try:
        from src.core.audit import log_admin_action
        log_admin_action(
            actor_id=admin.get("sub", "?"),
            actor_email=admin.get("email"),
            action=f"kb.{action}",
            target_type="knowledge_chunks",
            target_id=fn,
            before={"chars": before_chars},
            after={"chars": len(text), "encrypted": kb_crypto_enabled()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        pass

    return {"action": action, **_chunk_summary(row), "encrypted": kb_crypto_enabled()}


@router.delete("/{source}")
def delete_chunk(source: str,
                 request: Request,
                 admin: dict = Depends(require_admin),
                 session: Session = Depends(get_core_session)):
    row = session.get(KnowledgeChunkORM, source)
    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")
    before_chars = row.char_count
    session.delete(row)
    session.commit()
    reset_kb_cache()
    try:
        from src.core.audit import log_admin_action
        log_admin_action(
            actor_id=admin.get("sub", "?"),
            actor_email=admin.get("email"),
            action="kb.delete",
            target_type="knowledge_chunks",
            target_id=source,
            before={"chars": before_chars},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        pass
    return {"deleted": source}


@router.post("/reingest")
def reingest_from_disk(admin: dict = Depends(require_admin),
                       session: Session = Depends(get_core_session)):
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
