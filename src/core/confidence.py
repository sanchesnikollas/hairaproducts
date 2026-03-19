from __future__ import annotations

CRITICAL_FIELDS = ["product_name", "product_category", "brand_slug", "description", "inci_ingredients", "image_url_main"]
WEIGHT_COMPLETUDE = 0.40
WEIGHT_PARSING = 0.35
WEIGHT_VALIDACAO = 0.25

EDITORIAL_SCORES = {
    "pendente": 0.0,
    "em_revisao": 0.5,
    "aprovado": 1.0,
    "corrigido": 1.0,
    "rejeitado": 0.0,
}


def calculate_confidence(
    fields: dict[str, object],
    validated_ingredient_count: int,
    total_ingredient_count: int,
    status_editorial: str | None,
) -> tuple[float, dict[str, float]]:
    """Calculate confidence score (0-100) and return (score, factors)."""
    filled = sum(1 for f in CRITICAL_FIELDS if fields.get(f))
    completude = filled / len(CRITICAL_FIELDS)

    if not fields.get("inci_ingredients") or total_ingredient_count == 0:
        parsing = 0.0
    else:
        parsing = validated_ingredient_count / total_ingredient_count

    validacao = EDITORIAL_SCORES.get(status_editorial or "pendente", 0.0)

    score = (completude * WEIGHT_COMPLETUDE + parsing * WEIGHT_PARSING + validacao * WEIGHT_VALIDACAO) * 100
    factors = {"completude": completude, "parsing": parsing, "validacao_humana": validacao}
    return round(score, 2), factors
