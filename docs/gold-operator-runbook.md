# Runbook — Workflow Gold (operação)

Guia prático do que foi entregue e como operar. Para o racional/design, ver
[workflow-gold-redesign.md](workflow-gold-redesign.md).

---

## 1. Os tiers (`products.gold_status`)

O único eixo que a IA (Moon) consome. Calculado por `src/core/gold_gate.evaluate_gold`,
nunca por flip manual.

| tier | significado |
|---|---|
| `gold` | INCI verídico + foto + como usar + descrição + categoria. **Único que a IA usa.** |
| `gold_candidate` | completo, mas um sinal de confiança precisa de revisão humana (INCI só-LLM, baixa taxa de ingrediente reconhecido) |
| `catalog` | produto capilar real, mas falta/falha um campo exigido |
| `raw` | não avaliado, OU desqualificado (não-capilar / nome inválido / kit / WAF) |
| `gold_rejected` | humano revisou e reprovou — nunca é sobrescrito pelo recompute |

## 2. Deploy / migrations (já no ar)

`entrypoint.sh` roda `alembic upgrade head` no boot do Railway → as colunas
`gold_*` e `ean` já existem em produção. Confirmado: `/api/products` 200,
`/api/moon/analyze` retorna `allergens`, `/api/moon/identify` 401 (rota viva).

## 3. Baseline (rodar 1x em produção — PRÓXIMO PASSO)

```bash
railway run haira backfill-usage --all-brands   # recupera 'como usar' já extraído
railway run haira gold-report --all-brands       # popula gold_status + mostra o gap
```

`gold-report` imprime, por marca: % Gold, **gap por campo** (quantos produtos
faltam cada campo) e "closest to Gold" (a 1 campo de virar Gold). É isso que
prioriza o enriquecimento.

## 4. Loop de enriquecimento por marca (subir cobertura Gold)

Ordem barato→caro; rode por marca priorizada (`brands.json` priority, depois
maior catálogo). Mede com `gold-report` no começo e no fim.

```bash
haira gold-report --brand <slug>          # baseline da marca
haira backfill-usage --brand <slug>
haira scrape --brand <slug>               # re-extração (já grava usage + splitter + WAF→quarentena)
haira audit-inci --brand <slug>           # diagnostica falhas de INCI
haira source-scrape --source belezanaweb --brand <slug>
haira enrich-external --brand <slug>      # INCI externo: EAN exato / nome+volume (auto >0.90, fila 0.75–0.90)
haira enrich --brand <slug>               # LLM-grounded p/ o resto (budget-capped)
haira classify --brand <slug> --with-validation   # hair_type/function (Gold+)
haira labels --brand <slug>
haira gold-report --brand <slug>          # mede o delta; o gap diz qual fila Ops trabalhar
```

No Ops, filtre `gap=nao_gold` e use o painel **Gold** no detalhe (checklist de
blockers) para fechar os produtos "closest to Gold". Aprovar na quarentena agora
**exige** o gate (422 com blockers se reprovar).

## 5. Marcas que extraíram nada (recon manual)

| marca | causa | ação |
|---|---|---|
| Mustela | INCI em accordion, `requires_js=false` | ligar `requires_js: true` + recon |
| Keune | Cloudflare WAF (agora vira quarentena `waf_challenge`, visível) | recon httpx |
| Keragen / Lacan | blueprint auto-gerado nunca revisado | recon + ajustar selectors/pattern |
| Bob-bars | não registrada | adicionar em `config/brands.json` |

## 6. Consumo pela IA / OCR

- `POST /api/moon/identify` — OCR manda `{ean?, brand_text?, product_name_text?, volume_text?, back_label_inci?}`; cascata EAN→nome+volume→verificação por INCI do verso. Match Gold → payload completo; não-Gold → `is_gold=false`.
- `GET /api/moon/gold/{id}` — contrato Gold de 1 produto (INCI, como usar, descrição, imagens, hair_type/function, `allergens`, `cronograma_role`). 409 se não for Gold.
- `GET /api/moon/gold?hair_type=&function_objective=&product_category=` — navega o pool Gold.
- `POST /api/moon/analyze` (público) — agora retorna `allergens` (26 UE + sulfatos + isotiazolinonas + liberadores de formaldeído + álcoois ressecantes).

## 7. Admin

```bash
railway run haira create-user --email nikollas@sanchescreative.com --role admin
# já existe? redefine role/senha:
railway run haira create-user --email <e> --role admin --promote
```

## 8. Conhecidos / fora do escopo

- 2 testes pré-existentes falham (`taxonomy.normalize_product_type` — ordem do `_TYPE_MAP`).
- Falhas de `tests/api/test_ops.py` são infra multi-DB local (tabela `ingredients` no DB central) — não afetam produção.
- Montagem editorial do cronograma depende do Compêndio (criptografado, só em prod); a camada factual (`cronograma_role`) já está pronta.
