"""Seed/reset the reviewer accounts for Moon validation.

Idempotent: creates each user if missing, otherwise resets the password (and
keeps the row). Shared temporary password — meant for internal validation;
should be rotated afterwards.

Usage:
    python scripts/seed_reviewers.py                 # uses default password
    REVIEWER_PASSWORD=segredo python scripts/seed_reviewers.py
"""
from __future__ import annotations

import os

import bcrypt
from sqlalchemy.orm import Session

from src.storage.database import get_engine
from src.storage.ops_models import UserORM

PASSWORD = os.environ.get("REVIEWER_PASSWORD", "haira2026")

# (email, display name, role)
REVIEWERS = [
    ("clarisse@haira.app", "Clarisse", "reviewer"),
    ("fernanda@haira.app", "Fernanda", "reviewer"),
    ("claudia@haira.app", "Claudia", "reviewer"),
    ("fran@haira.app", "Fran", "reviewer"),
    ("daniel@haira.app", "Daniel", "reviewer"),
]


def main() -> None:
    engine = get_engine()
    with Session(engine) as s:
        for email, name, role in REVIEWERS:
            pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
            user = s.query(UserORM).filter(UserORM.email == email).first()
            if user:
                user.password_hash = pw_hash
                user.name = name
                user.role = role
                user.is_active = True
                action = "reset"
            else:
                s.add(UserORM(email=email, password_hash=pw_hash, name=name, role=role))
                action = "created"
            print(f"{action}: {email} ({name}, {role})")
        s.commit()
    print(f"\nSenha de todos: {PASSWORD}")


if __name__ == "__main__":
    main()
