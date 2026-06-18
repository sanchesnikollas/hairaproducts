# HAIRA v2 — Redesenho do Workflow: a régua "Gold" e a base que alimenta a IA

> Documento de arquitetura/processo. Define a base de produtos capilares verídica e
> completa que vai alimentar a Moon (IA): cronograma capilar, alérgenos, recomendação,
> e o caso de uso OCR (ler o produto físico → consultar a base → responder).
>
> Status: proposta de design. Não implementado. Data: 2026-06-17.

---

## 1. Contexto e objetivo

A HAIRA scrapeia e-commerces para montar uma base de produtos capilares. Hoje essa base
é usada como catálogo + scoring de INCI pela Moon. O objetivo agora é elevá-la a uma
**fonte de verdade confiável o suficiente para uma IA construtiva** — um OCR vai ler um
produto físico, casar com a base e devolver ingredientes, modo de uso, alertas de
alérgenos e orientação de cronograma. Logo o dado precisa ser **verídico e funcional**,
não apenas "presente".

**Decisões do dono do produto (norteiam todo o design):**
1. Escopo completo: workflow de qualidade + camada de consumo OCR→base + lógica de IA (cronograma/alérgenos).
2. **Régua "Gold" rigorosa** para o que a IA consome: produto só é Gold com **INCI verificado + foto + como usar + descrição + categoria**. Base menor, porém impecável.
3. **Não remover nada.** A base completa permanece para operação; a régua Gold já exclui naturalmente do consumo da IA o que não é produto capilar/confiável.

---

## 2. Diagnóstico crítico (o que está errado hoje)

Base atual: **6.170 produtos**.

| Indicador | Hoje | Implicação |
|---|---|---|
| `verified_inci` | 36,7% | Único tier que a IA consome hoje |
| `catalog_only` (sem INCI) | 60,8% | Maioria inutilizável para a IA |
| `quarantined` | 2,5% | Maioria por `no_image` |
| INCI presente | 36,9% | Bloqueia alérgenos/scoring para 63% |
| **`usage_instructions` (como usar)** | **0%** | Campo existe mas **nunca é gravado** |
| `care_usage` | 29,5% | É onde o "como usar" está, mas não chega no campo certo |
| descrição | 72,7% · foto 97,5% · preço 46% · labels 32,3% | |
| `ph`, `hair_type`, `function_objective`, `audience_age`, `image_url_front/back` | 0% | Criados em migration, nunca populados |

**As três falhas de raiz (a verdadeira causa da dor com "quarentena"):**

1. **A régua de "produto confiável" é fraca.** `verified_inci` é atribuído com critérios frouxos que deixam **texto de marketing entrar como INCI verídico**:
   - `section_classifier.py` (~L304-317) promove "Composição" (texto PT de marketing) a `ingredients_inci` quando há ≥3 "ingredientes-âncora" — código duplicado em 5 lugares.
   - `inci_validator.py` (~L123): mínimo de **3** ingredientes quando há contexto de seção → listas truncadas/incompletas viram "verificadas".
   - `inci_validator.py` (~L62-66): a rejeição de verbos de marketing é **desligada** quando há contexto de seção → "deixe agir por 3 minutos" sobrevive como "ingrediente".
   - `coverage_engine.py` (~L238-264): INCI extraído por seletor = confiança 0.90 e por LLM = 0.85 (ambos passam o gate 0.80 **sem grounding**) → INCI alucinado pelo LLM pode virar "verificado".

2. **Aprovar na quarentena só vira o status — não corrige o dado.** `quarantine.py` (~L98-119) e `ops.py` (~L562-586) fazem `verification_status = "verified_inci"` sem checar nada. Um revisor "aprova" lixo. **Esse é exatamente o erro que você não quer repetir.**

3. **Perdas silenciosas.** Páginas com WAF/Cloudflare (`deterministic.py` ~L466-468) retornam vazio e o produto **some sem registro de quarentena, sem alerta**. Some sem rastro.

