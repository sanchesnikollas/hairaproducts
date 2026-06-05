from __future__ import annotations
from datetime import datetime, timezone
import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.api.auth import create_access_token, get_current_user, require_admin
from src.api.dependencies import get_ops_session
from src.storage.ops_models import UserORM

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str
    role: Literal["admin", "reviewer"] = "reviewer"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: Literal["admin", "reviewer"] | None = None
    is_active: bool | None = None


@router.post("/login")
def login(body: LoginRequest, session: Session = Depends(get_ops_session)):
    user = session.query(UserORM).filter(UserORM.email == body.email, UserORM.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        password_ok = bcrypt.checkpw(body.password.encode(), user.password_hash.encode())
    except (ValueError, TypeError):
        password_ok = False
    if not password_ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc)
    session.commit()
    token = create_access_token(user_id=user.user_id, role=user.role)
    return {
        "token": token,
        "user": {"id": user.user_id, "name": user.name, "email": user.email, "role": user.role},
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user), session: Session = Depends(get_ops_session)):
    db_user = session.query(UserORM).filter(UserORM.user_id == user["sub"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": db_user.user_id, "name": db_user.name, "email": db_user.email, "role": db_user.role}


@router.post("/users", status_code=201)
def create_user(body: CreateUserRequest, admin: dict = Depends(require_admin), session: Session = Depends(get_ops_session)):
    existing = session.query(UserORM).filter(UserORM.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = UserORM(email=body.email, password_hash=pw_hash, name=body.name, role=body.role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"id": user.user_id, "name": user.name, "email": user.email, "role": user.role}


@router.get("/users")
def list_users(admin: dict = Depends(require_admin), session: Session = Depends(get_ops_session)):
    users = session.query(UserORM).order_by(UserORM.created_at).all()
    return [
        {"id": u.user_id, "name": u.name, "email": u.email, "role": u.role, "is_active": u.is_active}
        for u in users
    ]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user), session: Session = Depends(get_ops_session)):
    db_user = session.query(UserORM).filter(UserORM.user_id == user["sub"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not bcrypt.checkpw(body.current_password.encode(), db_user.password_hash.encode()):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    db_user.password_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    session.commit()
    return {"status": "ok"}


class ResetAdminRequest(BaseModel):
    email: str
    new_password: str
    reset_key: str


@router.post("/reset-admin")
def reset_admin_password(body: ResetAdminRequest, session: Session = Depends(get_ops_session)):
    """Emergency admin password reset. Requires ADMIN_RESET_KEY env var."""
    import os
    expected_key = os.getenv("ADMIN_RESET_KEY")
    if not expected_key:
        raise HTTPException(status_code=404, detail="Not found")
    if body.reset_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid reset key")
    user = session.query(UserORM).filter(UserORM.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    session.commit()
    return {"status": "ok", "message": f"Password reset for {body.email}"}


@router.post("/logout")
def logout(user: dict = Depends(get_current_user)):
    # JWT is stateless — logout is handled client-side by removing the token.
    # This endpoint exists for API completeness and future token blacklisting.
    return {"status": "ok"}


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UpdateUserRequest, admin: dict = Depends(require_admin), session: Session = Depends(get_ops_session)):
    user = session.query(UserORM).filter(UserORM.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    session.commit()
    return {"id": user.user_id, "name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active}
