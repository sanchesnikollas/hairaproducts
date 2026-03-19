#!/usr/bin/env python3
"""Run Alembic migrations for all active brand databases registered in the central DB."""
from __future__ import annotations

import logging
import os
import sys
import pathlib

# Ensure project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic.config import Config
from alembic import command as alembic_command

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get_central_url() -> str:
    url = os.environ.get("CENTRAL_DATABASE_URL", "sqlite:///haira_central.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _get_brand_alembic_config(database_url: str) -> Config:
    """Return an Alembic Config pointed at the standard brand migrations and the given URL."""
    cfg = Config("alembic.ini")
    # Normalise postgres:// -> postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def run() -> None:
    central_url = _get_central_url()
    logger.info("Connecting to central DB: %s", central_url)

    engine = create_engine(central_url)

    # Import here so the project src is already on sys.path
    from src.storage.central_models import BrandDatabaseORM  # noqa: PLC0415

    success_count = 0
    failure_count = 0

    with Session(engine) as session:
        brands = (
            session.query(BrandDatabaseORM)
            .filter(BrandDatabaseORM.is_active == True)  # noqa: E712
            .all()
        )

        if not brands:
            logger.info("No active brands found in central DB. Nothing to migrate.")
            return

        logger.info("Found %d active brand(s) to migrate.", len(brands))

        for brand in brands:
            logger.info(
                "[%s] Running migrations against: %s",
                brand.brand_slug,
                brand.database_url,
            )
            try:
                cfg = _get_brand_alembic_config(brand.database_url)
                alembic_command.upgrade(cfg, "head")
                logger.info("[%s] Migrations succeeded.", brand.brand_slug)
                success_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[%s] Migration FAILED: %s. Marking brand inactive.",
                    brand.brand_slug,
                    exc,
                )
                brand.is_active = False
                session.add(brand)
                failure_count += 1

        session.commit()

    logger.info(
        "Migration summary: %d succeeded, %d failed.",
        success_count,
        failure_count,
    )

    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