**Conclusão:** o problema não é "ter quarentena". É que o conceito de "confiável" hoje não garante verdade — e é isso que alimenta a IA. A solução é uma **régua positiva, auditável e impossível de furar por flip de status.**

---

## 3. O conceito central: a régua "Gold" + contrato de dados

Hoje um único enum (`verification_status`) mistura três perguntas distintas. Separe-as:

| Eixo | Pergunta | Dono | Onde fica |
|---|---|---|---|
| Extração | Conseguimos puxar o dado da fonte? | scraper | `verification_status` (rebaixado a sinal de extração) |
| Completude | Os campos exigidos pelo Gold estão presentes? | função de gate | `gold_status` + `gold_blockers` |
| Veracidade | Cada campo é o que diz ser (INCI real, instrução real)? | gate reusando validadores | `gold_status` + `field_provenance` |

### 3.1 Três níveis de produto

- **Gold (consumo da IA — os 5 campos exigidos):** INCI verificado (estrito, anti-marketing) + imagem (front/main) + `usage_instructions` (instrução real, com verbo de ação) + descrição (prosa real, não lista de INCI) + categoria (vocabulário controlado). **É o único tier que a Moon lê.**
- **Gold+ ("pronto para cronograma"):** Gold + `hair_type` + `function_objective`. Necessário para montar cronograma e recomendar bem. Populado pelo pipeline `classify` (já existe).
- **Bônus (exposto, não bloqueia Gold):** `ph`, `image_url_back`, `ean`, `audience_age`. Enriquecem OCR e IA, mas não impedem Gold (coerente com a régua de 5 campos que você definiu).

`gold_status` (novo enum): `raw → catalog → gold_candidate → gold` (+ `gold_rejected`).
A transição **automática** para `gold` só ocorre quando a função de gate passa com tudo verídico; o que tem ambiguidade de confiança vira `gold_candidate` e vai para revisão humana. `is_gold` é conveniência = `gold_status == 'gold'`.

### 3.2 Contrato Gold (checklist que a função `evaluate_gold` aplica)

Novo arquivo **`src/core/gold_gate.py`** com `evaluate_gold(product) -> (gold_status, blockers, field_report)`, espelhando `qa_gate.run_product_qa` e **reusando** `validate_inci_list`, `validate_product_fields`, `validate_product_name_quality`, `VALID_CATEGORIES`.

- **G1 — INCI verídico:** `validate_inci_list(inci, has_section_context=False)` (piso de 5 termos, rejeição de verbos ligada) **E** zero erros de `field_validator` (`inci_is_marketing`, `inci_is_usage`, `inci_has_sentences`) **E** **≥60% dos termos resolvem** para um ingrediente conhecido (`ingredients`/`ingredient_aliases`, resolver read-only sem auto-criar) — defesa mais forte contra INCI alucinado/marketing **E** procedência aceitável (`extraction_method` ∈ jsonld/html_selector/js_dom/manual/external; `llm_grounded` puro → no máximo `gold_candidate`).
- **G2 — Imagem:** `image_url_main`/`image_url_front` presente e válido (URL com esquema+host). `image_url_back` é desejável (melhora OCR) mas **não bloqueia** Gold.
- **G3 — Como usar real:** `usage_instructions` presente, ≥30 chars, **com verbo de ação**, e **não** é rótulo de aba ("Como usar"/"Modo de uso") — reusa `field_validator._check_usage_quality` + `section_classifier.TAB_LABEL_NOISE`.
- **G4 — Descrição real:** `description` presente, ≥40 chars, **não** é lista de INCI nem rótulo de aba (`_check_description_quality`).
- **G5 — Categoria:** `product_category` ∈ `VALID_CATEGORIES` (`taxonomy.py`).
- **G6 — É capilar e não quarentenado:** `verification_status != quarantined`, `is_hidden == False`, `hair_relevance_reason` não começa com `non_hair`.
- **G7 — Nome:** `validate_product_name_quality(...).is_valid`.

