# HAIRA v2 — Handoff técnico & operacional (para André)

> **Autor:** Nikollas Sanches (via Claude Code) · **Data:** 2026-06-25
> **Status do projeto:** em produção, ativo · **Objetivo deste doc:** permitir que o André
> assuma o projeto de ponta a ponta (entender, rodar, operar, evoluir) sem depender de ninguém.
>
> Leia a seção **0 (TL;DR)** e a **5 (Bancos de dados)** primeiro — a #5 é onde mora a
> armadilha que mais causou dor de cabeça.

---

## 0. TL;DR (1 minuto)

- **O que é:** plataforma de inteligência de produtos capilares. Robôs raspam e-commerces, extraem
  e validam os produtos (nome, tipo, preço, descrição, **ingredientes/INCI**, modo de uso) e
  alimentam uma IA de recomendação ("Moon").
- **Onde está:** produção no **Railway** (`haira-app`), Postgres. App:
  https://haira-app-production-deb8.up.railway.app
- **Stack:** Python (FastAPI + Click CLI + SQLAlchemy + Alembic) no backend; React 19 + TS + Vite +
  Tailwind no frontend. Tudo num container só (Dockerfile).
- **Tamanho da base (snapshot 01/jun):** ~27 mil produtos, ~22 mil capilares, **~6,7 mil prontos
  para recomendação**. 152 marcas com produtos; ~540 marcas cadastradas ainda não raspadas.
- **Maior gap:** **INCI (fórmula)** — só ~1/3 do catálogo tem ingredientes validados. É o foco do roadmap.
- **Armadilha #1:** produção usa **bancos separados** (`CORE` para usuários, `CATALOG`/`DATABASE_URL`
  para produtos). Vários scripts escrevem no banco errado. Detalhe na seção 5 e 10.

---

## 1. O que é o HAIRA (não-técnico)

HAIRA monta uma **base de dados confiável de produtos capilares brasileiros** para alimentar a
**Moon**, uma assistente de IA que recomenda produtos e rotinas com base na fórmula real (INCI),
no tipo de cabelo e no conhecimento proprietário de especialistas ("Doutoras").

O ciclo de vida de um produto:

1. **Descobrir** a URL do produto no site da marca.
2. **Extrair** os dados (nome, tipo, preço, descrição, ingredientes, modo de uso).
3. **Validar** a qualidade — produto "completo" (com INCI) vs "só catálogo" vs "quarentena".
4. **Enriquecer/etiquetar** — selos (vegano, sem sulfato…), alérgenos, papel na rotina.
5. **Publicar (tier "Gold")** — só o que passa num gate rígido fica visível para a Moon recomendar.

Quem usa: time interno de revisão (Clarisse, Fernanda, Cláudia, Fran, Daniel) via painel de Ops; e
o usuário final via Moon (chat + analisador de produto por foto).

---

## 2. Estado atual da base (números)

> ⚠️ **Frescor:** os números abaixo são do **snapshot de produção de 01/jun/2026**
> (`data/reports/2026-06-01-base-haira.md`). Entre 11–21/jun houve muito trabalho (limpeza de
> não-capilares, tier Gold, enrich de INCI), então os totais já mudaram. Para o número de **hoje**,
> rode o snapshot ao vivo (seção 6) ou regenere o report.

| Métrica | Valor (01/jun) |
|---|---|
| Produtos no banco | 27.093 |
| Capilares relevantes | 22.030 (81%) |
| Não-capilares marcados | 5.063 |
| **Prontos p/ recomendação (Moon)** | **6.710** |
| Status `verified_inci` (com fórmula) | 7.411 (33,6%) |
| Status `catalog_only` (sem fórmula) | 14.224 (64,6%) |
| Status `quarantined` | 395 (1,8%) |
| Marcas com produtos | 152 |
| Marcas cadastradas, sem scrape | ~540 |
| Ingredientes únicos | 24.542 (50% categorizados) |
| Docs de conhecimento (Doutoras) | 4 (~44k tokens) |

