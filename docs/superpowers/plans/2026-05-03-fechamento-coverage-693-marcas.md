# Fechamento Coverage 693 Marcas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended). Steps use checkbox (`- [ ]`) syntax for tracking. Despache subagents fresh por task; review entre tasks. Use os agents existentes (`brand-onboarding`, `batch-processor`, `inci-enricher`, `pipeline-doctor`) para escala.

**Goal:** Levar o banco de **47 marcas / 11.899 produtos atuais** a **693 marcas com produtos coletados** via 3 canais: (a) scrape direto quando há site próprio, (b) source-scrape via distribuidores (Beleza na Web, Época) quando não há site, (c) catalog-stub mínimo + enrichment por amostragem para marcas inviáveis. Fechar paralelamente todos os gaps de qualidade nas 47 atuais (INCI ≥80%, price ≥90%, care_usage ≥60%).

**Architecture:** 13 fases em 3 tracks que podem rodar paralelos depois da Fase 7:

- **Track A (Fases 1-7):** Qualidade das 47 atuais — bug fixes em blueprints/labels, cleanup, auto-resolve. ~4-7h.
- **Track B (Fases 8-10):** Onboarding em wave das ~50-100 marcas pendentes com site próprio + INCI provável. Despacho via `brand-onboarding` agent em batch. ~2-3 dias.
- **Track C (Fases 11-12):** Source-scrape via distribuidores para as ~400-500 marcas sem site dedicado. Despacho via `inci-enricher` agent em batch. ~2-3 dias.
- **Track D (Fase 13):** Diagnóstico final, deploy, memory, plano de manutenção. ~1h.

Cada fase é independente — pode pausar entre elas. Backup do banco antes de cada modificação destrutiva. Padrão consolidado (do Hidratei/Alva/Joico): fix `requires_js`, ajuste de labels, cleanup, labels+classify, auto-resolve.

**Tech Stack:** Python CLI (haira scrape/labels/classify/source-scrape/enrich), pytest, scripts/ existentes, agents customizados (`.claude/agents/`), Railway deploy.

**Targets finais:**

*Qualidade (universo capturável das 47 originais):*
| Métrica | Hoje | Meta |
|---------|------|------|
| INCI hair-only (excl. gap fundamental) | 69% | ≥80% |
| Price | 75% | ≥90% |
| care_usage | 35% | ≥60% |
| Review queue pending | 149 | <50 |

*Cobertura (universo total 693):*
| Estado | Meta |
|--------|------|
| Marcas com produtos individuais (≥10 produtos) | ≥250 |
| Marcas com catalog-stub via source-scrape | ≥350 |
| Marcas marcadas inviável + razão documentada | ≤90 |
| **Soma 693** | ✓ |

**Marcas com gap fundamental (skip de re-scrape — site não publica INCI):** brae, bio-extratus, griffus, haskell, elseve, aneethun, loccitane, natura. Essas vão para enrichment via fontes externas (Track C).

**Marcas inviáveis** (sem site dedicado E sem presença em distribuidores principais): documentar no notes do brands.json com `status='no_source'`. Meta: ≤90 marcas dessa categoria.

---

## Fase 1 — Audit requires_js em keune/amend/inoar (Quick wins)

**Hipótese:** mesmo padrão Hidratei/Alva/Joico — `requires_js: true` desnecessário causa `expand_accordions=True` que degrada o DOM. Fix: trocar para `false` + re-scrape.

### Task 1.1: Inspecionar blueprints e DOM atual

**Files:**
- Read: `config/blueprints/keune.yaml`
- Read: `config/blueprints/amend.yaml`
- Read: `config/blueprints/inoar.yaml`

- [ ] **Step 1: Verificar valor atual de requires_js em cada blueprint**

```bash
for slug in keune amend inoar; do
  echo "=== $slug ==="
  grep -E "requires_js|platform" "config/blueprints/$slug.yaml" | head -5
done
```

Expected: cada um mostra `requires_js: true` e platform.

- [ ] **Step 2: Pegar 1 URL sample de produto individual (não-kit) de cada marca**

```bash
source .venv/bin/activate && python -c "
import sqlite3
conn = sqlite3.connect('haira.db')
cur = conn.cursor()
for slug in ['keune','amend','inoar']:
    cur.execute('''SELECT product_url FROM products WHERE brand_slug=?
                   AND product_name LIKE \"%hampoo%\" AND product_name NOT LIKE \"%Kit%\"
                   LIMIT 1''', (slug,))
    row = cur.fetchone()
    print(f'{slug}: {row[0] if row else None}')
"
```

Expected: 1 URL por marca, todas terminando em path de produto (não /collections/).

- [ ] **Step 3: Testar fetch httpx + extract_product_deterministic em cada URL**

```bash
source .venv/bin/activate && PYTHONPATH=. python << 'PY'
import httpx, yaml, sys
sys.path.insert(0, '.')
from src.extraction.deterministic import extract_product_deterministic

URLS = {
    'keune': '<URL_FROM_STEP_2>',
    'amend': '<URL_FROM_STEP_2>',
    'inoar': '<URL_FROM_STEP_2>',
}
for slug, url in URLS.items():
    bp = yaml.safe_load(open(f'config/blueprints/{slug}.yaml'))
    extr = bp.get('extraction', {})
    r = httpx.get(url, follow_redirects=True, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
    print(f'\n=== {slug} (HTTP {r.status_code}, len={len(r.text)}) ===')
    if r.status_code != 200 or len(r.text) < 1000:
        print('  unusable response — skip')
        continue
    res = extract_product_deterministic(
        html=r.text, url=url,
        inci_selectors=extr.get('inci_selectors'),
        name_selectors=extr.get('name_selectors'),
        image_selectors=extr.get('image_selectors'),
        section_label_map=extr.get('section_label_map'),
        price_selectors=extr.get('price_selectors'),
        description_selectors=extr.get('description_selectors'),
    )
    for k in ('product_name','price','inci_raw','care_usage','description'):
        v = res.get(k)
        if isinstance(v,str): v = v[:80]
        print(f'  {k}: {v!r}')
PY
```

Expected output: para cada slug, ver se extraction funciona via httpx (price não-None, INCI presente, etc).

- [ ] **Step 4: Decidir candidatas reais**

Critério: marca passa para Task 1.2 se via httpx capturar AT LEAST price e INCI corretamente.
Documentar em scratch:
```
keune: <CANDIDATA / SKIP — razão>
amend: <CANDIDATA / SKIP — razão>
inoar: <CANDIDATA / SKIP — razão>
```

