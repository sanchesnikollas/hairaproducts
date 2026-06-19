"""Regression guard for the core fix: approving a quarantined product must pass
the Gold gate — no more blind flip to verified_inci. This protects the behaviour
the client specifically complained about ("aprovar virava o status sem corrigir
o dado")."""
import os
import tempfile

import pytest
from fastapi import HTTPException

GOOD_INCI = ["Aqua", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine", "Glycerin", "Parfum", "Citric Acid"]
DESC = "Shampoo de limpeza suave com glicerina e betaína para uso diário em cabelos normais a oleosos."
USAGE = "Aplique no cabelo úmido, massageie suavemente e enxágue bem."


@pytest.fixture()
def session_factory():
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.NamedTemporaryFile(suffix='.db', delete=False).name}"
    from src.storage import database as dbmod
    dbmod.reset_engine()
    from src.storage.orm_models import Base, IngredientORM
    from sqlalchemy.orm import Session as SASession
    engine = dbmod.get_engine()
    Base.metadata.create_all(engine)
    with SASession(engine) as s:
        for n in GOOD_INCI:
            s.add(IngredientORM(canonical_name=n))
        s.commit()
    return engine, SASession


def _quarantined(SASession, engine, **overrides):
    from src.storage.orm_models import ProductORM, QuarantineDetailORM
    base = dict(
        brand_slug="acme", product_name="Shampoo Hidratante 300ml",
        verification_status="quarantined", image_url_main="https://a.com/i.jpg",
        inci_ingredients=list(GOOD_INCI), description=DESC, usage_instructions=USAGE,
        product_category="shampoo", extraction_method="html_selector",
        hair_relevance_reason="hair_keyword:shampoo",
    )
    base.update(overrides)
    with SASession(engine) as s:
        p = ProductORM(product_url=f"u/{overrides.get('product_url_id', 'x')}",
                       **{k: v for k, v in base.items() if k != "product_url_id"})
        s.add(p)
        s.flush()
        qd = QuarantineDetailORM(product_id=p.id, rejection_reason="x", rejection_code="x")
        s.add(qd)
        s.commit()
        return qd.id, p.id


def test_approve_complete_product_becomes_gold(session_factory):
    from src.api.routes.quarantine import approve_quarantined
    engine, SASession = session_factory
    qid, _ = _quarantined(SASession, engine, product_url_id="a")
    with SASession(engine) as s:
        r = approve_quarantined(qid, "ok", s)
    assert r["verification_status"] == "verified_inci"
    assert r["gold_status"] == "gold"


def test_approve_non_hair_is_refused_422(session_factory):
    from src.api.routes.quarantine import approve_quarantined
    from src.storage.orm_models import ProductORM
    engine, SASession = session_factory
    qid, pid = _quarantined(SASession, engine, product_url_id="b",
                            product_name="Difusor de Ambiente",
                            hair_relevance_reason="non_hair:difusor")
    with SASession(engine) as s:
        with pytest.raises(HTTPException) as ei:
            approve_quarantined(qid, "", s)
    assert ei.value.status_code == 422
    assert ei.value.detail["code"] == "NOT_APPROVABLE"
    # stayed quarantined (rollback) — not rubber-stamped
    with SASession(engine) as s:
        assert s.query(ProductORM).filter_by(id=pid).one().verification_status == "quarantined"


def test_approve_incomplete_unquarantines_to_catalog_not_gold(session_factory):
    from src.api.routes.quarantine import approve_quarantined
    engine, SASession = session_factory
    # real product but no image -> approve un-quarantines, honest status, NOT gold
    qid, _ = _quarantined(SASession, engine, product_url_id="c", image_url_main=None)
    with SASession(engine) as s:
        r = approve_quarantined(qid, "", s)
    assert r["gold_status"] == "catalog"
    assert any(b["code"] == "image_missing" for b in r["gold_blockers"])