**Completude por campo (resposta ao "estão completas?"):**
- ✅ Nome / tipo / preço / descrição → cobertura alta.
- ⚠️ **INCI (fórmula)** → ~1/3. Maior gap. Sites BR raramente publicam fórmula → depende de
  fonte externa (Beleza na Web, Época) ou parceria com a marca.
- ⚠️ **Modo de uso** (`care_usage`) → parcial, sendo preenchido pelo `enrich`.

**Termômetro das 152 marcas ativas:** 14 saudáveis · 14 estáveis · 52 precisam atenção ·
46 sem INCI · 19 críticas · 7 vazias. **28 marcas grandes (100+ produtos) têm <10% de INCI.**
Detalhe por marca: `data/reports/2026-06-01-termometro-marcas.csv`.

---

## 3. Stack & arquitetura

```
Backend  : Python 3.12 · FastAPI · Click (CLI `haira`) · SQLAlchemy · Alembic · BeautifulSoup · Playwright
Frontend : React 19 · TypeScript · Vite · Tailwind 4 · recharts · motion · react-router-dom
LLM      : Anthropic (Claude) — categorização de ingredientes, classificação capilar, Moon
Infra    : Docker (multi-stage) · Railway (Postgres + serviço web) · Alembic migrations
```

Ponto de entrada de tudo está documentado no **`CLAUDE.md`** da raiz (leitura obrigatória — é o
mapa do repo). Design e decisões em `docs/architecture.md` e `docs/plans/`.

**Camadas (separação importante):**
- Pydantic models → `src/core/models.py` (domínio)
- ORM models → `src/storage/orm_models.py` e `src/storage/ops_models.py` (persistência)
- Repository → `src/storage/repository.py` (acesso a dados)
- API → `src/api/` (rotas sob prefixo `/api`)
- CLI → `src/cli/main.py` (entrypoint `haira`)

---

## 4. O pipeline (5 estágios)

Orquestrado por `src/pipeline/coverage_engine.py`. Cada estágio tem um comando CLI:

| # | Estágio | Código | CLI | O que faz |
|---|---|---|---|---|
| 1 | Discovery | `src/discovery/` | `haira blueprint` / `scrape` | acha URLs via sitemap + DOM; blueprints YAML por marca (`config/blueprints/*.yaml`, 233 marcas); adapters VTEX/Shopify/Woo |
| 2 | Extraction | `src/extraction/` | `haira scrape` | extrai via JSON-LD + CSS + fallback BS4; INCI à parte (`inci_extractor.py`) |
| 3 | QA Gate | `src/core/qa_gate.py` | (no scrape) | classifica `verified_inci`/`catalog_only`/`quarantined`; separa não-capilares |
| 4 | Labels | `src/core/label_engine.py` | `haira labels` | selos via keyword (`config/labels/seals.yaml`) + inferência por INCI |
| 5 | **Gold** | `src/core/gold_gate.py` | (orquestrador) | gate rígido de publicação; a Moon só consome `gold_status='gold'` |

**Enrich** (`src/enrichment/`, `scripts/enrich_products.py`): recupera INCI + "como usar" de fontes
externas para fechar o gap do Gold. É a peça-chave do roadmap atual.

Comandos do dia a dia:
```bash
haira registry --input "Lista de Produtos.xlsx"   # importa marcas do Excel → config/brands.json
haira blueprint --brand <slug>                    # gera/testa blueprint
haira scrape --brand <slug>                       # descobre + extrai
haira labels --brand <slug>                       # detecta selos
haira audit --brand <slug>                        # auditoria de qualidade
haira report --brand <slug>                       # relatório
```

---

## 5. Bancos de dados (split) — ⚠️ LEIA COM ATENÇÃO

Produção roda em **modo split**: tabelas diferentes vivem em **bancos diferentes**, resolvidos por
variáveis de ambiente. A cadeia de fallback está documentada em `src/api/dependencies.py` (topo):

