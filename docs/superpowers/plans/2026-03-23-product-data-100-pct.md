# Plano: Dados de Produto 100% — Lapidação por Marca

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar cada campo de produto o mais proximo possivel de 100% para todas as 46 marcas em producao.

**Architecture:** 4 frentes de ataque — (A) recovery de dados ja extraidos, (B) re-scrape com blueprints corrigidos, (C) enriquecimento automatizado por regex/heuristica, (D) LLM fallback para INCI em portugues. Cada marca e tratada individualmente.

**Tech Stack:** Python 3.12, SQLite, SQLAlchemy, BeautifulSoup, curl_cffi, Playwright, Claude API (LLM fallback)

---

## Diagnostico por marca

### Tier 1: Marcas com INCI recuperavel via re-scrape (blueprint fix)
Estas marcas TEM INCI no site mas os selectors estao errados ou incompletos.

| Marca | Produtos | INCI atual | Gap | Acao |
|-------|----------|-----------|-----|------|
| Griffus | 519 | 11% | section_classifier nao pega emoji labels | Re-scrape (fix ja aplicado, testar) |
| Haskell | 255 | 44% | 103 prods com composicao nao promovida a INCI | Testar composition->INCI promotion |
| All Nature | 208 | 28% | Nuvemshop table layout | Re-scrape com table fix |
| Widi Care | 171 | 13% | Table layout INCI | Re-scrape com table fix |
| Lola Cosmetics | 45 | 22% | Selectors possivelmente errados | Investigar blueprint |
| Joico | 79 | 3% | Tabs JS nao renderizadas | Playwright com wait_for tabs |
| Redken | 68 | 40% | Sitecore Vue (como L'Oreal) | Re-scrape headed |

### Tier 2: Marcas com dados parciais — enriquecer automaticamente
Campos faltantes recuperaveis via regex, heuristica ou copy de evidence.

| Marca | Gap principal | Acao |
|-------|-------------|------|
| Amend (461) | desc 51%, img 54%, cat 31% | Re-scrape sem stop_the_line para quarantined |
| Natura (365) | uso 3%, comp 3% | Blueprint precisa section_label_map |
| L'Occitane (256) | uso 0%, comp 3% | Blueprint precisa section_label_map |
| Keune (245) | desc 76% | Copiar de JSON-LD description |
| Seda (128) | vol 0%, comp 0% | Extrair vol do nome, comp da pagina |
| Aneethun (118) | TUDO 0% | Site so tem nome+imagem, sem texto |
| Alva (109) | desc 0%, uso 0% | Blueprint sem section_label_map |
| Granado (67) | uso 0%, comp 0% | Blueprint tem labels mas nao extrai |
| Aussie (15) | desc 0%, vol 0% | Site minimo |

### Tier 3: Marcas sem INCI no site — LLM ou dados externos
Estes sites genuinamente nao publicam INCI. Opcoes: LLM para converter nomes PT-BR, ou aceitar catalog_only.

| Marca | Produtos | Opcao |
|-------|----------|-------|
| Bio Extratus (197) | 0% | Sem INCI no site. Catalog only. |
| Aneethun (118) | 0% | Marketing only. Catalog only. |
| Brae (75) | 0% | Ativos sim, INCI nao. Catalog only. |
| Acquaflora (73) | 0% | Sem INCI. Catalog only. |
| Dove (53) | 0% | Template vazio. Catalog only. |
| Pantene (47) | 0% | INCI em __NEXT_DATA__ mas nao extraido | Corrigir extrator |
| Elseve (31) | 0% | Ingredientes em PT-BR, nao INCI padrao | LLM fallback |
| Salon Line (128) | 5% | Sem INCI no OCC. Catalog only. |

---

## Tasks

### Task 1: Recovery — Promover composition valida a INCI

**Files:**
- Modify: `src/extraction/section_classifier.py` (promotion logic)
- Script: inline SQL update

O section_classifier ja tem o fix de promotion, mas os produtos existentes no DB nao foram re-processados. Vou rodar um update em batch.

- [ ] **Step 1: Identificar produtos com composition que parece INCI**
```sql
SELECT id, brand_slug, composition FROM products
WHERE verification_status != 'verified_inci'
AND composition IS NOT NULL AND LENGTH(composition) > 30
AND (composition LIKE '%Aqua%' OR composition LIKE '%Water%' OR composition LIKE '%AQUA%')
```

- [ ] **Step 2: Script para promover composition -> inci_ingredients**
```python
# Para cada produto com composition que passa validate_inci_content()
# Atualizar inci_ingredients e verification_status
```

- [ ] **Step 3: Rodar e verificar quantos foram promovidos**

- [ ] **Step 4: Migrar para producao**

---

### Task 2: Re-scrape Tier 1 com fixes aplicados

**Files:**
- Modify: blueprints de cada marca
- Run: `haira scrape --brand <slug>`

- [ ] **Step 1: Griffus** — Re-scrape (emoji fix ja aplicado). Esperado: 11% -> ~30%
- [ ] **Step 2: Haskell** — Re-scrape. Esperado: 44% -> ~60%
- [ ] **Step 3: All Nature** — Re-scrape (table fix). Esperado: 28% -> ~50%
- [ ] **Step 4: Widi Care** — Re-scrape (table fix). Esperado: 13% -> ~40%
- [ ] **Step 5: Lola Cosmetics** — Investigar blueprint, re-scrape
- [ ] **Step 6: Joico** — Re-scrape com Playwright headless + wait_for tabs
- [ ] **Step 7: Redken** — Re-scrape com headed browser (Cloudflare)
- [ ] **Step 8: Migrar tudo para producao**

---

### Task 3: Enriquecer campos faltantes — batch automatizado

**Files:**
- Create: `scripts/enrich_products.py`

Script unico que roda todos os enriquecimentos:

- [ ] **Step 1: size_volume** — Regex no product_name para TODOS os produtos sem volume
- [ ] **Step 2: usage_instructions** — Copiar de care_usage onde disponivel
- [ ] **Step 3: product_category** — Inferir de product_type_normalized ou product_name
- [ ] **Step 4: description** — Copiar de product_evidence onde description esta vazio
- [ ] **Step 5: image_url_main** — Copiar de product_images normalizado onde vazio
- [ ] **Step 6: Rodar e migrar**

---

### Task 4: Fix blueprints Tier 2 — marcas com dados parciais

- [ ] **Step 1: Natura** — Adicionar section_label_map para uso/composicao
- [ ] **Step 2: L'Occitane BR** — Adicionar section_label_map
- [ ] **Step 3: Alva** — Adicionar section_label_map (atualmente 0 desc, 0 uso)
- [ ] **Step 4: Granado** — Debug por que uso/comp nao extrai (labels existem no blueprint)
- [ ] **Step 5: Re-scrape marcas corrigidas**
- [ ] **Step 6: Migrar**

---

### Task 5: Pantene — Extrair INCI de __NEXT_DATA__

**Files:**
- Modify: `src/extraction/deterministic.py` — adicionar estrategia JSON-LD __NEXT_DATA__
- Modify: `config/blueprints/pantene.yaml`

- [ ] **Step 1: Investigar estrutura do __NEXT_DATA__**
```python
# Fetch pagina Pantene e parsear __NEXT_DATA__ JSON
# Encontrar campo allIngredients
```
- [ ] **Step 2: Adicionar extrator de __NEXT_DATA__**
- [ ] **Step 3: Re-scrape Pantene**
- [ ] **Step 4: Migrar**

---

### Task 6: Elseve — LLM para converter ingredientes PT-BR para INCI

**Files:**
- Modify: `src/extraction/inci_extractor.py` — adicionar modo PT-BR
- Config: `config/labels/pt_br_to_inci.yaml` — mapeamento manual

- [ ] **Step 1: Mapear ingredientes PT-BR mais comuns**
```yaml
# Agua -> Aqua, Alcool Cetilico -> Cetyl Alcohol, etc.
```
- [ ] **Step 2: Adicionar validacao que aceita nomes PT-BR como INCI valido**
- [ ] **Step 3: Re-scrape Elseve**
- [ ] **Step 4: Migrar**

---

### Task 7: Desquarantinar Amend — recuperar 211 produtos

**Files:**
- Modify: `src/core/qa_gate.py` — relaxar regra no_image para kits

Amend tem 211 quarantined (maioria kits sem imagem individual).

- [ ] **Step 1: Analisar motivos de quarentena**
- [ ] **Step 2: Relaxar no_image para produtos com nome valido + descricao**
- [ ] **Step 3: Re-processar quarantined**
- [ ] **Step 4: Migrar**

---

### Task 8: Migracao final + verificacao

- [ ] **Step 1: Rodar enrichment script completo**
- [ ] **Step 2: Delete all brands em producao**
- [ ] **Step 3: Full migration**
- [ ] **Step 4: Update enriched fields**
- [ ] **Step 5: Verificacao: cada marca > 80% nos campos principais**
- [ ] **Step 6: Commit + push + deploy**

---

## Meta esperada pos-plano

| Campo | Atual | Meta |
|-------|-------|------|
| INCI verificado | 40% | 55-60% |
| Descricao | 83% | 95% |
| Foto | 95% | 98% |
| Modo de uso | 45% | 70% |
| Volume | 67% | 85% |
| Composicao | 34% | 50% |
| Categoria | ~75% | 90% |

Marcas catalog_only (Bio Extratus, Aneethun, Acquaflora, Brae, Dove, Salon Line) permanecem sem INCI por design — sites nao publicam.
