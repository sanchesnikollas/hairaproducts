"""Alembic env pra haira_audit DB.

Lê `AUDIT_DATABASE_URL` (fallback: `CORE_DATABASE_URL` → `CENTRAL_DATABASE_URL`
→ `DATABASE_URL`). Esse fallback chain garante que durante a transição,
mesmo sem provisionar Postgres-Audit, as migrations rodam no DB atual.
"""
from logging.config import fileConfig
import os
import pathlib
import sys

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from src.storage.audit_models import AuditBase  # noqa: E402

config = context.config

# Fallback chain: audit → core → central (legacy) → catalog (legacy default).
db_url = (
    os.environ.get("AUDIT_DATABASE_URL")
    or os.environ.get("CORE_DATABASE_URL")
    or os.environ.get("CENTRAL_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
)
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = AuditBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