| Sessão (API) | Cadeia de resolução | Tabelas |
|---|---|---|
| `get_core_session()` | `CORE_DATABASE_URL` → `CENTRAL_DATABASE_URL` → `DATABASE_URL` | **users**, hair_profiles, moon_*, knowledge_chunks |
| `get_catalog_session()` | `CATALOG_DATABASE_URL` → `DATABASE_URL` → central | **products**, ingredients, brand_registry, coverage |
| `get_audit_session()` | `AUDIT_DATABASE_URL` → `CORE_DATABASE_URL` → `DATABASE_URL` | audit log |

**Em produção hoje:** `CORE_DATABASE_URL` está setada (confirmado 25/jun) e `CENTRAL_DATABASE_URL`
não. Ou seja: **usuários ficam no banco CORE; produtos no `DATABASE_URL` (catalog).** São bancos
distintos.

**O perigo:** a CLI (`haira create-user`/`reset-password`) e os seeds (`scripts/seed_admin.py`,
`scripts/seed_reviewers.py`) usam `get_engine()` de `src/storage/database.py`, que **só olha
`DATABASE_URL`**. Resultado: eles criam/resetam usuários no banco **catalog**, mas o login lê do
**CORE** → o usuário "existe" mas nunca loga.

**Como criar/resetar usuário CORRETAMENTE em produção** (apontando a CLI pro banco CORE):
```bash
railway ssh 'cd /app && export PYTHONPATH=/app && \
  EFF="${CORE_DATABASE_URL:-${CENTRAL_DATABASE_URL:-$DATABASE_URL}}"; \
  DATABASE_URL="$EFF" haira create-user --email <email> --name <Nome> --role admin --promote --password <senha>'
```
Depois confirme batendo no login ao vivo:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://haira-app-production-deb8.up.railway.app/api/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"<email>","password":"<senha>"}'   # espera 200
```

---

## 6. Como rodar localmente

```bash
# Backend (Python 3.12+)
pip install -e ".[dev]"
cp .env.example .env            # preencher ANTHROPIC_API_KEY etc. DATABASE_URL local = sqlite:///haira.db
uvicorn src.api.main:app --reload --port 8000

# Frontend (outro terminal)
cd frontend && npm install && npm run dev      # Vite :5173, faz proxy de /api → :8000
# abrir http://localhost:5173

# Testes (pytest, 57 arquivos)
pytest
pytest --cov=src --cov-report=term-missing

