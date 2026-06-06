# HAIRA v2 — Arquitetura

> Documento operacional. Descreve **o que existe hoje em produção** (06 jun 2026), por que está assim, e onde tocar quando algo mudar.
> Para o backlog vivo, ver Jira HAIRA-143 (épico "Engenharia & Dados").

---

## 1. Visão geral

HAIRA é uma plataforma de inteligência capilar. Coleta produtos de e-commerce, extrai INCI, classifica, e expõe uma assistente (**Moon**) que conversa com usuárias usando esse catálogo + conteúdo proprietário das Doutoras.

```
                ┌──────────────────────────────────┐
                │   haira-app (FastAPI + React)    │
                │   1 container, Railway            │
                └─────────────┬────────────────────┘
                              │ railway.internal (Wireguard, TLS)
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
       ┌─────────┐       ┌──────────┐      ┌────────┐
       │  CORE   │       │ CATALOG  │      │ AUDIT  │  (target state)
       │ 🔴 alta │       │ 🟡 média │      │ 🟢 log │
       └─────────┘       └──────────┘      └────────┘
            │
   ┌────────┴────────────────┐
   │ KB encriptada (AES-GCM) │
   │ Compêndio das Doutoras  │
   └─────────────────────────┘
```

**Stack:**
- Backend: Python 3.12 · FastAPI · SQLAlchemy 2.x · Alembic · Click CLI
- Frontend: React 19 · Vite · Tailwind 4 · servido como static pelo FastAPI
- IA: Anthropic Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) · prompt cache 5 min TTL
- DB: PostgreSQL no Railway (production) · SQLite (dev local)
- Auth: JWT HS256 · bcrypt
- KB encryption: AES-256-GCM (`KB_ENCRYPTION_KEY` env)

**Hospedagem:**
- Railway (tier Pro/Team)
- GitHub: `sanchesnikollas/hairaproducts` (público — nada proprietário no repo)
- Branch principal: `main` (auto-deploy)

---

## 2. Decisão chave: split 3-DB por sensibilidade

A arquitetura quebra o que historicamente seria 1 Postgres em **3 bancos separados por classe de dado**. Não é separação por marca (seria 692 DBs — pesadelo) nem por equipe — é por **requisitos de proteção**.

### 2.1 Tabela das tabelas

| DB | Sensibilidade | Conteúdo | Backup | Pool app |
|---|---|---|---|---|
| **`haira_core`** | 🔴 alta | `users`, `hair_profiles`, `moon_conversations`, `moon_messages`, `moon_feedback`, `moon_config`, `knowledge_chunks` (encriptado), `brand_databases` | PITR 7 dias | 3 + overflow 2 |
| **`haira_catalog`** | 🟡 média | `brand_registry`, `brand_coverage`, `products`, `product_evidence`, `product_images`, `product_compositions`, `quarantine_details`, `ingredients`, `ingredient_aliases`, `product_ingredients`, `ingredient_category_compatibility`, `claims`, `claim_aliases`, `product_claims`, `external_inci`, `enrichment_queue`, `validation_comparisons`, `review_queue` | Daily, 30 dias | 5 + overflow 5 |
| **`haira_audit`** | 🟢 append-only | `revision_history`, `kb_retrieval_log`, `admin_action_log`, `auth_event_log` | Daily, 1 ano | 2 + overflow 1 |

### 2.2 Por que 3 e não 1 (motivos reais, não estética)

| Motivo | Detalhe |
|---|---|
| **Blast radius** | PII (`users`, `hair_profiles`, conversas Moon) e conteúdo proprietário (Compêndio) compartilham backup, criptografia em repouso, retenção. Catalog (público em 90%) tem requisitos diferentes — não merece a mesma proteção custosa. |
| **Performance** | Catalog faz leitura muito pesada (`/api/brands` lista 692 marcas com agregados). Pool 5+5 dedicado evita starvation do core (auth/chat). |
| **Auditoria não-bloqueante** | Audit DB cai → app continua. Logs ficam em fila de retry. Não bloquear request por falha de observabilidade é regra dura. |
| **Compliance futura** | LGPD/GDPR exigem deleção de PII sob pedido. Com core isolado, basta operar 1 DB pequena — não trocar 24k linhas de catalog. |
| **PITR só onde importa** | PITR no core custa ~5×/mês. Em catalog seria desperdício — catalog reconstrói via re-scrape. |

### 2.3 Estado atual (06 jun 2026)