### Task 1.2: Aplicar requires_js=false nas candidatas

Para cada slug confirmado em Task 1.1 Step 4:

- [ ] **Step 1: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_<slug>_no_js
ls -la haira.db.bak.20260503_pre_<slug>_no_js
```

Expected: arquivo criado.

- [ ] **Step 2: Editar blueprint — trocar requires_js: true → false**

Edit `config/blueprints/<slug>.yaml`: trocar `requires_js: true` por `requires_js: false` na chave `extraction:`.

- [ ] **Step 3: Re-scrape em background**

```bash
mkdir -p logs && \
source .venv/bin/activate && export $(grep -v '^#' .env | xargs) && \
PYTHONPATH=. python -m src.cli.main scrape --brand <slug> 2>&1 | \
  tee logs/<slug>_no_js_$(date +%H%M%S).log
```

Run via `run_in_background: true` — ver via Monitor.

- [ ] **Step 4: Validar re-scrape concluiu**

```bash
tail -10 logs/<slug>_no_js_*.log
```

Expected: ver "Brand <slug> complete: X extracted, Y verified".

- [ ] **Step 5: Cleanup URLs lixo**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/cleanup_non_product_urls.py <slug>
```

Expected: relatório com N produtos removidos.

- [ ] **Step 6: Verificar coverage pós-fix**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
c.execute('''SELECT COUNT(*),
  SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != \"[]\" AND inci_ingredients != \"null\" THEN 1 ELSE 0 END),
  SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END),
  SUM(CASE WHEN care_usage IS NOT NULL AND care_usage != \"\" THEN 1 ELSE 0 END)
  FROM products WHERE brand_slug=?''', ('<slug>',))
t,i,p,care = c.fetchone()
print(f'<slug>: total={t}, INCI={100*i/t:.0f}%, price={100*p/t:.0f}%, care={100*care/t:.0f}%')
"
```

Critério de aceite: price ≥50%, care_usage ≥30%, INCI mantido (não cair).
Se falhar, restaurar do backup: `cp haira.db.bak.20260503_pre_<slug>_no_js haira.db`.

- [ ] **Step 7: Rodar labels + classify**

```bash
source .venv/bin/activate && export $(grep -v '^#' .env | xargs) && \
PYTHONPATH=. python -m src.cli.main labels --brand <slug> 2>&1 | tail -10 && \
PYTHONPATH=. python -m src.cli.main classify --brand <slug> 2>&1 | tail -10
```

Expected: relatórios saem sem erro.

### Task 1.3: Commit Fase 1

- [ ] **Step 1: Stage blueprints alterados**

```bash
git status --short
git add config/blueprints/{keune,amend,inoar}.yaml  # apenas as candidatas confirmadas
```

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(blueprints): <list> requires_js=false

Mesmo padrão Hidratei/Alva/Joico — sites SSR-rendered onde
expand_accordions=true degradava o DOM final.

Coverage final por marca:
  - <slug>: price X%->Y%, care Z%->W%, INCI mantido em N%
  ...
EOF
)"
```

Expected: commit limpo. Não push ainda (push agrupado na Fase 7).

---

## Fase 2 — Labels apice/beleza-natural (sem re-scrape pesado)

**Hipótese:** apice (670 produtos, care 3%) e beleza-natural (365, care 1%) têm o conteúdo no DOM mas labels do blueprint não casam. Adicionar labels resolve ANTES de re-scrape.

### Task 2.1: Inspecionar DOM apice + beleza-natural

- [ ] **Step 1: Pegar 1 URL produto individual de cada**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
for slug in ['apice-cosmeticos','beleza-natural']:
    c.execute('''SELECT product_url FROM products WHERE brand_slug=?
                 AND product_name LIKE \"%hampoo%\" AND product_name NOT LIKE \"%Kit%\"
                 LIMIT 1''', (slug,))
    row = c.fetchone()
    print(f'{slug}: {row[0] if row else None}')
