"""Admin endpoints for Moon personality config.

Read/write `moon_config` table. Every successful write resets the in-process
cache (`reset_moon_config_cache`) so the next `/api/moon/chat` reflects the
edit without a redeploy.

All endpoints require `require_admin`. Audit trail via `updated_by` FK and
`updated_at` timestamp.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.auth import require_admin
from src.api.dependencies import get_core_session
from src.core.moon_config import reset_moon_config_cache
from src.core.moon_personality import CONFIG_DESCRIPTIONS, default_config
from src.storage.moon_models import MoonConfigORM

logger = logging.getLogger("haira.admin_moon")

router = APIRouter(prefix="/admin/moon", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MoonConfigItem(BaseModel):
    key: str
    value: str
    description: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None
    char_count: int
    token_estimate: int


class UpdateMoonConfigBody(BaseModel):
    value: str = Field(..., min_length=1, max_length=50_000)


class MoonConfigListResponse(BaseModel):
    config: list[MoonConfigItem]
    total_keys: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize(row: MoonConfigORM | None, *, key: str, value: str, description: str | None) -> MoonConfigItem:
    """Build a MoonConfigItem from either a real ORM row or a fallback default."""
    return MoonConfigItem(
        key=key,
        value=value,
        description=description,
        updated_at=row.updated_at.isoformat() if (row and row.updated_at) else None,
        updated_by=row.updated_by if row else None,
        char_count=len(value),
        token_estimate=len(value) // 4,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/config", response_model=MoonConfigListResponse)
def list_config(
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_core_session),
) -> MoonConfigListResponse:
    """Return every config key — merged DB overrides + defaults fallback."""
    rows = {r.key: r for r in session.query(MoonConfigORM).all()}
    defaults = default_config()

    items: list[MoonConfigItem] = []
    for key, default_value in defaults.items():
        row = rows.get(key)
        items.append(_serialize(
            row,
            key=key,
            value=row.value if row else default_value,
            description=CONFIG_DESCRIPTIONS.get(key),
        ))
    # Inclui chaves extras (caso alguém adicione algo via banco direto)
    for key, row in rows.items():
        if key not in defaults:
            items.append(_serialize(
                row,
                key=key,
                value=row.value,
                description=CONFIG_DESCRIPTIONS.get(key),
            ))
    return MoonConfigListResponse(config=items, total_keys=len(items))


@router.get("/config/{key}", response_model=MoonConfigItem)
def get_config_key(
    key: str,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_core_session),
) -> MoonConfigItem:
    row = session.query(MoonConfigORM).filter(MoonConfigORM.key == key).first()
    defaults = default_config()
    if not row and key not in defaults:
        raise HTTPException(status_code=404, detail=f"Config key not found: {key}")
    return _serialize(
        row,
        key=key,
        value=row.value if row else defaults[key],
        description=CONFIG_DESCRIPTIONS.get(key),
    )


@router.put("/config/{key}", response_model=MoonConfigItem)
def update_config_key(
    key: str,
    body: UpdateMoonConfigBody,
    request: Request,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_core_session),
) -> MoonConfigItem:
    """Upsert. Rejeita chaves desconhecidas (segurança contra typos)."""
    defaults = default_config()
    if key not in defaults:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown config key: {key}. Allowed: {sorted(defaults.keys())}",
        )

    row = session.query(MoonConfigORM).filter(MoonConfigORM.key == key).first()
    before_value = row.value if row else defaults[key]
    if row is None:
        row = MoonConfigORM(
            key=key,
            value=body.value,
            description=CONFIG_DESCRIPTIONS.get(key),
            updated_by=admin.get("sub"),
        )
        session.add(row)
    else:
        row.value = body.value
        row.updated_by = admin.get("sub")
        row.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(row)

    reset_moon_config_cache()

    # Audit trail — só persiste o tamanho antes/depois pra não duplicar
    # texto integral em audit (já está em moon_config).
    try:
        from src.core.audit import log_admin_action
        log_admin_action(
            actor_id=admin.get("sub", "?"),
            actor_email=admin.get("email"),
            action="moon_config.update",
            target_type="moon_config",
            target_id=key,
            before={"len": len(before_value)},
            after={"len": len(body.value)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:  # noqa: BLE001
        pass
    logger.info(
        "moon_config[%s] updated by %s (%d chars)",
        key,
        admin.get("email", admin.get("sub", "?")),
        len(body.value),
    )
    return _serialize(row, key=key, value=row.value, description=CONFIG_DESCRIPTIONS.get(key))


@router.post("/config/{key}/reset", response_model=MoonConfigItem)
def reset_config_key(
    key: str,
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_core_session),
) -> MoonConfigItem:
    """Volta uma chave para o default do código (deleta override do DB)."""
    defaults = default_config()
    if key not in defaults:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")

    row = session.query(MoonConfigORM).filter(MoonConfigORM.key == key).first()
    if row is not None:
        session.delete(row)
        session.commit()

    reset_moon_config_cache()
    logger.info(
        "moon_config[%s] reset to default by %s",
        key,
        admin.get("email", admin.get("sub", "?")),
    )
    return _serialize(
        None,
        key=key,
        value=defaults[key],
        description=CONFIG_DESCRIPTIONS.get(key),
    )


@router.post("/config/reset-all", response_model=MoonConfigListResponse)
def reset_all_config(
    admin: dict = Depends(require_admin),
    session: Session = Depends(get_core_session),
) -> MoonConfigListResponse:
    """Apaga todos os overrides — Moon volta a usar 100% defaults do código."""
    session.query(MoonConfigORM).delete()
    session.commit()
    reset_moon_config_cache()
    logger.info("moon_config FULL RESET by %s", admin.get("email", "?"))
    return list_config(admin=admin, session=session)