- ✅ **Cutover Core feito** — `CORE_DATABASE_URL` apontando pra Postgres-Core dedicado. 102 linhas migradas com checksum MD5.
- ⏸️ **Catalog + Audit** ainda compartilham `DATABASE_URL` (Postgres-MsGQ legado) por causa de limite de 20 volumes no Railway. Migração programada quando volumes órfãos forem limpos. Ver pendências em HAIRA-143.

### 2.4 Fallback chain (resiliente)

Cada `get_X_session()` em `src/api/dependencies.py` resolve assim:

```
get_core_session()     → _core_engine    OR _resolve_default_engine()
get_catalog_session()  → _catalog_engine OR _resolve_default_engine()
get_audit_session()    → _audit_engine   OR _resolve_default_engine()
_resolve_default_engine() → _router._central_engine OR get_engine() (DATABASE_URL)
```

Setar nenhuma env nova → modo single-DB legacy (funciona). Setar todas → modo split 3-DB. Setar parcial → mistura controlada. Não há big-bang.

---

## 3. Anatomia da Moon

> A IA não é monolítica. Tem **cérebro** (Compêndio = o que sabe) e **órgãos** que servem o cérebro (voz, visão, memória factual, reflexo INCI).

```
┌──────────────────────────────────────────────────────────────┐
│                  🧠 COMPÊNDIO HAIRA                          │
│                  (knowledge_chunks, AES-256)                 │
│                  carregado em prompt cache Anthropic (5 min) │
└────────────────────────┬─────────────────────────────────────┘
                         │ servido por
        ┌────────────────┼────────────────┬─────────────────┐
        ▼                ▼                ▼                 ▼
   🎭 VOZ            👁️ VISÃO         🗂️ MEMÓRIA         🧬 REFLEXO
   moon_config       hair_profiles    catálogo          score_inci
   (system+intent)   (user)           (produtos reais)  (rules table)
```

**Caminho de uma pergunta** (`POST /api/moon/chat`):

```
1. JWT verify                 → users (core)
2. Rate limit per-user        → in-memory (process)
3. Carrega perfil capilar     → hair_profiles (core)
4. Detecta intent (regex)     → 5 buckets
5. Carrega Compêndio          → knowledge_chunks (core) + decrypt AES-GCM
6. (cond) Analisa INCI        → ingredients + compatibility (catalog)
7. (cond) Busca alternativas  → products + scoring (catalog)
8. Chama Anthropic            → static outbound IP (planejado A3)
9. Persiste turn              → moon_messages (core)
10. Audit log                 → kb_retrieval_log (audit)  fire-and-forget
```

**Cinco intents:** `saude_couro` (prioridade — redireciona derma), `analise_produto` (INCI + produto em contexto), `recomendacao` (catálogo), `rotina_cuidado` (Compêndio puro), `geral` (fallback).

**Privacidade:** a pergunta crua **não fica armazenada** no audit log. Só `sha256(query_text)` em `kb_retrieval_log` — permite detectar dúvidas recorrentes sem reter PII.

---

## 4. Mapa de módulos

```
src/
├── api/
│   ├── main.py                ← app FastAPI, middlewares, init engines
│   ├── auth.py                ← JWT issue/verify, require_admin
│   ├── dependencies.py        ← get_X_session, DatabaseRouter, fallback chain
│   └── routes/
│       ├── auth.py            ← login, logout, change-password, reset-admin
│       ├── moon.py            ← /chat, /analyze, /profile, /feedback
│       ├── brands.py          ← catálogo público
│       ├── products.py        ← catálogo público
│       ├── ingredients.py     ← catálogo público
│       ├── quarantine.py      ← review queue
│       ├── admin_brands.py    ← admin: brand CRUD (audita)
│       ├── admin_knowledge.py ← admin: KB upload + encryption
│       ├── admin_moon.py      ← admin: editar personalidade + intents
│       └── admin_audit.py     ← admin: viewer dos 3 logs
│
├── core/
│   ├── audit.py               ← fire-and-forget log helpers (3 tipos)
│   ├── llm.py                 ← LLMClient (wrap Anthropic + retry)
│   ├── knowledge_base.py      ← load_knowledge_base (decrypt + cache)
│   ├── moon_config.py         ← load_moon_config (system + addendums)
│   ├── kb_crypto.py           ← AES-256-GCM wrappers
│   ├── label_engine.py        ← detecção de selos (sulfate_free, vegan, ...)
│   ├── qa_gate.py             ← verified_inci / catalog_only / quarantined
│   └── hair_profile.py        ← HairProfileInput + derive_hair_types
│
├── discovery/                 ← scrapers (sitemaps + DOM)
│   ├── platform_adapters/     ← VTEX, Shopify, WooCommerce
│   └── ...
│
├── extraction/                ← JSON-LD + selectors + BS fallback
│   └── inci_extractor.py      ← parse INCI (preserva copolímeros no `/`)
│
├── enrichment/                ← source-scrape (Beleza, Época) + matching
│
├── pipeline/
│   └── coverage_engine.py     ← orquestra discovery → extract → validate
│
└── storage/
    ├── orm_models.py          ← Base + ProductORM, IngredientORM, ...
    ├── ops_models.py          ← Base + UserORM (auth)
    ├── moon_models.py         ← Base + MoonConversationORM, MoonMessageORM, MoonFeedbackORM, MoonConfigORM
    ├── hair_profile_models.py ← Base + HairProfileORM
    ├── knowledge_models.py    ← Base + KnowledgeChunkORM (encriptado)
    ├── central_models.py      ← CentralBase + BrandDatabaseORM (legacy multi-brand)
    ├── audit_models.py        ← AuditBase + Auth/Admin/KB log ORMs
    ├── repository.py          ← ProductRepository
    ├── migrations/            ← Alembic catalog (legacy default)
    ├── central_migrations/    ← Alembic central (legacy multi-brand)
    └── audit_migrations/      ← Alembic audit (3-DB split)
```

