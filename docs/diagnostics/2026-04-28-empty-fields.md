# Diagnóstico — Campos vazios em `products`

**Data:** 2026-04-28
**Investigado:** `usage_instructions` (0%), `benefits_claims` (0%), `line_collection` (0%) — em 12.949 produtos

---

## Resumo

| Campo | Status | Causa-raiz | Fix recomendado |
|-------|--------|-----------|-----------------|
| `usage_instructions` | 0% (12.949 vazios) | Vestigial pós-migration `d4b8e2f3a567` (2026-03-03) — dados foram movidos para `care_usage` | **Consolidar:** sempre escrever em ambos, ou deprecar `usage_instructions` na UI/API |
| `benefits_claims` | 0% (12.949 vazios) | `section_classifier.py` não tem suporte ao taxonomy_field `benefits_claims` | **Adicionar suporte** no section_classifier + parser dedicado para listas em description |
| `line_collection` | 0% (12.949 vazios) | Nunca extraído — não há código que popula | **Adicionar parser** via meta tags / breadcrumb / regex em product_name |

---

## Detalhe — `usage_instructions`

A migration `src/storage/migrations/versions/d4b8e2f3a567_add_taxonomy_fields.py` (2026-03-03) adicionou `care_usage` e copiou:

```sql
UPDATE products SET care_usage = usage_instructions WHERE usage_instructions IS NOT NULL
```

Mas **não** zerou `usage_instructions`. Ainda assim, o pipeline atual (`src/extraction/section_classifier.py`) **só escreve em `care_usage`**, nunca em `usage_instructions`.

**Verificação no banco atual:**

```
care_usage:           3.549 produtos preenchidos (27.4%)
usage_instructions:   0 produtos preenchidos
```

Concentração por marca em `care_usage`:
- o-boticario: 1.668
- eudora: 1.302
- forever-liss-professional: 167
- all-nature: 110
- seda: 106

**Conclusão:** `usage_instructions` é vestigial. Ainda aparece no:
- `src/storage/orm_models.py` linha 43
- `src/core/models.py` linha 82
- `src/core/field_validator.py` linhas 260, 273, 375, 391
- `src/core/label_engine.py` linhas 184-200, 376-388
- `src/api/routes/products.py` linha 31
- `src/cli/main.py` linha 488
- `src/storage/repository.py` linhas 55, 88

---

## Detalhe — `benefits_claims`

`SectionExtractionResult` em `src/extraction/section_classifier.py:25-30`:

```python
@dataclass
class SectionExtractionResult:
    description: str | None = None
    care_usage: str | None = None
    composition: str | None = None
    ingredients_inci_raw: str | None = None
    sections: list[PageSection] = field(default_factory=list)
```

Não há `benefits_claims`. O classifier suporta apenas 4 campos taxonômicos.

Os blueprints (`config/blueprints/*.yaml`) também só declaram seções para `description`, `care_usage`, `composition`, `ingredients_inci`. Nenhum tem mapping para benefícios.

**Conclusão:** Feature nunca foi implementada. Para preencher precisaríamos de:
1. Adicionar campo `benefits_claims` em `SectionExtractionResult`
2. Adicionar mapping `benefits_claims` em `config/blueprints/*.yaml` com labels como `benefícios`, `vantagens`, `resultados`
3. Atualizar `section_classifier.py` para tratar o novo taxonomy_field
4. Pós-processar para JSON array (split por bullet/quebra de linha)

---

## Detalhe — `line_collection`

Não há código que popule esse campo. Marcas como Kerastase organizam produtos em linhas (Résistance, Nutritive, Discipline, Genesis), mas o nome da linha não é extraído.

**Onde poderia vir:**
1. **Meta tags / breadcrumb** — Kerastase tem `<meta property="product:line">` ou breadcrumb `Home > Résistance > Bain Force Architecte`
2. **Regex em product_name** — patterns conhecidos por marca (ex: "Kerastase Résistance Bain..." → linha = "Résistance")
3. **JSON-LD** — `additionalProperty` ou `category`

**Cobertura esperada:** baixa (~30-50%) porque nem toda marca organiza assim.

---

## Recomendação de Fix (a aplicar nas Fases 2-3 do plano)

### Plano de ação

1. **`usage_instructions`** — sincronizar com `care_usage`:
   - **Opção A (recomendada):** No `repository.py:upsert_product`, se `extraction.care_usage` existe e `usage_instructions` está vazio, copiar (manter ambos populados para retrocompatibilidade da UI)
   - **Opção B:** Deprecar `usage_instructions` da API/UI, manter só no schema para histórico
   - Decisão: **A** — copiar `care_usage` → `usage_instructions` no upsert, sem mexer na UI ainda

2. **`benefits_claims`** — adicionar feature completa:
   - Estender `SectionExtractionResult` com `benefits_claims: list[str] | None`
   - Adicionar bloco `benefits_claims:` no template de blueprints (labels: `benefícios`, `vantagens`, `o que oferece`, `resultados`, `benefits`)
   - Atualizar `section_classifier.py` para coletar e split em bullets/lines
   - Atualizar `deterministic.py:result["benefits_claims"]` na linha 348+

3. **`line_collection`** — extração simples:
   - No `deterministic.py`, após extrair name, tentar:
     - JSON-LD `category` ou `breadcrumb`
     - Meta tag `<meta property="product:line">`
     - Regex em product_name por brand (config opcional `line_patterns:` no blueprint)
   - Fallback null aceitável

### Quem executa o quê

- **Fase 1.5 (este diagnóstico):** documento ✓
- **Fase 2:** migration adiciona campos novos (não relacionado aos vazios — é independente)
- **Fase 3 estendida:** incluir os fixes acima como parte do scrape pipeline (separadamente do classifier)
- **Backfill:** rodar `haira scrape --brand kerastase` após fix → validar 100% nos campos antes vazios
