from __future__ import annotations

from pydantic import BaseModel, Field


class InterpretationData(BaseModel):
    formula_classification: str | None = None
    key_actives: list[str] = Field(default_factory=list)
    formula_base: str | None = None
    silicone_presence: bool | None = None
    sulfate_presence: bool | None = None
    protein_presence: bool | None = None
    hydration_nutrition_balance: str | None = None
    treatment_intensity: str | None = None  # leve | medio | intenso


class ApplicationData(BaseModel):
    when_to_use: str | None = None
    when_to_avoid: str | None = None
    ideal_frequency: str | None = None
    ideal_hair_types: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)


class DecisionData(BaseModel):
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    ready_for_publication: bool = False
    requires_human_review: bool = True
    review_reason: str | None = None
    confidence_score: float | None = None  # Moon's assessment (Phase 2), distinct from ProductORM.confidence
    uncertainty_flags: list[str] = Field(default_factory=list)
