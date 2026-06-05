"""Loader/cache for Moon personality config (DB-backed).

Mesmo padrão do `src/core/knowledge_base.py`: lazy load do DB no primeiro chat,
cache em memória do processo, reset hook chamado quando o admin edita via UI.

Fallback ao defaults de `moon_personality.py` quando uma chave não existe na
DB (ex.: prod nova antes da migration seedar, ou se alguém deletar uma row).
"""

from __future__ import annotations

import logging
from threading import Lock

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.moon_personality import default_config
from src.storage.database import get_engine

logger = logging.getLogger("haira.moon_config")

_CACHED: dict[str, str] | None = None
_LOCK = Lock()


def load_moon_config() -> dict[str, str]:
    """Return {key: value} dict, merging DB overrides on top of defaults.

    Cached at process scope. First call hits the DB once; subsequent calls
    return the cached dict until `reset_moon_config_cache()` runs.
    """
    global _CACHED
    with _LOCK:
        if _CACHED is not None:
            return _CACHED

        defaults = default_config()
        try:
            from src.storage.moon_models import MoonConfigORM
            engine = get_engine()
            with Session(engine) as session:
                rows = session.query(MoonConfigORM.key, MoonConfigORM.value).all()
                overrides = {k: v for k, v in rows if v}
                merged = {**defaults, **overrides}
                _CACHED = merged
                logger.info(
                    "moon_config loaded: %d defaults, %d DB overrides",
                    len(defaults),
                    len(overrides),
                )
                return merged
        except SQLAlchemyError as exc:
            logger.warning("moon_config DB unreachable, falling back: %s", exc)
            return defaults
        except Exception as exc:  # tabela ainda não migrada, etc
            logger.warning("moon_config fallback to defaults: %s", exc)
            return defaults


def reset_moon_config_cache() -> None:
    """Drop the cached config. Next `load_moon_config()` will re-read DB."""
    global _CACHED
    with _LOCK:
        _CACHED = None
        logger.info("moon_config cache invalidated")