**Regras de boundary:**
- `api/routes/` chama `core/` mas **nunca** `extraction/` ou `discovery/` direto. Aqueles são executados pelo CLI ou worker.
- `storage/` exporta ORMs e repositories. Resto consome via repository, não query raw — exceto quando perf justifica (score_inci faz raw SQL pra evitar overhead ORM).
- `core/audit.py` **não pode** levantar exceção pro caller. Falha em audit é log + segue. Garantido por `_safe_commit` wrapper.

---

## 5. Frontend

```
frontend/src/
├── pages/
│   ├── Dashboard.tsx          ← métricas gerais
│   ├── BrandsDashboard.tsx    ← lista 692 marcas
│   ├── ProductBrowser.tsx     ← filtro de produtos
│   ├── QuarantineReview.tsx   ← review queue
│   └── ops/                   ← painel admin
│       ├── OpsBrands.tsx
│       ├── OpsKnowledge.tsx   ← 5 abas (Identidade & Tom · Material · Como decide · Métricas · Auditoria)
│       └── sections/
│           ├── IdentityTab.tsx
│           ├── MaterialTab.tsx
│           ├── WorkflowTab.tsx ← anatomia da Moon (cérebro + órgãos)
│           ├── MetricsTab.tsx
│           └── AuditTab.tsx    ← viewer dos 3 logs com KPIs
├── lib/
│   ├── api.ts                 ← fetch client público
│   └── ops-api.ts             ← fetch client admin (com token)
├── hooks/
│   └── useAPI.ts              ← async fetcher genérico
└── types/
    └── api.ts                 ← shapes que casam API
```

**Servido em produção:** `src/api/main.py` monta `/assets/*` e faz fallback de SPA pra `index.html` em qualquer rota não-API.

---

## 6. Segurança em camadas

| Camada | Mecanismo |
|---|---|
| Transport | HTTPS Railway + `Strict-Transport-Security` `max-age=31536000; includeSubDomains` |
| Origin | `CORS` whitelist (`ALLOWED_ORIGINS` env) — sem `*` |
| Browser | `X-Frame-Options: DENY` + `X-Content-Type-Options: nosniff` + `Permissions-Policy: camera=(), microphone=(), geolocation=()` + `Referrer-Policy: strict-origin-when-cross-origin` |
| Rate limit | global per-IP (`API_RATE_LIMIT` env, default 120/min) + per-user no `/moon/chat` (20/min) |
| Auth | JWT HS256 24h · `bcrypt` hash · roles {admin, reviewer} |
| Conteúdo | KB encriptada AES-256-GCM em repouso · `KB_ENCRYPTION_KEY` env (planejado: sealed) |
| Logging | Audit fire-and-forget · sha256 de queries (não PII) · IPs registrados |
| Network (planejado A3) | Static outbound IP · whitelist Anthropic · railway.internal apenas |

**Não exposto publicamente:** Postgres não tem TCP proxy público. Só app conecta via railway.internal.

---

## 7. Pipeline de dados (catálogo)

```
Excel "Lista de Produtos" ──haira registry──> brands.json
                                        │
brands.json ──haira blueprint──> config/blueprints/<slug>.yaml
                                        │
config/blueprints/<slug>.yaml ──haira scrape──> products (raw)
                                        │
products ──haira labels──> products (com sellos)
                                        │
products ──haira audit──> quarantine_details (fails)
                                        │
quarantine_details ──ops review──> products (verified_inci)
```