`blockers` é lista de `{code, field, message}` → vira **checklist visível no Ops** ("4/5 critérios Gold — falta: como usar, INCI").

---

## 4. Arquitetura do novo workflow (3 camadas)

### Camada 1 — Qualidade & Gold gate (a confiança)

Objetivo: tornar impossível um dado não-verídico chegar à IA, e tornar a aprovação humana significativa.

1. **Corrigir os vazamentos de extração** (todos mapeados):
   - **Fix A** `section_classifier.py`: extrair os 5 blocos duplicados em um único `_classify_inci_or_composition(content) -> (field, needs_review)`; remover a promoção por contagem-de-âncoras direto para `ingredients_inci` (marketing PT fica em `composition` + `needs_inci_review`).
   - **Fix B** `inci_validator.py`: caminho Gold sempre chama `validate_inci_list(..., has_section_context=False)` → piso de 5; o piso de 3 fica só para o sinal de extração `verified_inci`.
   - **Fix C** `inci_validator.py` + `field_validator`: filtro de verbo de marketing sempre roda no caminho Gold; checagens de nível-de-lista (`_check_inci_is_usage/_is_marketing`) entram no G1.
   - **Fix D** `coverage_engine.py`: confiança **deixa de ser entrada do Gold** (vira só ordenação de fila); LLM sem locator verificável → INCI gravado mas no máximo `gold_candidate`, confiança rebaixada de 0.85 → 0.50; `extraction_method` persistido na evidência do INCI.
   - **Fix E** `deterministic.py` + `coverage_engine.py`: WAF deixa de retornar vazio silencioso → marca `blocked_reason="waf_challenge"` → vira `QuarantineDetailORM` com `rejection_code="waf_challenge"` (aparece no Ops com badge próprio; permite re-scrape por outro caminho, sem perder o produto).

2. **`evaluate_gold`** roda no pipeline depois do `run_product_qa` e em **todo** `PATCH /ops/products/{id}` — produto impecável vira `gold` sozinho; ambíguo vira `gold_candidate`.

3. **Aprovar passa a EXIGIR o gate** (corrige a falha de raiz nº2):
   - `quarantine.approve` e `ops.ops_quarantine_promote`: roda `evaluate_gold`; só vira `gold` se passar. Se não passar → **HTTP 422 com a lista de blockers**. Promoção sem dado corrigido só chega a `catalog` (tira da quarentena para visibilidade), nunca a `gold`.
   - `ops.resolve_review` (`approve`/`correct`): após aplicar correções, re-roda `evaluate_gold` e devolve os blockers restantes. Novo `gold_reject` com `notes` obrigatório (trilha de "olhamos e não dá para confiar").
   - `PATCH /ops/products`: ao gravar INCI manual, validar com `validate_inci_list(has_section_context=False)` antes de marcar `verified_inci`; persistir `gold_status`/`gold_blockers`; devolver `GoldEvaluation` para a UI atualizar o checklist ao vivo.

4. **Ops UI:** painel "Gold Status" com checklist de blockers; botão "Aprovar para Gold" **desabilitado enquanto houver blocker**; tornar `image_url_front/back` editáveis; badge `waf_challenge` na quarentena.

### Camada 2 — Cobertura & enriquecimento ("Push-to-Gold")

Objetivo: subir o máximo de produtos reais para Gold, do mais barato/confiável ao mais caro. Princípio: **todo campo carrega procedência + tier de confiança** (`field_provenance` JSON novo); só `deterministic`/`verified`/`dual_validated` contam para Gold. LLM-only e external-only são `provisional` e **nunca viram Gold em silêncio**.

1. **Fase 0 — recuperação a custo zero (maior alavanca):** o "como usar" já é extraído como `care_usage`, mas `_extract_product` (`coverage_engine.py` ~L268-289) **nunca** copia para `usage_instructions` (`repository.py` grava `None`). Fix: ao retornar, se `care_usage` passa no gate de verbo de ação → `usage_instructions = care_usage`. **+ backfill** `UPDATE products SET usage_instructions = care_usage WHERE usage_instructions IS NULL AND care_usage IS NOT NULL AND <passa gate>`. Recupera ~29,5% de "como usar" instantaneamente, sem rede, sem LLM.

