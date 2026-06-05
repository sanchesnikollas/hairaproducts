from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.core.hair_profile import (
    HairProfileInput, derive_hair_types, profile_summary, KNOWN_HAIR_TYPE_SLUGS,
)
from src.storage.orm_models import Base
from src.storage.hair_profile_models import HairProfileORM  # noqa: F401 (register table)
from src.storage.ops_models import UserORM  # noqa: F401 (FK target)
from src.storage.hair_profile_repository import HairProfileRepository


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


class TestDerivation:
    def test_subtype_takes_precedence_over_curl_type(self):
        # 3B subtype -> cacheado, even if curl_type says something else
        p = HairProfileInput(curl_type="liso", curl_subtype="3B")
        assert "cacheado" in derive_hair_types(p)
        assert "liso" not in derive_hair_types(p)

    def test_ondulado_is_a_documented_gap(self):
        # "2x" / "ondulado" has no engine slug -> no curvature slug emitted
        p = HairProfileInput(curl_type="ondulado", curl_subtype="2B")
        assert not ({"liso", "cacheado", "crespo"} & set(derive_hair_types(p)))

    def test_oily_scalp_and_dryness(self):
        p = HairProfileInput(scalp_oiliness="alta", dryness_damage="bastante")
        slugs = derive_hair_types(p)
        assert "oleoso" in slugs and "seco" in slugs and "danificado" in slugs

    def test_bleaching_adds_damage_chain(self):
        p = HairProfileInput(chemical_treatments=["descoloracao"])
        slugs = derive_hair_types(p)
        for expected in ("com_quimica", "tingido", "danificado", "sensibilizado"):
            assert expected in slugs

    def test_only_known_slugs_returned(self):
        p = HairProfileInput(curl_type="crespo", thickness="finos",
                             scalp_oiliness="alta", chemical_treatments=["alisamento"],
                             heat_usage="diariamente", sun_exposure="alta")
        assert set(derive_hair_types(p)).issubset(KNOWN_HAIR_TYPE_SLUGS)

    def test_no_duplicate_slugs(self):
        # descoloracao + bastante dryness both push "danificado" — must dedupe
        p = HairProfileInput(chemical_treatments=["descoloracao"], dryness_damage="bastante")
        slugs = derive_hair_types(p)
        assert len(slugs) == len(set(slugs))

    def test_empty_profile_yields_no_slugs(self):
        assert derive_hair_types(HairProfileInput()) == []

    def test_summary_mentions_subtype_and_chemistry(self):
        p = HairProfileInput(curl_type="ondulado", curl_subtype="2B",
                             thickness="finos", chemical_treatments=["coloracao"])
        s = profile_summary(p)
        assert "ondulado 2B" in s and "coloração" in s and "finos" in s


class TestRepository:
    def test_upsert_creates_then_updates(self):
        engine = make_engine()
        with Session(engine) as s:
            repo = HairProfileRepository(s)
            row = repo.upsert("user-1", HairProfileInput(curl_type="cacheado", curl_subtype="3A"))
            assert row.profile_id is not None
            assert row.derived_hair_types == ["cacheado"]

            # Second upsert for same user updates the same row (one per user)
            row2 = repo.upsert("user-1", HairProfileInput(curl_type="crespo", curl_subtype="4B",
                                                          scalp_oiliness="alta"))
            assert row2.profile_id == row.profile_id
            assert "crespo" in row2.derived_hair_types and "oleoso" in row2.derived_hair_types
            assert s.query(HairProfileORM).count() == 1

    def test_get_by_user_missing(self):
        engine = make_engine()
        with Session(engine) as s:
            assert HairProfileRepository(s).get_by_user("nobody") is None
