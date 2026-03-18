from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from src.api.dependencies import get_ops_session

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "haira-ops-dev-secret-change-in-prod")
ALGORITHM = "HS256"
DEFAULT_EXPIRE_MINUTES = 1440  # 24h


def create_access_token(user_id: str, role: str, expires_minutes: int = DEFAULT_EXPIRE_MINUTES) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None


def _extract_token_payload(request: Request) -> dict[str, Any]:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth_header[7:]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def get_current_user(
    request: Request,
    session: Session = Depends(get_ops_session),
) -> dict[str, Any]:
    """FastAPI dependency: extracts JWT and verifies user is still active in DB."""
    payload = _extract_token_payload(request)
    from src.storage.ops_models import UserORM
    user = session.query(UserORM).filter(UserORM.user_id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account deactivated")
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: requires admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
