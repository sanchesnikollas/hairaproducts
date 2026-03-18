"""Seed the first admin user. Run once after migration."""
from __future__ import annotations
import bcrypt
from sqlalchemy.orm import Session
from src.storage.database import get_engine
from src.storage.ops_models import UserORM

engine = get_engine()
pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()

with Session(engine) as s:
    existing = s.query(UserORM).filter(UserORM.email == "admin@haira.com").first()
    if existing:
        print(f"Admin already exists: {existing.user_id}")
    else:
        user = UserORM(email="admin@haira.com", password_hash=pw, name="Admin", role="admin")
        s.add(user)
        s.commit()
        print(f"Admin created: {user.user_id}")
