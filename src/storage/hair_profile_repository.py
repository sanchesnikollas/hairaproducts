# src/storage/hair_profile_repository.py
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.core.hair_profile import HairProfileInput, derive_hair_types
from src.storage.hair_profile_models import HairProfileORM

logger = logging.getLogger("haira.hair_profile")

# Columns mirrored 1:1 from HairProfileInput onto the ORM row.
_SCALAR_FIELDS = (
    "curl_type", "curl_subtype", "color", "volume", "thickness", "length",
    "scalp_oiliness", "dryness_damage", "heat_usage", "extensions",
    "wash_frequency", "sun_exposure", "water_exposure", "scalp_issues",
)
_JSON_FIELDS = ("chemical_treatments", "conditionals", "raw_answers")


class HairProfileRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_by_user(self, user_id: str) -> HairProfileORM | None:
        return (
            self._session.query(HairProfileORM)
            .filter(HairProfileORM.user_id == user_id)
            .first()
        )

    def get(self, profile_id: str) -> HairProfileORM | None:
        return self._session.get(HairProfileORM, profile_id)

    def upsert(self, user_id: str | None, data: HairProfileInput) -> HairProfileORM:
        """Create or update the single profile for a user (one per user)."""
        row = self.get_by_user(user_id) if user_id else None
        if row is None:
            row = HairProfileORM(user_id=user_id)
            self._session.add(row)

        for f in _SCALAR_FIELDS:
            setattr(row, f, getattr(data, f))
        for f in _JSON_FIELDS:
            setattr(row, f, getattr(data, f))
        row.derived_hair_types = derive_hair_types(data)

        self._session.commit()
        self._session.refresh(row)
        return row