2. **Estratégia por campo (determinístico → externo → LLM-grounded → manual):**
   - INCI: pipeline atual (forte) + `audit-inci` direciona `extraction_missed`/`extracted_rejected` para re-parse/ajuste.
   - como usar/descrição/categoria/imagem: determinístico primeiro; categoria via `normalize_category` (backfill nos nulos).
   - front/back: heurística de posição na galeria (1ª imagem = front, última = back), sem LLM.
   - campos de IA (`hair_type`/`function_objective`/`audience_age`): **já existem** via comando `classify` (`main.py` ~L1019) — falta é orquestração, não código. `--with-validation` faz dupla-checagem.
   - `ph`: extrator de regex literal novo (`ph_extractor.py`, `config/ph.yaml`) — **proibido inferir por LLM**; só quando a página declara.

3. **Loop operacional por marca, mensurável e idempotente** (ordem por `priority` em brands.json, depois por tamanho do catálogo):
   ```
   haira gold-report --brand B      # baseline: % Gold + gap por campo (NOVO)
   haira backfill-usage --brand B   # copia care_usage→usage_instructions (NOVO, Fase 0)
   haira scrape --brand B           # re-extração determinística (já grava usage agora)
   haira audit-inci --brand B       # bins de falha de INCI → ação
   haira source-scrape --source belezanaweb --brand B
   haira enrich-external --brand B  # INCI externo (auto >0.90, fila 0.75–0.90)
   haira enrich --brand B           # LLM-grounded, budget-capped (provisional)
   haira classify --brand B --with-validation   # hair_type/function/age (Gold+)
   haira labels --brand B           # selos (agora lê usage_instructions)
   haira gold-report --brand B      # mede o delta; o gap diz qual fila Ops trabalhar
   ```
   `gold-report` (NOVO, irmão de `report`/`audit-inci`) imprime % Gold e contagem de produtos faltando cada campo; persiste em `BrandCoverageORM.coverage_report` (+ colunas `gold_total`/`gold_rate`).

4. **LLM sempre verídico:** `LLMClient.extract_structured` já manda o texto da página e "nunca alucine"; **toda** saída LLM passa pelos validadores determinísticos antes de gravar (INCI sem âncora/ com verbo → descartado). Caminho de auto-promoção verídico = **dupla validação** (`validate`): quando Pass-1 determinístico e Pass-2 LLM **concordam** sobre a mesma página → dois groundings independentes → sobe de `provisional` para `dual_validated` (elegível a Gold). Divergiu → `ReviewQueueORM` → `OpsDualValidation` para humano.

5. **Fonte externa confiável:** chave de match **marca + nome + volume** (penaliza volume divergente: 300ml ≠ 1L), **EAN como match exato → auto 1.0**; médias (0.75–0.90) vão para `EnrichmentQueueORM` revisadas na mesma UI `OpsDualValidation`.

### Camada 3 — Consumo (OCR → base → resposta; alérgenos; cronograma)

Objetivo: definir o que a base precisa **expor** e como a IA/OCR lê — o que justifica de volta os campos que o enriquecimento deve preencher.

1. **OCR `POST /api/moon/identify`** (reusa `enrichment/matcher.py`):
   - Cascata de match: **EAN** (exato, tier-0) → **marca+nome fuzzy** (tier-1) → **desambiguação por volume** → **INCI do verso como verificação** (Jaccard contra o INCI armazenado: confirma/possível reformulação/mismatch) → imagem (hook futuro).
   - Base precisa expor: **nova coluna `ProductORM.ean`** (indexada; backfill de `ExternalInciORM.ean`), **`name_normalized`** + **`match_tokens`** pré-computados (evita varredura O(N) em request), índice `(brand_slug, product_type_normalized)`.
   - Se achou mas **não é Gold** → devolve stub (nome/marca/foto) + `is_gold=false` ("achei, mas ainda não posso orientar"). Degradação graciosa: se vier INCI do verso, roda `score_inci` no INCI cru mesmo sem match Gold.