Cada estágio é idempotente e re-executável. `coverage_engine.py` orquestra. Estado por marca em `brand_coverage` (counters + razões de quarentena).

---

## 8. Deploy

**Auto-deploy:** push em `main` → GitHub → Railway → build Docker → deploy.

**Dockerfile** (2 stages):
1. `frontend-build` (node:20-slim) → `pnpm build` → `/app/frontend/dist`
2. `stage-1` (python:3.12-slim) → `pip install -e .` → copia dist + src + alembic + entrypoint

**Entrypoint** (`entrypoint.sh`):
1. `alembic upgrade head` (catalog/legacy default)
2. (futuro) `alembic -c alembic_central.ini upgrade head` (core)
3. (futuro) `alembic -c alembic_audit.ini upgrade head` (audit)
4. `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

**Build budget atual:** 646KB JS gzipped 193KB · 118KB CSS gzipped 19KB · build em ~1.3s local.

---

## 9. Métricas e observabilidade

| Sinal | Onde |
|---|---|
| Logins (ok/fail) | `auth_event_log` em `haira_audit` |
| Ações admin | `admin_action_log` em `haira_audit` |
| Consultas Moon | `kb_retrieval_log` em `haira_audit` |
| KPIs auth | `GET /api/admin/audit/summary` |
| Feedback Moon | `GET /api/moon/feedback/summary` (admin) |
| DB pool stats | (planejado A3) Railway alerts |
| LLM latência | (planejado A3) wrap em LLMClient |

**Privacy-aware:** `kb_retrieval_log` salva `sha256(query)`, intent, kb_sources e chunk_count — **nunca** a pergunta crua.

---

## 10. Decisões registradas (ADR-leves)

| # | Decisão | Por quê | Quando |
|---|---|---|---|
| 1 | 3-DB split por sensibilidade (não por marca) | Per-brand seriam 692 DBs. Split por classe casa com requisitos reais (PITR, backup, latência). | 04 jun 2026 |
| 2 | Anthropic prompt cache 5 min ao invés de RAG | Compêndio cabe em janela (45k de 200k tokens). RAG só faz sentido quando passar de ~150k. | 05 jun 2026 |
| 3 | AES-256-GCM in-app, não DB-side encryption | Portabilidade: chave fica no app, não vaza com snapshot do DB. | 03 jun 2026 |
| 4 | Audit fire-and-forget, não bloqueante | Observabilidade não pode derrubar request. `_safe_commit` wrapper. | 05 jun 2026 |
| 5 | `branch main` único (não master/main split) | Simplifica auto-deploy. Trabalho histórico em master foi mergeado em commit `b89f796`. | 05 jun 2026 |
| 6 | SQLite `journal_mode=DELETE` em dev (não WAL) | Reduz arquivos órfãos no dev local. | (anterior) |
| 7 | `sha256(query)` no audit, não query crua | Privacy by design. Suficiente pra detectar recorrência. | 05 jun 2026 |

---

## 11. Cabeçalho rápido pra novato

> Vou implementar uma feature nova hoje. Por onde começo?

1. **Backend** vivem em `src/api/routes/<feature>.py`. Cada route module monta um `APIRouter` que `main.py` inclui sob `/api`.
2. **DB** → usa `Depends(get_X_session)` da `dependencies.py`. Escolhe `core` se mexe com user/PII/KB, `catalog` se mexe com produtos/marcas, `audit` se for log.
3. **Pydantic schemas** vivem inline no `routes/<feature>.py`. Modelos ORM em `src/storage/*_models.py`.
4. **Frontend** consome via `frontend/src/lib/api.ts` (público) ou `ops-api.ts` (admin). Types em `frontend/src/types/api.ts`.
5. **Migration** → `alembic revision --autogenerate -m "feat: ..."` na ini correta. Para `haira_audit`, `alembic -c alembic_audit.ini revision ...`.
6. **Testes** → `tests/api/test_<feature>.py` seguindo padrão de `test_moon.py` (in-memory SQLite + override de sessions).
7. **Audit** → se a feature é admin-sensível, importa `log_admin_action` no handler. Fire-and-forget, não pode derrubar request.
8. **Push em main** → auto-deploy. Conferir build na Railway dashboard.

---

## 12. Onde achar o resto

- **Backlog & decisões em curso:** Jira HAIRA-143
- **Convenção CloudCode→Jira:** `docs/cloudcode-jira-standard.md`
- **CLAUDE.md** (raiz do repo): contém comandos comuns, agents disponíveis, padrão de commits

> Este doc é vivo. Quando arquitetura mudar materialmente (ex.: cutover Catalog+Audit completar), atualizar aqui antes de subir o PR final.
