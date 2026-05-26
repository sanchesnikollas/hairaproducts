"""Moon AI — camada consultiva opcional sobre o score rule-based.

Diferente de `LLMClient.extract_structured` (anti-inferência, pra extração de dados),
aqui o modelo atua como **analista de cosmetologia capilar**: dada a lista INCI de um
produto + o perfil capilar + o score determinístico já calculado, produz uma análise
personalizada. Pode inferir sinergias/interações conhecidas, mas NUNCA inventa
ingredientes ausentes da lista.

Degrada graciosamente: retorna `None` se não houver `ANTHROPIC_API_KEY` ou em qualquer
erro — o caller mantém o resultado rule-based.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("haira.moon_ai")

_SYSTEM = (
    "Você é uma analista de cosmetologia capilar especializada em INCI. "
    "Dada a lista de ingredientes de um produto, o perfil capilar do usuário e um "
    "score determinístico já calculado, produza uma análise personalizada em português "
    "do Brasil. Baseie-se SOMENTE nos ingredientes fornecidos — pode inferir sinergias e "
    "interações conhecidas entre eles, mas nunca invente ingredientes que não estão na "
    "lista. Seja concreta e útil. Responda APENAS com JSON válido."
)


def analyze_compatibility_ai(
    *,
    product_ctx: dict,
    hair_types: list[str],
    rule_result: dict,
    max_tokens: int = 1200,
) -> dict | None:
    """Retorna {summary, synergies[], personalized_alerts[], recommendation} ou None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.info("moon_ai: sem ANTHROPIC_API_KEY — pulando IA")
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("moon_ai: anthropic não instalado")
        return None

    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
    inci = product_ctx.get("inci") or []
    alerts = [a.get("name") for a in rule_result.get("alerts", [])][:6]
    benefits = [b.get("name") for b in rule_result.get("benefits", [])][:6]

    prompt = f"""Perfil capilar do usuário: {", ".join(hair_types)}

Produto: {product_ctx.get('name') or '(sem nome)'} — {product_ctx.get('product_type') or ''}
Descrição: {(product_ctx.get('description') or '')[:800]}
Lista INCI ({len(inci)} ingredientes): {", ".join(inci[:40])}

Score determinístico já calculado (rule-based): {rule_result.get('overall_score')} \
({rule_result.get('interpretation')})
Ingredientes que o sistema marcou como alerta: {alerts}
Ingredientes que o sistema marcou como benefício: {benefits}

Produza um JSON com EXATAMENTE estas chaves:
- "summary": string — 1 a 2 frases sobre a compatibilidade deste produto com o perfil
- "synergies": array de strings — interações/sinergias relevantes entre os ingredientes
- "personalized_alerts": array de strings — riscos específicos pro perfil, explicando o porquê
- "recommendation": string — 1 frase de recomendação prática (usar/evitar/como usar)"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        out = resp.content[0].text
        parsed = _parse_json(out)
        if parsed is not None:
            parsed["_model"] = model
        return parsed
    except Exception as e:  # noqa: BLE001
        logger.warning("moon_ai: chamada falhou: %s", e)
        return None


def _parse_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for fence in ("```json", "```"):
            if fence in text:
                start = text.index(fence) + len(fence)
                try:
                    end = text.index("```", start)
                    return json.loads(text[start:end])
                except (ValueError, json.JSONDecodeError):
                    continue
    logger.warning("moon_ai: resposta não era JSON válido")
    return None