2. **Contrato Gold de consumo** (`GoldProductContract`): servido por `GET /api/moon/gold[/{id}]` e `GET /api/moon/gold?hair_type=&function=&cleansing_strength=` — **substitui** a query ad-hoc + blacklist `LIKE '%labial%'` de `_fetch_alternatives` (`moon.py` ~L348-367) por um gate positivo `WHERE gold_status='gold'`. Inclui INCI canonizado por posição, `allergens_summary` e `cronograma_role` (derivados).

3. **Modelo de alérgenos** (novo `IngredientAllergenORM` ligado a `ingredients.id`):
   - Vocab `allergen_class`: `fragrance_allergen` (**seed dos 26 alérgenos da UE já presentes em `scripts/categorize_ingredients.py`**), `sulfate_harsh` (seed do `Rotinas e Produtos para Moon.md`), `mci_mit_preservative`, `formaldehyde_releaser`, `drying_alcohol`, `scalp_sensitizer_other`. Severidade `info|caution|high`.
   - **Pré-requisito:** backfill da tabela `ingredients` (5.213 linhas só com `canonical_name`; `category` NULL; `ingredient_aliases` vazio) rodando/estendendo `scripts/categorize_ingredients.py`; popular aliases PT/EN. Sem isso, alérgenos e scoring ficam cegos.
   - `score_inci` ganha `LEFT JOIN ingredient_allergens` e a Moon passa a dizer "contém Limonene/Linalool (alérgenos de fragrância UE) — relevante porque seu perfil é sensibilizado".

4. **Cronograma capilar:** lógica fica **gerada/grounded no Compêndio** (`Inteligence/Rotinas e Produtos para Moon.md` via KB — não hardcodar regras editoriais); **persiste o plano aceito** (novas `CronogramaORM` + `CronogramaStepORM`). Montagem: `derive_hair_types(profile)` → cadência e "alterne 2 linhas" do Doc → consulta o pool Gold filtrado por `function_objective`/`hair_type`/`cleansing_strength` (derivado das categorias de INCI em novo `src/core/cronograma.py`) → ranqueia com `score_inci`. **Corrigir lacuna:** adicionar slugs `ondulado` e `grosso` em `KNOWN_HAIR_TYPE_SLUGS` + `ingredient_compatibility.yaml` (o Doc tem regras para eles, o motor não).

5. **Reflexo nos campos exigidos:** o contrato de consumo é o que justifica cada obrigação do enriquecimento (EAN/normalizados p/ OCR; front/back p/ confirmação visual; `usage_instructions` p/ "como usar"; `function_objective`/`hair_type` p/ cronograma; `ingredients`+aliases+allergens p/ alérgenos). Ciclo: **contrato define campos → Gold gate exige → `gold_blockers` diz ao enriquecimento o que falta → enriquecimento preenche → produto vira Gold → Moon consome.**

---

## 5. Mudanças de schema (consolidadas, Alembic em `src/storage/migrations/versions/`)

`ProductORM`:
- `gold_status` `String(20)` NOT NULL default `'raw'`, indexado
- `gold_blockers` `JSON`, `gold_evaluated_at` `DateTime`
- `gold_reviewed_by` FK users, `gold_review_notes` `Text`
- `field_provenance` `JSON` (procedência + tier de confiança por campo)
- `ean` `String(50)` indexado · `name_normalized` `Text` indexado · `match_tokens` `JSON`
- índice composto `(brand_slug, product_type_normalized)`

