# src/storage/database.py
from __future__ import annotations

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "sqlite:///haira.db")
        # Railway/Heroku use postgres:// but SQLAlchemy needs postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        kwargs: dict = {"echo": os.environ.get("SQL_ECHO", "").lower() == "true"}
        if url.startswith("postgresql"):
            kwargs["pool_size"] = 5
            kwargs["pool_pre_ping"] = True
        _engine = create_engine(url, **kwargs)
    return _engine


def get_session() -> Session:
    factory = sessionmaker(bind=get_engine())
    return factory()


def reset_engine() -> None:
    global _engine
    _engine = None
