# Fluxo Moon + Perfil do Cliente — Design Specification

**Date:** 2026-05-27
**Status:** Implemented (backend + telas web)
**Scope:** Fechar o fluxo da Moon (assistente de IA) ligando o perfil capilar do
cliente ao motor de compatibilidade INCI já existente, com camada conversacional
LLM e recomendação de alternativas do catálogo.

Fonte de verdade do produto: Figma "Haira – App", canvas `◆ ・ Plano Cliente`
(`node-id 2:19`). Telas-chave: `2.3.1 Profile_EditHair`, `2.3.2
DiscoverType_Modal`, `4.0.1 Moon_Chat_ProductFound`, `4.1.3
Moon_Conversation_AIResponse`.

---

## 1. Problema

O Moon já existia como **analisador determinístico** (`POST /moon/analyze`:
INCI + `hair_types[]` → score via tabela `ingredient_category_compatibility`),
exposto numa ferramenta de ops (`MoonAnalyzer.tsx`). Faltava o que o Figma mostra:

1. Um **perfil capilar persistido** por usuário (as 14 perguntas do app).
2. Uma **camada conversacional** que cumprimenta pelo nome, referencia o perfil
   ("seu perfil ondulado 2B") e **sugere alternativas** do catálogo.
3. As **telas** de captura do perfil e de chat.

## 2. Arquitetura

```
Captura (telas) → hair_profiles (DB) → derive_hair_types() → slugs do motor
                                                   │
Produto escaneado/INCI ──→ score_inci() ──────────┤
Catálogo (verified_inci) ─→ _fetch_alternatives() ─┤
                                                   ▼
                              /moon/chat → LLM (Moon persona) → resposta + alternativas
```

### 2.1 Perfil — `hair_profiles` (nova tabela)

Um registro por usuário (`user_id` unique, FK `users`). Dimensões principais em
colunas tipadas (queryáveis pela derivação/filtros); condicionais e payload bruto
em JSON. Campos espelham o questionário do Figma — ver
`src/storage/hair_profile_models.py`.

### 2.2 Derivação perfil → slugs do motor

`src/core/hair_profile.py::derive_hair_types`. O motor entende 11 slugs
(`liso, cacheado, crespo, oleoso, seco, normal, com_quimica, tingido,
danificado, sensibilizado, fino`). Regras determinísticas:

| Entrada do perfil | Slugs derivados |
|---|---|
| subtipo 1x / 3x / 4x | liso / cacheado / crespo (subtipo tem precedência) |
| oleosidade alta / baixa / normal | oleoso / seco / normal |
| ressecamento bastante | seco + danificado |
| coloração | com_quimica + tingido |
| descoloração | com_quimica + tingido + danificado + sensibilizado |
| alisamento | com_quimica + sensibilizado |
| fios finos | fino |
| calor diário / sol alto / piscina frequente | danificado |

**Gaps de taxonomia documentados** (intencionalmente sem slug, para não gerar
sinal ruim): curvatura `ondulado` (2x), espessura `grosso`, e `cor / extensions /
exposição` (registrados, ainda não pontuados). Resolver = adicionar regras em
`ingredient_category_compatibility`.

### 2.3 Endpoints (`src/api/routes/moon.py`)

| Método | Rota | Função |
|---|---|---|
| POST | `/moon/profile` | upsert do perfil (1 por usuário) + grava `derived_hair_types` |
| GET | `/moon/profile/{user_id}` | lê o perfil |
| POST | `/moon/chat` | resposta conversacional aterrada em perfil + análise + alternativas |
| POST | `/moon/analyze` | (existente) scoring puro — refatorado sobre `score_inci()` |
| GET | `/moon/categories` | (existente) regras de compatibilidade |

`/moon/chat` resolve o perfil (inline ou persistido via `user_id`), roda
`score_inci` no produto em contexto (se houver), busca top-3 alternativas
(`verified_inci`, mesmo `product_type`, ranqueadas pelo motor) e injeta tudo num
bloco de contexto para o LLM com a persona Moon (PT-BR, acolhedor, ≤1 emoji 🌙,
nunca inventa ingredientes).

### 2.4 Telas (web, `frontend/src/pages/`)

- `HairProfileForm.tsx` (`/ops/profile`) — questionário com botões de opção,
  carrega perfil existente, salva e leva ao chat.
- `MoonChat.tsx` (`/ops/moon-chat`) — chat com bolhas, usa o perfil salvo,
  mostra alternativas.

São telas **web** no app de ops existente (React+Vite+Tailwind). O app mobile do
Figma é outra superfície; estas telas validam o fluxo e o contrato de API.

## 3. Critérios de aceite

- [x] `hair_profiles` criada via Alembic sem dropar `ingredient_category_compatibility`.
- [x] Derivação cobre as 14 perguntas, só emite slugs conhecidos, sem duplicatas. (10 testes)
- [x] `/moon/profile` faz upsert idempotente (1 por usuário) e persiste `derived_hair_types`.
- [x] `/moon/chat` responde aterrado no perfil + sugere alternativa real do catálogo.
- [x] `/moon/analyze` intacto após refactor.
- [x] Frontend builda limpo (tsc + vite).
- [x] Perfil persiste através de recreate do container.

## 4. Riscos & decisões

- **SQLite WAL + bind-mount de arquivo único** corrompia persistência no Docker
  (sidecar `-wal` divergia entre host e container). **Decisão:** converter o
  `haira.db` para `journal_mode=DELETE` (grava in-place no arquivo montado).
  Backup `haira.db.bak.20260527_pre_journal_switch`. Alinhado ao constraint já
  conhecido de SQLite single-writer.
- **Custo LLM:** `/moon/chat` usa `LLMClient.chat()` que NÃO consome o budget
  por-marca (não é brand-scoped), mas registra custo no `CostTracker`.
- **Multi-DB (Railway):** os endpoints usam `_get_session()` no DB central; em
  produção multi-banco, `hair_profiles`/`users` vivem no central (coerente com a
  spec do Railway que adiou `users/user_profiles` para a fase de IA — esta é a
  materialização).

## 5. Fora de escopo (próximos)

- Telas mobile pixel-perfect do Figma (esta entrega é web).
- Condicionais de química na UI (tipo de coloração, quem aplica, frequências) —
  schema já suporta (`conditionals` JSON), falta UI.
- Regras de compatibilidade para `ondulado` e `grosso`.
- Histórico de conversas Moon persistido (hoje o chat é stateless por request).
- Entrada via Scanner (a tela `4.0.1` liga scanner→`/moon/chat` com `product_id`;
  o endpoint já aceita `product_id`, falta a tela de scanner).

## 6. Arquivos

```
src/storage/hair_profile_models.py        NEW  ORM
src/storage/hair_profile_repository.py    NEW  CRUD/upsert
src/core/hair_profile.py                  NEW  Pydantic + derivação + summary
src/storage/migrations/versions/62fd79bb9256_*.py  NEW  migration
src/api/routes/moon.py                    MOD  score_inci extraído + profile/chat
src/core/llm.py                           MOD  método chat()
frontend/src/pages/HairProfileForm.tsx    NEW
frontend/src/pages/MoonChat.tsx           NEW
frontend/src/lib/api.ts                   MOD  tipos + clients
frontend/src/App.tsx, components/ops/OpsLayout.tsx  MOD  rotas + nav
docker-compose.yml                        NEW/MOD  dev stack + mounts
tests/core/test_hair_profile.py           NEW  10 testes
```