`BrandCoverageORM`: `gold_total` `Integer`, `gold_rate` `Float`.
`ExternalInciORM`: `usage_instructions_raw` `Text` (e opcional `description_raw`, `ph`).
Novas tabelas: `IngredientAllergenORM`, `CronogramaORM`, `CronogramaStepORM`.
Novos modelos Pydantic em `src/core/models.py`: `GoldStatus`, `GoldEvaluation`, `GoldBlocker`.
Novos arquivos: `src/core/gold_gate.py`, `src/core/cronograma.py`, `src/extraction/ph_extractor.py`, `src/enrichment/ocr_matcher.py`, `config/ph.yaml`.

---

## 6. Roadmap faseado (ordem por dependência)

| Fase | Entrega | Por quê primeiro |
|---|---|---|
| **0** | Fix `usage_instructions` + `backfill-usage` | Custo zero, maior salto imediato de Gold; recupera 29,5% de "como usar" |
| **1** | `gold_gate.py` + migration (gold_status/blockers/provenance) + `gold-report` + filtro `gap=nao_gold` no Ops | Torna a régua existente e **mensurável** |
| **2** | Fixes A–E (extração) + `evaluate_gold` no pipeline | Fecha os vazamentos de INCI e a perda silenciosa por WAF |
| **3** | Aprovação passa pelo gate (quarantine/ops/resolve) + Ops UI (checklist, botão travado, front/back editáveis) | Corrige a falha de raiz: aprovar = dado corrigido, não flip |
| **4** | Re-sweep determinístico por marca prioritária + categoria/front-back/ph | Sobe Gold sem custo de LLM |
| **5** | Externo endurecido (volume/EAN) + extensão a usage/descrição | Cobertura confiável de INCI/usage |
| **6** | LLM enrich + dual-validation com auto-upgrade provisional→dual_validated | Cauda longa, com verdade garantida |
| **7** | Backfill `ingredients` + `ingredient_aliases` + modelo de alérgenos | Pré-requisito da camada de consumo |
| **8** | `is_gold` na query da Moon + contrato Gold + `/moon/identify` (OCR) | Liga o consumo OCR→base |
| **9** | Cronograma (model + endpoints) + slugs `ondulado`/`grosso` | Lógica de IA construtiva sobre Gold |

Fases 0–3 são a fundação (qualidade e confiança). 4–6 sobem cobertura. 7–9 entregam o consumo IA/OCR/cronograma.

---

## 7. Como verificar (métricas de sucesso)

- **Gold rate** por marca prioritária sobe a cada volta do loop (`gold-report`).
- **Zero** produtos viram `gold` por flip de status (todo `gold` tem `evaluate_gold` passando + `field_provenance` aceitável).
- **Anti-junk:** amostra de INCI Gold sem texto de marketing / sem itens com verbo / ≥5 termos / ≥60% resolvidos a ingrediente conhecido.
- `usage_instructions` sai de 0% para ≈ cobertura de `care_usage` na Fase 0 e cresce no loop.
- Páginas WAF aparecem na quarentena com `waf_challenge` (nenhuma some sem rastro).
- `/moon/identify` casa por EAN e por nome+volume; INCI do verso confirma/sinaliza reformulação.
- Moon cita alérgenos reais a partir do join de `ingredient_allergens`.
- Testes: gate unitário (`gold_gate`), validadores (anti-marketing), matcher OCR, e regressão de extração (`pytest tests/core/...`).

---

## 8. Decisões assumidas e em aberto

**Assumidas (padrões sensatos; corrija se discordar):**
- `image_url_back` e `ph` são **bônus**, não bloqueiam Gold (coerente com sua régua de 5 campos).
- `usage_instructions` é o campo canônico de "como usar"; `care_usage` é o sink bruto.
- `/moon/identify` faz **degradação graciosa**: sem match Gold mas com INCI do verso, ainda analisa o INCI cru.

**Em aberto (decisão sua quando chegarmos lá):**
- Meta de Gold rate por marca prioritária (ex.: 80%?) e quais marcas entram primeiro.
- Persistir cronograma do usuário desde já, ou só gerar on-the-fly na v1.
- `gold_candidate` exige revisão humana sempre, ou auto-promove quando dual-validation concorda.