# Snapshot de métricas (gera JSON do estado atual — útil para o "número de hoje")
python scripts/snapshot_baseline.py > data/baselines/$(date +%F)-baseline.json
```

Local usa **SQLite** (`haira.db`) por padrão — banco único, sem o split. O `haira.db` versionado é
pequeno/antigo; não representa produção.

---

## 7. Produção & deploy (Railway)

- **Projeto Railway:** `Haira Data` · **serviço:** `haira-app` · região US East.
- **Deploy:** push na branch `main` do repo `sanchesnikollas/hairaproducts` → Railway builda o
  `Dockerfile` e sobe. `ENTRYPOINT = sh /app/entrypoint.sh`.
- **`entrypoint.sh` faz, em ordem:** pré-check de conexão ao DB → migrations Alembic →
  `seed_admin.py` + `seed_reviewers.py` → `uvicorn ... --workers 2`.
- **CLI/ops em produção:** `railway ssh` (precisa `cd /app && export PYTHONPATH=/app` antes de
  rodar `haira ...`; o shell do ssh não herda o WORKDIR/PYTHONPATH do container).
- **Segredos:** ficam em **Railway → serviço → Variables** (`ANTHROPIC_API_KEY`, `DATABASE_URL`,
  `CORE_DATABASE_URL`, `ADMIN_RESET_KEY`, etc.). Nunca commitar.

Runbooks prontos: `docs/gold-operator-runbook.md`, `docs/audit-runbook.md`.

---

## 8. Operação de usuários & login

- **Login:** `POST /api/auth/login` → retorna JWT. Frontend: tela `Login.tsx`.
- **Trocar senha:** `POST /api/auth/change-password` (autenticado).
- **Criar usuário:** `POST /api/auth/users` (exige admin logado) **ou** CLI `haira create-user`
  (ver seção 5 para o jeito certo em produção).
- **Reset de emergência:** `POST /api/auth/reset-admin` — exige a env `ADMIN_RESET_KEY` (no Railway).
- **Papéis:** `admin` (acesso total) e `reviewer` (revisão/quarentena).

---

## 9. Frontend

React em `frontend/`. Páginas em `frontend/src/pages/`:
`Home`, `Login`, `Dashboard`, `BrandsDashboard`, `BrandPage`, `ProductBrowser`, `ProductDetail`,
`QuarantineReview`, `HairProfileForm`, `MoonChat`, `MoonAnalyzer`, e a pasta `ops/` (painel interno).

- API client tipado: `frontend/src/lib/api.ts` · hook de dados: `frontend/src/hooks/useAPI.ts`
- Tipos devem casar com as respostas da API: `frontend/src/types/api.ts`
- Build: `npm run build` (`tsc -b && vite build`) · lint: `npm run lint`

---

## 10. Armadilhas conhecidas (gotchas)

1. **Split de banco (a grande):** ver seção 5. Usuário criado por seed/CLI cai no banco errado.
   `seed_admin.py` e `seed_reviewers.py` rodam **a cada deploy** contra `DATABASE_URL` (catalog) →
   reviewers seedados (`haira2026`) também não logam pelo mesmo motivo. **Fix recomendado abaixo.**
2. **Migrations no split:** `entrypoint.sh` só roda migrations CORE-aware se `CENTRAL_DATABASE_URL`
   estiver setada. Como hoje só `CORE_DATABASE_URL` está setada, o deploy roda `alembic upgrade head`
   apenas no `DATABASE_URL`. **Verifique que o schema do banco CORE está migrado** antes de assumir.
3. **Coluna JSON no Postgres:** `inci_ingredients` é JSON; `length()` (estilo SQLite) quebra no
   Postgres. Use `verification_status='verified_inci'` como sinal de "tem fórmula", não introspecção
   do JSON. (Commit `0d12f12` corrigiu isso no repo.)
4. **Scrape no servidor:** forçar `headless=True` no container — `headless:false` derruba o
   Playwright no Railway (commit `2271c1a`).
5. **INCI "lixo":** texto de checkout às vezes vaza como INCI → vira erro HARD e cai pra catalog,
   não Gold (commit `ec7d0a4`).
6. **Não-capilares:** padrão das listagens é esconder `non_hair`/`is_hidden`. Ao contar produtos,
   cuidado com o filtro (`repository._apply_filters`).

---

## 11. Roadmap / próximos passos

Backlog **0→100** no Jira, todos filhos do épico-log **HAIRA-143** ("Engenharia & Dados"):

| Ticket | Frente |
|---|---|
| HAIRA-144 | Loop de cobertura |
| HAIRA-145 | Deploy Moon |
| HAIRA-146 | Fixes de INCI |
| HAIRA-147 | Source-scrape (fontes externas de INCI) |
| HAIRA-148 | Cleanup non_hair + quarantined |
| HAIRA-149 | Preço + care_usage (modo de uso) |
| HAIRA-150 | Infra Postgres |
| HAIRA-151 | Aceite 100% + manutenção |
| HAIRA-152 | Onboarding manual tier_2 |

**Prioridade prática (do mais alto impacto):**
1. **Fechar o gap de INCI** — rodar o orquestrador de enrich/source-scrape mirando as 28 marcas
   grandes com <10% de fórmula. Sobe direto o "universo recomendável".
2. **Re-scrape de manutenção** — 19 marcas com catálogo encolhido + 7 ausentes.
3. **Onboarding das ~540 marcas** cadastradas e não raspadas (HAIRA-152, tier_2).
4. **Empurrar `catalog_only` → `gold`** conforme INCI/modo de uso entram.
5. **(Dívida técnica) Corrigir o split de usuários:** CLI e seeds devem resolver o engine de `users`
   com a mesma cadeia do app (`CORE → CENTRAL → DATABASE_URL`) em vez de só `DATABASE_URL`. Fecha a
   armadilha #1 e #10.1 de vez. Bom primeiro PR pro André.

---

## 12. Documentação & relatórios existentes

| Arquivo | Conteúdo |
|---|---|
| `CLAUDE.md` | mapa do repo, comandos, convenções, ecossistema de agentes — **comece aqui** |
| `docs/architecture.md` | arquitetura |
| `docs/gold-operator-runbook.md` | operação do workflow Gold |
| `docs/audit-runbook.md` | auditoria de qualidade |
| `docs/moon-knowledge-base.md` | base de conhecimento da Moon |
| `docs/cloudcode-jira-standard.md` | padrão obrigatório de documentação no Jira |
| `docs/workflow-gold-redesign.md` | redesenho do Gold |
| `docs/plans/*` | designs e planos de implementação (v2, smart-labels, frontend) |
| `data/reports/2026-06-01-base-haira.md` | snapshot da base (este doc usa esses números) |
| `data/reports/2026-06-01-termometro-marcas.csv` | termômetro por marca (status + ação) |

**Agentes do projeto** (em `.claude/agents/`, acionáveis pelo Claude Code): `pipeline-doctor`,
`brand-onboarding`, `data-quality-auditor`, `frontend-reviewer`, `deploy-operator`,
`inci-enricher`, `batch-processor`. Veja o `CLAUDE.md` para quando usar cada um.

---

## 13. Acessos & credenciais

> **Por segurança, senhas não vão neste arquivo versionado.** Elas foram entregues à parte (chat de
> handoff). **André deve trocar no primeiro acesso** (`/api/auth/change-password`) e idealmente ter
> a própria conta admin.

- **App produção:** https://haira-app-production-deb8.up.railway.app
- **Contas admin existentes:** `nikollas@sanches.io`, `admin@haira.com` (ambas validadas ao vivo 25/jun).
- **Railway:** acesso ao projeto `Haira Data` (workspace SANCHES) — pedir convite/permissão.
- **Anthropic API key, DATABASE_URL, CORE_DATABASE_URL, ADMIN_RESET_KEY:** Railway → Variables.
- **Jira:** site `sanchescreative.atlassian.net`, projeto `HAIRA`.

**Sugestão:** criar uma conta admin pro André (`andre@…`) com o comando da seção 5 e ele rotacionar.

---

## 14. Convenção Jira (obrigatório)

Toda atividade técnica vira documentação acionável no Jira (detalhe em
`docs/cloudcode-jira-standard.md`):

- **Frente nova** = tarefa filha de **HAIRA-143**, estrutura completa (Summary, Context, Problem,
  Objective, Technical Scope, Acceptance Criteria, Implementation Plan, Risks, Dependencies, QA,
  Release Notes). Modelo: HAIRA-152.
- **Wave/lote/fix executado** = comentário datado na tarefa (métricas antes/depois + commit hash).
- **Decisão/incidente** = comentário.
- Comentário solto do usuário → converter em ticket estruturado.

Commits: conventional (`feat:`, `fix:`, `chore:`, `docs:`).

---

## 15. Primeiros passos sugeridos pro André

1. Ler `CLAUDE.md` + seções 5 e 10 deste doc.
2. Conseguir acesso ao Railway (`Haira Data`) e ao Jira (`HAIRA`).
3. Subir o projeto localmente (seção 6) e rodar `pytest` (ver o verde).
4. Gerar o **snapshot de hoje** da base e comparar com o de 01/jun (entender o que mudou).
5. Pegar como primeira tarefa o **fix do split de usuários** (seção 11, item 5) — é pequeno,
   bem-delimitado e ensina o sistema de bancos.
6. Confirmar que o schema do banco **CORE** está migrado (armadilha #10.2).