"
```

Expected: 1 URL por marca.

- [ ] **Step 2: Inspecionar headings (h2/h3/h4) das páginas**

Para cada URL:
```bash
source .venv/bin/activate && python << 'PY'
import httpx, re
url = '<URL>'
r = httpx.get(url, follow_redirects=True, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
print(f'HTTP {r.status_code}, len={len(r.text)}')
seen=set()
for tag in ['h2','h3','h4','strong','dt']:
    for m in re.finditer(rf'<{tag}[^>]*>(.*?)</{tag}>', r.text, re.I|re.S):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and len(text) < 80 and text not in seen:
            seen.add(text)
            print(f'  <{tag}> {text!r}')
PY
```

Expected: lista de headings reais do site.

- [ ] **Step 3: Comparar com section_label_map atual de cada blueprint**

```bash
grep -A 30 "section_label_map" config/blueprints/apice-cosmeticos.yaml | head -40
echo "---"
grep -A 30 "section_label_map" config/blueprints/beleza-natural.yaml | head -40
```

Identificar headings reais que NÃO estão no blueprint (ex: "Modo de Aplicação", "Ingredientes Ativos", "Resultados", etc).

### Task 2.2: Adicionar labels nos blueprints

Para cada slug:

- [ ] **Step 1: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_<slug>_labels
```

- [ ] **Step 2: Editar blueprint adicionando labels novos**

Edit `config/blueprints/<slug>.yaml` na seção `section_label_map:` — adicionar labels descobertos em Task 2.1 Step 3.

Exemplo (apice):
```yaml
care_usage:
  labels:
  - como usar
  - modo de uso
  - "modo de aplica\xE7\xE3o"   # NOVO
  - "indica\xE7\xE3o de uso"      # NOVO
```

- [ ] **Step 3: Re-scrape em background**

```bash
source .venv/bin/activate && export $(grep -v '^#' .env | xargs) && \
PYTHONPATH=. python -m src.cli.main scrape --brand <slug> 2>&1 | \
  tee logs/<slug>_labels_$(date +%H%M%S).log
```

Run via `run_in_background: true`.

- [ ] **Step 4: Cleanup + verificar coverage** (mesmas queries da Fase 1 Steps 5-6)

Critério: care_usage ≥30% (apice meta: ≥40%; beleza-natural meta: ≥40%).

- [ ] **Step 5: Labels + classify**

```bash
source .venv/bin/activate && export $(grep -v '^#' .env | xargs) && \
PYTHONPATH=. python -m src.cli.main labels --brand <slug> 2>&1 | tail -8 && \
PYTHONPATH=. python -m src.cli.main classify --brand <slug> 2>&1 | tail -8
```

### Task 2.3: Commit Fase 2

- [ ] **Step 1: Stage blueprints**

```bash
git add config/blueprints/{apice-cosmeticos,beleza-natural}.yaml
```

- [ ] **Step 2: Commit**

```bash
git commit -m "fix(blueprints): apice + beleza-natural section labels

care_usage subiu de X% para Y% / Z%->W%, sem mudança em requires_js.
Labels adicionados: <list>"
```

---

## Fase 3 — Salon-line custom (occ_api investigation)

**Contexto:** salon-line tem 792 produtos, INCI 97% mas price 0% / care 0%. Blueprint usa `occ_api` (Oracle Commerce Cloud) + Chakra UI. Dois caminhos possíveis: (A) conserto do occ_api fallback, (B) ajuste de selectors DOM.

### Task 3.1: Diagnosticar problema de price/care

- [ ] **Step 1: Verificar se occ_api está sendo chamado no scraper atual**

```bash
grep -rn "occ_api\|occ_API\|salon-line" src/ --include="*.py" | head -10
```

Identificar se há código que usa o `occ_api` config no blueprint, ou se ele é ignorado.

- [ ] **Step 2: Pegar URL sample de produto e inspecionar DOM**

```bash
source .venv/bin/activate && python << 'PY'
import sqlite3, httpx, re
c = sqlite3.connect('haira.db').cursor()
c.execute("SELECT product_url FROM products WHERE brand_slug='salon-line' LIMIT 1")
url = c.fetchone()[0]
r = httpx.get(url, follow_redirects=True, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
print(f'URL: {url}')
print(f'HTTP {r.status_code}, len={len(r.text)}')

# Price markers
for pat in [r'R\$\s*\d', r'price-current', r'product-price', r'sale-price', r'data-price']:
    cnt = len(re.findall(pat, r.text, re.I))
    if cnt: print(f'  {pat!r}: {cnt}')

# Headings
seen=set()
for tag in ['h2','h3','h4']:
    for m in re.finditer(rf'<{tag}[^>]*>(.*?)</{tag}>', r.text, re.I|re.S):
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if text and len(text) < 80 and text not in seen:
            seen.add(text)
            print(f'  <{tag}> {text!r}')
PY
```

Expected: ver se DOM tem price markers e quais headings reais existem.

- [ ] **Step 3: Decidir abordagem**

Se DOM tem price markers visíveis (R$ X,YY) → ajustar `price_selectors` no blueprint.
Se headings ETAPAS DE USO/PRINCIPAIS ATIVOS já estão no blueprint mas extraction falha → debug `extract_by_selectors` ou wait_for_selector.

Documentar decisão.

### Task 3.2: Aplicar fix salon-line

- [ ] **Step 1: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_salonline_fix
```

- [ ] **Step 2: Aplicar fix decidido em Task 3.1 Step 3**

Edit `config/blueprints/salon-line.yaml` — adicionar/ajustar selectors conforme diagnóstico.

- [ ] **Step 3: Testar em 3 URLs sample antes do re-scrape completo**

```bash
source .venv/bin/activate && PYTHONPATH=. python << 'PY'
# Igual Task 1.1 Step 3 mas com 3 URLs salon-line
PY
```

Critério: price capturado em ≥2/3, care_usage capturado em ≥2/3.
Se falhar, ajustar e repetir. Se passar, ir Step 4.

- [ ] **Step 4: Re-scrape completo (background — pode demorar 30-60min)**

```bash
source .venv/bin/activate && export $(grep -v '^#' .env | xargs) && \
PYTHONPATH=. python -m src.cli.main scrape --brand salon-line 2>&1 | \
  tee logs/salon-line_fix_$(date +%H%M%S).log
```

- [ ] **Step 5: Cleanup + coverage check + labels + classify** (mesmas queries da Fase 1)

Critério: price ≥70%, care_usage ≥40%, INCI mantido em ≥90%.

### Task 3.3: Commit Fase 3

- [ ] **Step 1: Commit**

```bash
git add config/blueprints/salon-line.yaml
git commit -m "fix(blueprint): salon-line — <descrever fix>

price 0% -> X%, care 0% -> Y%, INCI mantido em Z%."
```

---

## Fase 4 — INCI gaps widi-care + arvensis

**Contexto:** widi-care (291, INCI 20%) e arvensis (188, INCI 3%). Care_usage 71% / 31% — sites podem funcionar mas captura INCI específica falha. Investigar se INCI está disponível mas em formato diferente.

### Task 4.1: Diagnosticar widi-care

- [ ] **Step 1: Pegar produto widi-care com INCI presente E sem INCI no banco**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
print('=== Sem INCI ===')
c.execute('''SELECT product_url, product_name FROM products WHERE brand_slug=\"widi-care\"
              AND (inci_ingredients IS NULL OR inci_ingredients=\"[]\" OR inci_ingredients=\"null\")
              AND product_name LIKE \"%hampoo%\" LIMIT 2''')
for r in c.fetchall(): print(r)
print('=== Com INCI ===')
c.execute('''SELECT product_url, product_name FROM products WHERE brand_slug=\"widi-care\"
              AND inci_ingredients IS NOT NULL AND inci_ingredients != \"[]\"
              AND product_name LIKE \"%hampoo%\" LIMIT 2''')
for r in c.fetchall(): print(r)
"
```

- [ ] **Step 2: Comparar DOM dos 2 (com vs sem INCI)**

Para cada URL, fetch + buscar palavra "INCI" e accordions com "Composição"/"Ingredientes":

```bash
source .venv/bin/activate && python << 'PY'
import httpx, re
URLS_NO_INCI = ['<URL>', '<URL>']
URLS_WITH_INCI = ['<URL>', '<URL>']
for tag, urls in [('SEM INCI', URLS_NO_INCI), ('COM INCI', URLS_WITH_INCI)]:
    print(f'\n=== {tag} ===')
    for url in urls:
        r = httpx.get(url, follow_redirects=True, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
        print(f'\n{url}: HTTP {r.status_code}, len={len(r.text)}')
        # Encontrar o trecho com INCI/Composição
        for kw in ['INCI', 'Composição', 'Ingredientes']:
            positions = [m.start() for m in re.finditer(kw, r.text)]
            print(f'  {kw}: {len(positions)} matches')
            for pos in positions[:2]:
                snippet = re.sub(r'<[^>]+>', ' ', r.text[max(0,pos-30):pos+200])
                snippet = re.sub(r'\s+', ' ', snippet)[:250]
                print(f'    pos {pos}: {snippet!r}')
PY
```

Expected: identificar diferença estrutural entre páginas com vs sem INCI.

- [ ] **Step 3: Decidir se é fix de blueprint ou gap fundamental**

Se INCI presente nas páginas "sem INCI" mas extractor falha → fix selectors/labels.
Se realmente ausente → documentar como gap (alguns produtos widi-care não publicam).

### Task 4.2: Mesma investigação para arvensis

Mesmas etapas que Task 4.1, com arvensis. Decidir fix vs skip.

### Task 4.3: Aplicar fixes (se houver)

Para cada slug com fix decidido:

- [ ] **Step 1-7:** Mesmo fluxo da Fase 1 Task 1.2 (backup, edit, re-scrape, cleanup, coverage, labels, classify, commit).

### Task 4.4: Commit Fase 4

```bash
git add config/blueprints/{widi-care,arvensis}.yaml  # apenas mudados
git commit -m "fix(blueprints): widi-care + arvensis INCI extraction

INCI subiu de X%/Y% para A%/B%."
```

---

## Fase 5 — Cleanup classificação Eudora + o-Boticário

**Contexto:** Eudora 1415 produtos, INCI 49% — mas 96% INCI nos hair-only individuais. Gap real é kits (esperados sem INCI individual) + produtos não-hair classificados como hair (cílios, perfumes, cremes faciais). Mesma situação em o-Boticário (1836).

### Task 5.1: Identificar critérios de filtragem não-hair

- [ ] **Step 1: Listar produtos suspeitos de não-hair**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
# Padrões claros de não-hair
patterns = ['%base %','%batom%','%blush%','%lápis %','%lapis %','%esmalte%','%perfume%',
            '%colônia%','%colonia%','%eau de%','%body splash%','%protetor solar%',
            '%hidratante facial%','%creme facial%','%sérum facial%','%serum facial%',
            '%cílios%','%cilios%','%rímel%','%rimel%','%sombra%','%delineador%',
            '%desodorante%','%antitranspirante%','%depilatório%','%depilatorio%']
print('=== Eudora não-hair candidatos ===')
total_eudora_nh = 0
for p in patterns:
    c.execute(f'''SELECT COUNT(*) FROM products WHERE brand_slug=\"eudora\" AND product_name LIKE ? COLLATE NOCASE''', (p,))
    n = c.fetchone()[0]
    if n: print(f'  {p!r}: {n}')
    total_eudora_nh += n
print(f'  TOTAL: ~{total_eudora_nh}')

print()
print('=== o-Boticario não-hair candidatos ===')
total_obot_nh = 0
for p in patterns:
    c.execute(f'''SELECT COUNT(*) FROM products WHERE brand_slug=\"o-boticario\" AND product_name LIKE ? COLLATE NOCASE''', (p,))
    n = c.fetchone()[0]
    if n: print(f'  {p!r}: {n}')
    total_obot_nh += n
print(f'  TOTAL: ~{total_obot_nh}')
"
```

Expected: ver quantos produtos cabem em cada padrão (não-hair claro).

### Task 5.2: Criar script de cleanup classificação

**Files:**
- Create: `scripts/cleanup_non_hair_products.py`

- [ ] **Step 1: Escrever script (com --dry-run obrigatório)**

```python
"""Mark or remove products that are clearly non-hair based on product_name patterns.

Default mode: marks `hair_relevance_reason='non_hair_by_name'` (soft).
With --delete: hard-deletes (with cascade).

Usage:
  python scripts/cleanup_non_hair_products.py --dry-run [brand_slug ...]
  python scripts/cleanup_non_hair_products.py [brand_slug ...]
  python scripts/cleanup_non_hair_products.py --delete [brand_slug ...]
"""
from __future__ import annotations
import sqlite3
import sys

DB = "haira.db"

NON_HAIR_PATTERNS = [
    "base ", "batom", "blush", "lápis ", "lapis ", "esmalte", "perfume",
    "colônia", "colonia", "eau de", "body splash", "protetor solar",
    "hidratante facial", "creme facial", "sérum facial", "serum facial",
    "cílios", "cilios", "rímel", "rimel", "sombra", "delineador",
    "desodorante", "antitranspirante", "depilatório", "depilatorio",
]

CHILD_TABLES = (
    "product_evidence", "quarantine_details", "validation_comparisons",
    "review_queue", "product_images", "product_claims", "product_compositions",
    "product_ingredients", "enrichment_queue",
)


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    delete_mode = "--delete" in args
    brands = [a for a in args if not a.startswith("--")]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    where_brand = ""
    params = []
    if brands:
        where_brand = f"AND brand_slug IN ({','.join('?' for _ in brands)})"
        params = brands

    pattern_ors = " OR ".join("LOWER(product_name) LIKE ?" for _ in NON_HAIR_PATTERNS)
    sql = f"""SELECT id, brand_slug, product_name FROM products
              WHERE ({pattern_ors}) {where_brand}"""
    c.execute(sql, [f"%{p}%" for p in NON_HAIR_PATTERNS] + params)
    rows = c.fetchall()
    print(f"Matched {len(rows)} products as non-hair")

    by_brand = {}
    for _, slug, _ in rows:
        by_brand[slug] = by_brand.get(slug, 0) + 1
    for slug, n in sorted(by_brand.items(), key=lambda x: -x[1])[:15]:
        print(f"  {slug}: {n}")

    if dry_run:
        print("DRY-RUN, no changes")
        return

    ids = [r[0] for r in rows]
    if delete_mode:
        for tbl in CHILD_TABLES:
            placeholders = ",".join("?" for _ in ids)
            try:
                c.execute(f"DELETE FROM {tbl} WHERE product_id IN ({placeholders})", ids)
            except sqlite3.OperationalError:
                pass
        c.execute(f"DELETE FROM products WHERE id IN ({','.join('?' for _ in ids)})", ids)
        print(f"Deleted {len(ids)} products + cascade")
    else:
        c.execute(
            f"UPDATE products SET hair_relevance_reason='non_hair_by_name' WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
        print(f"Marked {len(ids)} products as non_hair_by_name")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
```

Save to `scripts/cleanup_non_hair_products.py`.

- [ ] **Step 2: Dry-run em todas as marcas para ver impacto**

```bash
source .venv/bin/activate && python scripts/cleanup_non_hair_products.py --dry-run
```

Expected: ver totais e top brands afetados.

- [ ] **Step 3: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_nonhair_cleanup
```

- [ ] **Step 4: Aplicar em modo soft (mark, não delete)**

```bash
source .venv/bin/activate && python scripts/cleanup_non_hair_products.py
```

Expected: relatório de marcados.

- [ ] **Step 5: Validar coverage hair-only**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
c.execute('''SELECT COUNT(*),
    SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != \"[]\" AND inci_ingredients != \"null\" THEN 1 ELSE 0 END)
    FROM products WHERE hair_relevance_reason != \"non_hair_by_name\" OR hair_relevance_reason IS NULL''')
total, inci = c.fetchone()
print(f'Hair-only: total={total}, INCI={100*inci/total:.1f}%')
"
```

Critério: INCI hair-only ≥65% (vs 54% atual mistura).

### Task 5.3: Commit Fase 5

```bash
git add scripts/cleanup_non_hair_products.py
git commit -m "feat: add scripts/cleanup_non_hair_products.py

Marks products as non_hair_by_name (Eudora/o-Boticario etc) so coverage
metrics reflect hair-only universe."
```

---

## Fase 6 — Auto-resolve review queue final

**Contexto:** 149 pending após fixes anteriores. Aplicar 5 layers + análise final.

### Task 6.1: Rodar 5 layers de auto-resolve

- [ ] **Step 1: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_final_autoresolve
```

- [ ] **Step 2: Layer 1 — current ≠ pass_1**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/autoresolve_review_queue.py
```

- [ ] **Step 3: Layer 2 — INCI multilang**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/autoresolve_inci_multilang.py
```

- [ ] **Step 4: Layer 3 — text whitespace**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/autoresolve_text_whitespace.py
```

- [ ] **Step 5: Layer 4 — accept Pass 2 when empty**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/autoresolve_accept_pass2_when_empty.py
```

- [ ] **Step 6: Layer Dedupe**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/autoresolve_dedupe_review.py
```

- [ ] **Step 7: Layer 5 — text longer wins**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/autoresolve_text_longer_wins.py
```

- [ ] **Step 8: Verificar pending final**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
c.execute('SELECT status, COUNT(*) FROM review_queue GROUP BY status')
for row in c.fetchall(): print(row)
"
```

Critério: pending <50.

### Task 6.2: Análise dos pending restantes

- [ ] **Step 1: Listar pending por brand+field**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
c.execute('''SELECT p.brand_slug, rq.field_name, COUNT(*) FROM review_queue rq
              JOIN products p ON rq.product_id = p.id
              WHERE rq.status=\"pending\"
              GROUP BY p.brand_slug, rq.field_name
              ORDER BY 3 DESC''')
for row in c.fetchall(): print(f'  {row[0]:25s} {row[1]:25s} {row[2]}')
"
```

- [ ] **Step 2: Documentar restantes como divergências legítimas**

Os <50 finais são divergências reais que precisam:
- Revisão humana via UI `/ops/dual-validation`, OU
- Aceitar como steady-state.

Atualizar memory com a interpretação.

---

## Fase 7 — Diagnóstico final + commit + deploy + memory

### Task 7.1: Coverage final consolidado

- [ ] **Step 1: Gerar relatório completo**

```bash
source .venv/bin/activate && python << 'PY'
import sqlite3
c = sqlite3.connect('haira.db').cursor()

print('=== COVERAGE FINAL ===')
c.execute('''SELECT COUNT(*),
    SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != "[]" AND inci_ingredients != "null" THEN 1 ELSE 0 END),
    SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END),
    SUM(CASE WHEN care_usage IS NOT NULL AND care_usage != "" THEN 1 ELSE 0 END),
    SUM(CASE WHEN description IS NOT NULL AND description != "" THEN 1 ELSE 0 END)
    FROM products''')
t,i,p,care,d = c.fetchone()
print(f'Total: {t:,}')
print(f'  INCI: {i:,} ({100*i/t:.1f}%)')
print(f'  Price: {p:,} ({100*p/t:.1f}%)')
print(f'  Care: {care:,} ({100*care/t:.1f}%)')
print(f'  Desc: {d:,} ({100*d/t:.1f}%)')

print('\n=== HAIR-ONLY (excluindo non_hair_by_name) ===')
c.execute('''SELECT COUNT(*),
    SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != "[]" AND inci_ingredients != "null" THEN 1 ELSE 0 END),
    SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END),
    SUM(CASE WHEN care_usage IS NOT NULL AND care_usage != "" THEN 1 ELSE 0 END)
    FROM products WHERE hair_relevance_reason != "non_hair_by_name" OR hair_relevance_reason IS NULL''')
t,i,p,care = c.fetchone()
print(f'Total hair: {t:,}')
print(f'  INCI: {i:,} ({100*i/t:.1f}%)')
print(f'  Price: {p:,} ({100*p/t:.1f}%)')
print(f'  Care: {care:,} ({100*care/t:.1f}%)')

print('\n=== MARCAS POR COVERAGE FINAL ===')
c.execute('''SELECT brand_slug, COUNT(*) total,
    100.0*SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != "[]" AND inci_ingredients != "null" THEN 1 ELSE 0 END)/COUNT(*) inci,
    100.0*SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END)/COUNT(*) price,
    100.0*SUM(CASE WHEN care_usage IS NOT NULL AND care_usage != "" THEN 1 ELSE 0 END)/COUNT(*) care
    FROM products GROUP BY brand_slug ORDER BY total DESC''')
for r in c.fetchall():
    print(f'  {r[0]:25s} total={r[1]:5d} INCI={r[2]:3.0f}% price={r[3]:3.0f}% care={r[4]:3.0f}%')
PY
```

Expected: comparar contra targets.

### Task 7.2: Comparar contra targets

- [ ] **Step 1: Avaliar metas**

| Métrica | Meta | Atingido? |
|---------|------|-----------|
| INCI hair-only ≥80% | 80% | <preencher> |
| Price geral ≥90% | 90% | <preencher> |
| care_usage ≥60% | 60% | <preencher> |
| Pending review <50 | 50 | <preencher> |

Para cada meta não-atingida, decidir se: (a) é gap fundamental documentado, (b) precisa nova fase, (c) aceitar shortfall.

### Task 7.3: Push + deploy

- [ ] **Step 1: Verificar commits acumulados**

```bash
git log --oneline origin/master..HEAD
```

Expected: lista dos commits feitos nas Fases 1-6.

- [ ] **Step 2: Rodar testes**

```bash
source .venv/bin/activate && pytest tests/ --deselect tests/api/test_api.py::TestBrandsEndpoint::test_list_empty 2>&1 | tail -5
```

Expected: ≤7 testes preexistentes falhando, 400+ passando. Confirmar nenhum dos meus commits introduziu regressão.

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build 2>&1 | tail -10 && cd ..
```

Expected: "✓ built in Xs". Sem erros.

- [ ] **Step 4: Push origin master**

```bash
git push origin master
```

Expected: `commits ahead -> X commits pushed`.

- [ ] **Step 5: Pedir autorização explícita do usuário antes de deploy Railway**

```
Aguardar resposta do usuário com "SIM" ou "deploy" ou "autorizado"
antes de prosseguir. Deploy é shared system production.
```

- [ ] **Step 6: Após autorização — Deploy Railway**

```bash
railway up --detach
```

- [ ] **Step 7: Monitor deploy + healthcheck**

```bash
# Use Monitor para railway status até SUCCESS/FAILED
# Após SUCCESS:
curl -s -o /dev/null -w "%{http_code}\n" https://haira-app-production-deb8.up.railway.app/health
```

Expected: `200`.

### Task 7.4: Atualizar memory

- [ ] **Step 1: Adicionar ao [project_session_2026_05_03.md](memory/project_session_2026_05_03.md)**

Adicionar seção "Update parte 12 — Fechamento Coverage 47 Marcas":
- Coverage final hair-only (INCI/price/care/desc %)
- Marcas resolvidas vs gap fundamental (lista atualizada)
- Pending review final
- Commits finais
- Backups da fase

- [ ] **Step 2: Atualizar MEMORY.md** se aplicável

Adicionar entrada se houver mudança estrutural significativa.

### Task 7.5: Commit final + arquivar plano

- [ ] **Step 1: Commit dos blueprints, scripts e plano**

```bash
git add docs/superpowers/plans/2026-05-03-fechamento-coverage-47-marcas.md
git commit -m "docs(plans): fechamento coverage 47 marcas — completed

Coverage final hair-only:
  - INCI:  X% (meta: 80%)
  - Price: Y% (meta: 90%)
  - Care:  Z% (meta: 60%)
  - Pending review: N (meta: <50)"
```

---

## Self-Review

**Spec coverage:**
- ✅ Audit requires_js (Fase 1) cobre keune/amend/inoar
- ✅ Labels ajuste (Fase 2) cobre apice/beleza-natural
- ✅ Salon-line custom (Fase 3) — investigação + fix
- ✅ INCI gaps (Fase 4) — widi-care/arvensis
- ✅ Cleanup classificação (Fase 5) — Eudora/o-Boticário
- ✅ Auto-resolve review queue (Fase 6) — 5 layers
- ✅ Commit + deploy + memory (Fase 7)

**Backups:** cada fase destrutiva tem backup explícito.

**Critérios de aceite:** cada Task com fix tem `Critério: ...` antes de seguir. Permite abortar se sample falhar.

**Estimativa total:**
- Fase 1: 30-60min (3 marcas, mas re-scrapes podem ser paralelos)
- Fase 2: 30-45min
- Fase 3: 1-3h (salon-line é a mais incerta)
- Fase 4: 30-60min
- Fase 5: 30min (script + dry-run + apply)
- Fase 6: 10min
- Fase 7: 30-60min (build + push + deploy + memory)
- **Total: 4-7h** distribuíveis em 1-2 sessões

**Marcas que ficam fora do alvo de re-scrape direto (gap fundamental documentado):**
- brae, bio-extratus, griffus, haskell, elseve, aneethun, loccitane, natura, wella (regex URL bug — fora deste plano), granado (SPA real — fora). Estas vão para Track C (source-scrape) na Fase 11.

---

# Track B — Onboarding marcas pendentes (Fases 8-10)

## Fase 8 — Triagem das 645 marcas pendentes

**Hipótese:** das 645 pendentes, ~50-100 têm site próprio scrapeável (Shopify/VTEX/Wake reconhecíveis), o resto são marcas regionais/profissionais sem site — vão para Track C.

### Task 8.1: Auto-classify viabilidade

**Files:**
- Create: `scripts/triage_pending_brands.py`

- [ ] **Step 1: Escrever script de triagem**

```python
"""Triage pending brands from brands.json — classify each by viability for direct scrape.

For each brand without products in DB:
  1. Probe official_url_root with httpx (HEAD or GET, follow redirects, 10s timeout)
  2. Detect platform from response headers/HTML markers (Shopify, VTEX, Wake, custom, etc)
  3. Check sitemap.xml availability
  4. Assign tier:
     - tier_1_easy: known platform + sitemap OK + INCI flag=sim or unknown
     - tier_2_check: known platform + sitemap OK but INCI flag=não
     - tier_3_custom: site responds but no recognized platform
     - tier_4_no_site: domain dead or no useful response → Track C
     - tier_skip: status=blocked/blocked_maintenance

Output: writes config/brands_triage.json with {brand_slug, tier, platform_guess, notes}.
"""
# Implementation: ~80 lines. Each brand probed ~5s, total ~600s for 645 brands (parallel: 60s).
# Use httpx.AsyncClient with semaphore=10.
```

- [ ] **Step 2: Rodar triagem (background, ~10min)**

```bash
source .venv/bin/activate && PYTHONPATH=. python scripts/triage_pending_brands.py
```

Expected: gera `config/brands_triage.json`.

- [ ] **Step 3: Análise da triagem**

```bash
source .venv/bin/activate && python -c "
import json
with open('config/brands_triage.json') as f:
    t = json.load(f)
from collections import Counter
print('Tiers:', Counter(b['tier'] for b in t))
print('Platforms:', Counter(b.get('platform_guess','?') for b in t))
print()
print('Tier 1 (high-confidence direct scrape):')
for b in t:
    if b['tier']=='tier_1_easy': print(f'  {b[\"brand_slug\"]:25s} {b.get(\"platform_guess\",\"?\")}')
"
```

Critério: tier_1_easy ≥30 marcas para justificar Fase 9.

### Task 8.2: Commit triagem

- [ ] **Step 1: Commit script + resultado**

```bash
git add scripts/triage_pending_brands.py config/brands_triage.json
git commit -m "feat: triage pending brands — classify 645 brands by scrape viability

Tier 1 (direct scrape): N brands
Tier 2 (catalog only): M brands
Tier 3 (custom platform): K brands
Tier 4 (no site): J brands → Track C source-scrape"
```

---

## Fase 9 — Onboarding em wave: tier_1_easy

**Estratégia:** despachar agente `brand-onboarding` em paralelo (waves de 5-10 marcas) para tier_1_easy. Cada agente cria blueprint + roda discovery + scrape inicial.

### Task 9.1: Wave 1 — primeiras 10 marcas tier_1_easy

- [ ] **Step 1: Listar 10 primeiras tier_1**

```bash
source .venv/bin/activate && python -c "
import json
with open('config/brands_triage.json') as f:
    t = json.load(f)
tier1 = [b for b in t if b['tier']=='tier_1_easy']
print(f'Total tier_1: {len(tier1)}')
print('Wave 1 (10 primeiras):')
for b in tier1[:10]:
    print(f'  {b[\"brand_slug\"]} platform={b.get(\"platform_guess\")} url={b.get(\"official_url_root\",\"\")}')
"
```

- [ ] **Step 2: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_wave1
```

- [ ] **Step 3: Despachar `brand-onboarding` agent para cada uma das 10**

Use Agent tool com `subagent_type: brand-onboarding` para cada marca. Despache em paralelo (10 simultâneos). Prompt template:

```
Onboard a marca <SLUG> ao HAIRA. Dados:
- brand_name: <NAME>
- official_url_root: <URL>
- platform_guess: <PLATFORM>
- INCI flag: <yes/no/unknown>

Tarefas:
1. Criar config/blueprints/<SLUG>.yaml com platform=<PLATFORM>, sitemap_urls inferido, product_url_pattern
2. Rodar haira scrape --brand <SLUG>
3. Cleanup non-product URLs
4. Rodar haira labels + classify
5. Reportar coverage final (total produtos, INCI%, price%)

Critério de sucesso: ≥10 produtos extraídos OU diagnostico claro de por que não.
Retornar: relatório curto com coverage atingido ou justificativa de falha.
```

- [ ] **Step 4: Coletar resultados das 10 waves**

Após todos retornarem, analisar:
- Quais tiveram sucesso (≥10 produtos)
- Quais falharam e razões (atualizar tier no triage)

- [ ] **Step 5: Commit + verificar coverage**

```bash
git status
git add config/blueprints/*.yaml
git commit -m "feat: onboard wave 1 — N novas marcas via brand-onboarding agent"
```

### Task 9.2: Iterar waves até esgotar tier_1_easy

- [ ] **Steps:** Repetir Task 9.1 em waves de 10 até tier_1_easy esgotar. Cada wave = 1 commit.

Critério final: tier_1_easy processado, ≥30 novas marcas com ≥10 produtos cada.

### Task 9.3: Wave tier_2 e tier_3 (revisão manual)

- [ ] **Steps:** Tier_2 (catalog_only no site) e tier_3 (custom platforms) requerem investigação manual. Para cada uma, decidir:
- Rodar `brand-onboarding` mesmo (catalog_only) → produtos sem INCI no banco
- Mover para Track C (source-scrape)
- Marcar como inviável

Despachar `brand-onboarding` em waves menores (5 por vez) com instrução de aceitar `catalog_only` como sucesso.

---

## Fase 10 — Validação Track B

### Task 10.1: Coverage report Track B

- [ ] **Step 1: Estatísticas**

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
c.execute('SELECT COUNT(DISTINCT brand_slug), COUNT(*) FROM products')
brands, products = c.fetchone()
print(f'Marcas no banco: {brands}, produtos: {products}')
c.execute('''SELECT brand_slug, COUNT(*) FROM products
              GROUP BY brand_slug HAVING COUNT(*) >= 10
              ORDER BY 2''')
ge10 = c.fetchall()
print(f'Marcas com >= 10 produtos: {len(ge10)}')
c.execute('''SELECT brand_slug, COUNT(*) FROM products
              GROUP BY brand_slug HAVING COUNT(*) < 10''')
lt10 = c.fetchall()
print(f'Marcas com < 10 produtos: {len(lt10)}')
"
```

- [ ] **Step 2: Atualizar memory com Track B status**

---

# Track C — Source-scrape via distribuidores (Fases 11-12)

## Fase 11 — Source-scrape em batch

**Estratégia:** para marcas tier_4 + gap fundamental, usar `inci-enricher` agent que orquestra source-scrape de Beleza na Web e Época Cosméticos. Cada marca = ~5-50 produtos extraídos via distribuidor.

### Task 11.1: Wave 1 — 20 marcas tier_4 + gap fundamental

- [ ] **Step 1: Listar candidatas**

```bash
source .venv/bin/activate && python -c "
import json
with open('config/brands_triage.json') as f:
    t = json.load(f)
tier4 = [b for b in t if b['tier']=='tier_4_no_site']
gap_fundamental = ['brae','bio-extratus','griffus','haskell','elseve','aneethun','loccitane']
candidates = tier4 + [{'brand_slug':s, 'tier':'gap_fundamental'} for s in gap_fundamental]
print(f'Total candidatas Track C: {len(candidates)}')
for c in candidates[:20]:
    print(f'  {c[\"brand_slug\"]} ({c[\"tier\"]})')
"
```

- [ ] **Step 2: Despachar `inci-enricher` agent (waves de 10 paralelos)**

Use Agent tool com `subagent_type: inci-enricher`. Prompt template:

```
Enrich INCI para marca <SLUG> usando source-scrape de fontes externas.

Tarefas:
1. Rodar haira source-scrape --brand <SLUG> --source belezanaweb (e --source epocacosmeticos)
2. Match automático por nome/imagem com produtos existentes no banco
3. Para produtos novos não-matchados, criar registros catalog_only com inci_ingredients populado
4. Reportar: produtos atualizados / novos catalog_only / falhas

Critério: ≥5 produtos com INCI adicionado/criado OU justificativa.
```

- [ ] **Step 3: Coletar resultados + commit**

```bash
git add data/source_scrape/  # se houver dados intermediários
git commit -m "feat: source-scrape wave 1 — INCI enrichment N marcas via Beleza/Época"
```

### Task 11.2: Iterar waves até esgotar candidatas

- [ ] **Steps:** Repetir Task 11.1 em waves de 20. Marcas que falham 2x consecutivas → marcar `status='no_source'` em brands.json.

---

## Fase 12 — Auto-resolve final + cleanup global

### Task 12.1: Rodar 5 layers + dedupe em todo o banco

- [ ] **Step 1: Backup banco**

```bash
cp haira.db haira.db.bak.20260503_pre_final_global_cleanup
```

- [ ] **Step 2: Rodar todos os auto-resolves**

```bash
for s in scripts/autoresolve_review_queue.py scripts/autoresolve_inci_multilang.py \
         scripts/autoresolve_text_whitespace.py scripts/autoresolve_accept_pass2_when_empty.py \
         scripts/autoresolve_dedupe_review.py scripts/autoresolve_text_longer_wins.py; do
  echo "=== $s ==="
  source .venv/bin/activate && PYTHONPATH=. python "$s"
done
```

- [ ] **Step 3: Cleanup global de URLs lixo em todas as marcas**

```bash
source .venv/bin/activate && python -c "
import json
with open('config/brands.json') as f:
    bs = json.load(f)
slugs = [b['brand_slug'] for b in bs]
print(' '.join(slugs))
" > /tmp/all_slugs.txt
source .venv/bin/activate && PYTHONPATH=. python scripts/cleanup_non_product_urls.py $(cat /tmp/all_slugs.txt) --dry-run | tail -20
```

Decidir se aplicar com base em volume.

- [ ] **Step 4: Cleanup non-hair global**

```bash
source .venv/bin/activate && python scripts/cleanup_non_hair_products.py --dry-run
# Se aceitável:
source .venv/bin/activate && python scripts/cleanup_non_hair_products.py
```

### Task 12.2: Labels + classify global

- [ ] **Step 1: Despachar 1 subagent que rode labels+classify para todas as marcas**

Tarefa: rodar `haira labels --brand <slug>` e `haira classify --brand <slug>` para cada marca no banco, em sequência. Pode demorar 1-2h.

```bash
source .venv/bin/activate && python -c "
import sqlite3
c = sqlite3.connect('haira.db').cursor()
c.execute('SELECT DISTINCT brand_slug FROM products ORDER BY brand_slug')
for r in c.fetchall(): print(r[0])
" > /tmp/db_slugs.txt
while read slug; do
  source .venv/bin/activate && export $(grep -v '^#' .env | xargs) && \
    PYTHONPATH=. python -m src.cli.main labels --brand "$slug" 2>&1 | tail -3
  PYTHONPATH=. python -m src.cli.main classify --brand "$slug" 2>&1 | tail -3
done < /tmp/db_slugs.txt
```

---

# Track D — Diagnóstico final (Fase 13)

## Fase 13 — Diagnóstico final + commit + deploy + memory

### Task 13.1: Coverage report consolidado

- [ ] **Step 1: Stats globais**

```bash
source .venv/bin/activate && python << 'PY'
import sqlite3, json
c = sqlite3.connect('haira.db').cursor()

with open('config/brands.json') as f:
    brands_total = len(json.load(f))

c.execute('SELECT COUNT(DISTINCT brand_slug), COUNT(*) FROM products')
brands_db, products = c.fetchone()

c.execute('''SELECT brand_slug, COUNT(*) FROM products
              GROUP BY brand_slug HAVING COUNT(*) >= 10''')
ge10 = c.fetchall()

print(f'693 brands target')
print(f'  Marcas no banco: {brands_db} ({100*brands_db/brands_total:.0f}%)')
print(f'  Marcas com >= 10 produtos: {len(ge10)}')
print(f'  Total produtos: {products:,}')

c.execute('''SELECT 
    SUM(CASE WHEN inci_ingredients IS NOT NULL AND inci_ingredients != "[]" AND inci_ingredients != "null" THEN 1 ELSE 0 END),
    SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END),
    SUM(CASE WHEN care_usage IS NOT NULL AND care_usage != "" THEN 1 ELSE 0 END)
    FROM products WHERE hair_relevance_reason != "non_hair_by_name" OR hair_relevance_reason IS NULL''')
i, p, care = c.fetchone()
c.execute('SELECT COUNT(*) FROM products WHERE hair_relevance_reason != "non_hair_by_name" OR hair_relevance_reason IS NULL')
hair_total = c.fetchone()[0]
print(f'\nHair-only ({hair_total:,} produtos):')
print(f'  INCI:  {100*i/hair_total:.1f}%')
print(f'  Price: {100*p/hair_total:.1f}%')
print(f'  Care:  {100*care/hair_total:.1f}%')

c.execute('SELECT status, COUNT(*) FROM review_queue GROUP BY status')
print('\nReview queue:')
for r in c.fetchall(): print(f'  {r[0]}: {r[1]}')
PY
```

- [ ] **Step 2: Comparar contra targets**

| Métrica | Meta | Atingido? |
|---------|------|-----------|
| Marcas com produtos individuais | ≥250 | <preencher> |
| INCI hair-only | ≥80% | <preencher> |
| Price | ≥90% | <preencher> |
| care_usage | ≥60% | <preencher> |
| Pending review | <50 | <preencher> |

### Task 13.2: Push + deploy

- [ ] **Step 1-7:** Mesmo fluxo da Fase 7 antiga (testes, build, push, autorização explícita, deploy, healthcheck).

### Task 13.3: Atualizar memory + plano de manutenção

- [ ] **Step 1: Adicionar resumo final ao project_session_2026_05_03.md**

- [ ] **Step 2: Criar `docs/plans/manutencao-mensal-693-marcas.md`** com:
- Cronograma de re-scrape mensal das marcas top 50
- Source-scrape trimestral para marcas inviáveis sem produtos
- Auto-resolve review queue semanal

- [ ] **Step 3: Commit final**

```bash
git add docs/plans/manutencao-mensal-693-marcas.md
git commit -m "docs(plans): manutenção mensal das 693 marcas"
```

---

## Self-Review (atualizado para 693)

**Spec coverage:**
- ✅ Track A (Fases 1-7) — qualidade nas 47 atuais
- ✅ Track B (Fases 8-10) — onboarding via brand-onboarding agent
- ✅ Track C (Fases 11-12) — source-scrape via inci-enricher agent
- ✅ Track D (Fase 13) — diagnóstico, deploy, memory

**Estimativa total atualizada:**
- Track A (Fases 1-7): 4-7h (atual)
- Fase 8 (triagem): 30-60min (script + análise)
- Fase 9 (Track B onboarding): 1-2 dias (waves paralelas)
- Fase 10: 30min
- Fase 11 (Track C source-scrape): 1-2 dias
- Fase 12 (cleanup global): 2-3h
- Fase 13: 1-2h
- **Total: 3-5 dias** (ativo) + tempo de processamento background

**Trade-offs aceitos:**
- ~50-90 marcas vão ser marcadas `status='no_source'` (sem site E sem distribuidores) — OK como limite duro
- Maioria das ~500 marcas pendentes vai ficar `catalog_only` (sem INCI individual real) — OK porque INCI vem da fonte primária
- Pending review queue pode aumentar inicialmente com nova ondas de validate, mas auto-resolves cuidam

**Plano salvo. Próximo passo é executar Task 1.1 via subagent-driven.**
