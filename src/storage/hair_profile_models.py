"""Hair profile — the client questionnaire that feeds Moon.

Mirrors the "Plano Cliente" capture flow in Figma (2.3.1 Profile_EditHair +
2.3.2 DiscoverType). Core dimensions are typed columns so the derivation layer
(profile -> ingredient_category_compatibility hair_type slugs) and any future
filtering can query them directly; conditional/branching answers and the full
raw payload live in JSON for forward-compat.

One active profile per user (user_id unique).
"""
from __future__ import annotations

from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey

from src.storage.orm_models import Base, _uuid, _utcnow


class HairProfileORM(Base):
    __tablename__ = "hair_profiles"

    profile_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id"), unique=True, nullable=True, index=True)

    # Q1 — curvatura. liso | ondulado | cacheado | crespo | transicao
    curl_type = Column(String(20), nullable=True)
    # Q1b — subtipo específico (DiscoverType): 1A..4C | nao_sei
    curl_subtype = Column(String(6), nullable=True)
    # Q2 — cor atual. preto | castanho | loiro | ruivo | grisalhos | outras
    color = Column(String(20), nullable=True)
    # Q3 — volume. pouco | medio | muito
    volume = Column(String(10), nullable=True)
    # Q4 — espessura do fio. finos | medios | grossos
    thickness = Column(String(10), nullable=True)
    # Q5 — comprimento. muito_curto | curto | longo
    length = Column(String(12), nullable=True)
    # Q6 — oleosidade do couro. baixa | normal | alta
    scalp_oiliness = Column(String(10), nullable=True)
    # Q7 — ressecamento/dano/frizz. nao | um_pouco | bastante
    dryness_damage = Column(String(10), nullable=True)
    # Q8 — natural ou química (multi). lista de: coloracao | descoloracao | alisamento
    #      vazio/None => natural
    chemical_treatments = Column(JSON, nullable=True)
    # Q9 — uso de calor. nunca | as_vezes | diariamente | 1x_mes | 1_2_semana | 3_4_semana
    heat_usage = Column(String(12), nullable=True)
    # Q10 — alongamento/mega hair. none | tic_tac | locks | fixo
    extensions = Column(String(10), nullable=True)
    # Q11 — frequência de lavagem. diaria | semanal_ou_menos | 2_3_semana | 4_5_semana
    wash_frequency = Column(String(20), nullable=True)
    # Q12 — exposição ao sol. baixa | moderada | alta
    sun_exposure = Column(String(10), nullable=True)
    # Q13 — exposição mar/piscina. nunca | ocasional | frequente
    water_exposure = Column(String(12), nullable=True)
    # Q14 — saúde do couro (queda, caspa, coceira, dor...). True = apresenta sintomas
    scalp_issues = Column(Boolean, nullable=True)

    # Conditionals (quando há química): coloration_type, who_applies,
    # coloration_freq, bleaching_freq, straightening_routine
    conditionals = Column(JSON, nullable=True)
    # Dump completo das respostas como vieram do app (forward-compat)
    raw_answers = Column(JSON, nullable=True)
    # Cache dos slugs derivados para o motor de compatibilidade
    derived_hair_types = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
