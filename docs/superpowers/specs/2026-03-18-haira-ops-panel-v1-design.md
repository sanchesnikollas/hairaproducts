# HAIRA Ops Panel v1 -- PRD Executivo

**Data**: 2026-03-18
**Status**: Aprovado (brainstorming completo)
**Fase**: 1 (Ops-first)

---

## Decisoes de Design

- **Escopo**: Ops-first (painel puxa schema)
- **Usuarios**: Equipe pequena (2-3), admin + reviewers
- **Status**: 3 campos independentes (operacional, editorial, publicacao)
- **Camadas de produto**: JSONB com Pydantic (interpretation, application, decision)
- **Confianca**: Score simplificado (3 fatores: completude 40%, parsing 35%, validacao 25%)
- **Historico**: Diff completo por campo com author tracking
- **Permissoes**: 2 roles fixos (admin, reviewer)
- **Auth**: Email + password, JWT, sem OAuth

---

## Secao 1: Visao Geral e Principios

**Goal**: Transformar o frontend HAIRA de um browser de dados em um painel operacional para equipe de 2-3 pessoas validar, corrigir e publicar produtos com rastreabilidade completa.

**Principios de design**:

1. **Schema puxa tela, tela puxa schema** -- nenhuma entidade existe sem tela que a consuma, nenhuma tela existe sem entidade que a suporte
2. **Evolucao in-place** -- o sistema atual continua funcionando durante toda a implementacao. Nenhuma migration quebra o pipeline existente
3. **Diff, nao delete** -- toda alteracao gera historico. Nada e sobrescrito silenciosamente
4. **Confianca explicita** -- todo produto tem um score de confianca calculado, visivel no painel
5. **IA como assistente, nao oraculo** -- a Moon (quando entrar na Fase 2) sugere, o humano decide, o sistema registra ambos

**Usuarios e roles**:

| Role | Quem | Pode fazer |
|------|------|------------|
| `admin` | Owner | Tudo: pipeline, config, publicacao, revisao, gestao de usuarios |
| `reviewer` | Especialistas | Revisar produtos, editar campos, aprovar/rejeitar quarentena, ver historico |

**Fora de escopo (Fase 2+)**:
- Integracao com Moon (AI Decision Log, context packages)
- Experience Layer (chat da usuaria)
- Perfil capilar / Programa capilar / Recomendacao
- Feedback de resultado
- Clusterizacao de usuarios
- RBAC granular ou escopo por marca

---

## Secao 2: Evolucao do Schema

**Principio**: Evoluir o que existe, nao recriar. O ProductORM atual ganha campos novos, tabelas novas sao adicionadas ao lado.

### 2.1 Campos novos no ProductORM

```
status_operacional   VARCHAR   -- fase do pipeline: bruto, extraido, normalizado, parseado, validado
status_editorial     VARCHAR   -- revisao humana: pendente, em_revisao, aprovado, corrigido, rejeitado
status_publicacao    VARCHAR   -- visibilidade: rascunho, publicado, despublicado, arquivado
confidence_score     FLOAT     -- score 0-100 calculado
confidence_factors   JSONB     -- {completude: 0.8, parsing: 0.9, validacao_humana: 0.0}
interpretation_data  JSONB     -- camada 2: analise funcional da formula
application_data     JSONB     -- camada 3: contexto de uso
decision_data        JSONB     -- camada 4: sintese, confianca, alertas
```

**Migration strategy**: Os 3 campos de status comecam com valores derivados do `verification_status` atual:
- `verified_inci` -> operacional=`validado`, editorial=`aprovado`, publicacao=`publicado`
- `catalog_only` -> operacional=`extraido`, editorial=`pendente`, publicacao=`rascunho`
- `quarantined` -> operacional=`extraido`, editorial=`rejeitado`, publicacao=`rascunho`

O campo `verification_status` antigo permanece por compatibilidade ate o frontend migrar completamente.

### 2.2 Nova tabela: RevisionHistory

```
revision_id          UUID PK
entity_type          VARCHAR     -- 'product', 'ingredient', 'claim'
entity_id            UUID        -- FK polimorfico
field_name           VARCHAR     -- campo alterado
old_value            TEXT        -- valor anterior (serializado)
new_value            TEXT        -- valor novo (serializado)
changed_by           UUID FK     -- quem alterou (user_id)
change_source        VARCHAR     -- 'human', 'system', 'pipeline'
change_reason        TEXT        -- motivo opcional
created_at           TIMESTAMP
```

### 2.3 Nova tabela: UserORM

```
user_id              UUID PK
email                VARCHAR UNIQUE
name                 VARCHAR
role                 VARCHAR     -- 'admin' ou 'reviewer'
is_active            BOOLEAN
created_at           TIMESTAMP
last_login_at        TIMESTAMP
```

Autenticacao simplificada: email + password hash (bcrypt). Sem OAuth na Fase 1.

### 2.4 Pydantic schemas para os JSONB

```python
class InterpretationData(BaseModel):
    formula_classification: str | None     # "hidratacao", "reconstrucao", etc.
    key_actives: list[str]                 # ativos principais
    formula_base: str | None               # base da formula
    silicone_presence: bool | None
    sulfate_presence: bool | None
    protein_presence: bool | None
    hydration_nutrition_balance: str | None
    treatment_intensity: str | None        # leve, medio, intenso

class ApplicationData(BaseModel):
    when_to_use: str | None
    when_to_avoid: str | None
    ideal_frequency: str | None
    ideal_hair_types: list[str]
    cautions: list[str]

class DecisionData(BaseModel):
    summary: str | None                    # sintese em 1 linha
    strengths: list[str]
    concerns: list[str]
    ready_for_publication: bool
    requires_human_review: bool
    review_reason: str | None
    confidence_score: float | None
    uncertainty_flags: list[str]
```

### 2.5 O que NAO muda

- `IngredientORM`, `ClaimORM`, `ProductIngredientORM`, `ProductClaimORM` -- ja existem e estao bem modelados
- `ProductEvidenceORM` -- continua como esta
- `QuarantineDetailORM` -- continua, mas o painel usa `status_editorial` como fonte primaria
- `BrandCoverageORM` -- continua sendo recalculado pelo pipeline
- Multi-DB architecture -- intocada

---

## Secao 3: Fluxo 1 -- Dashboard Operacional

**Quem usa**: Admin e Reviewers (tela inicial apos login)

**Objetivo**: Visao instantanea da saude da base e das pendencias. A pergunta que responde: "o que precisa da minha atencao agora?"

### 3.1 KPIs principais (cards no topo)

| KPI | Calculo | Fonte |
|-----|---------|-------|
| Total de produtos | COUNT(products) | ProductORM |
| INCI Coverage | AVG(confidence_score) ou weighted rate | BrandCoverageORM |
| Pendentes de revisao | COUNT(status_editorial = 'pendente') | ProductORM |
| Em quarentena | COUNT(status_editorial = 'rejeitado') | ProductORM |
| Publicados | COUNT(status_publicacao = 'publicado') | ProductORM |
| Confianca media | AVG(confidence_score) | ProductORM |

### 3.2 Blocos de atencao (abaixo dos KPIs)

- **Fila prioritaria**: Top 10 produtos com `requires_human_review = true` ordenados por confidence_score ASC (pior primeiro)
- **Inconsistencias**: Produtos onde `confidence_score < 50` agrupados por tipo de problema (INCI incompleto, categoria ausente, etc.)
- **Reformulacao suspeita**: Produtos com `status_operacional = 'reformulado_suspeito'` (Fase 2, mas o campo ja existe)
- **Atividade recente**: Ultimas 20 entradas em RevisionHistory com avatar do autor

### 3.3 API necessaria

```
GET /api/ops/dashboard
Response: {
  kpis: { total_products, inci_coverage, pending_review, quarantined, published, avg_confidence },
  priority_queue: Product[],         // top 10 requires_human_review
  low_confidence: Product[],         // confidence < 50
  recent_activity: RevisionHistory[] // last 20
}
```

### 3.4 Diferenca do dashboard atual

Hoje o Home mostra: health score global, alertas por marca, grid de brand cards. Isso **continua existindo** como visao publica. O dashboard operacional e uma tela nova, acessivel so apos login, focada em acao, nao em visualizacao.

**Rota**: `/ops` (dashboard operacional) vs `/` (home publica)

---

## Secao 4: Fluxo 2 -- Gestao de Produtos

**Quem usa**: Admin e Reviewers
**Objetivo**: Encontrar, inspecionar e editar qualquer produto da base com eficiencia.

### 4.1 Lista de produtos (evolucao do Explorador atual)

**O que muda vs hoje**:
- Colunas novas: `status_operacional`, `status_editorial`, `status_publicacao`, `confidence_score`
- Filtros novos: por status editorial, por faixa de confianca, por "precisa revisao humana"
- Acoes em lote: alterar `status_editorial` ou `status_publicacao` de multiplos produtos de uma vez
- Atribuicao: marcar produtos como "em revisao por [reviewer]"

**O que NAO muda**:
- Busca por nome, marca, INCI, categoria -- ja funciona
- Ordenacao por colunas -- ja funciona
- ProductSheet lateral -- ja funciona (mas evolui, ver 4.2)

**Rota**: `/ops/products` (lista operacional) vs `/explorer` (visao publica, continua)

### 4.2 Detalhe do produto (evolucao do ProductSheet)

O ProductSheet atual mostra sections colapsaveis (Basic Info, INCI, Labels, Quality, Evidence, Edit). Evolui para as **4 camadas do blueprint**:

**Aba 1 -- Dados Brutos**
- Nome, marca, categoria, descricao, modo de uso, volume
- INCI raw (texto original extraido)
- Claims do rotulo
- Imagens
- Fonte da extracao (evidence)
- Status operacional com timeline visual

**Aba 2 -- Interpretacao**
- `interpretation_data` JSONB renderizado
- Classificacao da formula, ativos-chave, base
- Flags: silicone, sulfato, proteina, etc.
- Intensidade de tratamento
- Equilibrio hidratacao/nutricao/reconstrucao
- Badge de confianca com fatores expandiveis

**Aba 3 -- Aplicacao** (vazio na Fase 1, preparado para Moon)
- `application_data` JSONB renderizado quando existir
- Placeholder: "Aguardando analise da Moon" com visual discreto
- Quando preenchido: quando usar, quando evitar, para quem, frequencia

**Aba 4 -- Decisao** (vazio na Fase 1, preparado para Moon)
- `decision_data` JSONB renderizado quando existir
- Placeholder similar
- Quando preenchido: sintese, forcas, alertas, elegibilidade para publicacao

**Footer permanente**:
- Status editorial (dropdown editavel)
- Status publicacao (dropdown editavel)
- Botao "Salvar" (gera RevisionHistory)
- Botao "Publicar" / "Despublicar" (admin only)

### 4.3 Modo edicao inline

Ao clicar em qualquer campo editavel:
- Campo vira input
- Ao sair do campo, diff e mostrado: "Nome: `Condicionador Curumim 200ml` -> `Condicionador Curumim Infantil 200ml`"
- Salvar gera 1 registro em RevisionHistory por campo alterado
- `change_source = 'human'`, `changed_by = user_id` do usuario logado

### 4.4 APIs necessarias

```
PATCH /api/products/{id}
  -- ja existe, mas passa a gerar RevisionHistory automaticamente

PATCH /api/products/batch
  -- novo: altera status_editorial ou status_publicacao de multiplos IDs
  Body: { product_ids: [], status_editorial?: string, status_publicacao?: string }

GET /api/products/{id}/history
  -- novo: retorna RevisionHistory[] para o produto
  Response: { revisions: [{ field_name, old_value, new_value, changed_by, change_source, created_at }] }
```

### 4.5 Historico de alteracoes (sub-aba no detalhe)

- Timeline vertical com diff por campo
- Cada entrada mostra: campo, valor anterior -> novo, quem, quando, origem (humano/sistema/pipeline)
- Filtro por campo e por autor
- Possibilidade de reverter (gera novo registro de diff, nao deleta o anterior)

---

## Secao 5: Fluxo 3 -- Fila de Revisao

**Quem usa**: Reviewers principalmente, Admin supervisiona
**Objetivo**: Pipeline de trabalho para resolver pendencias de forma sistematica, nao caotica.

### 5.1 Fontes da fila

A fila agrega pendencias de 4 origens numa unica interface:

| Origem | Criterio | Prioridade |
|--------|----------|------------|
| Quarentena | `status_editorial = 'rejeitado'` com `review_status = 'pending'` | Alta |
| Baixa confianca | `confidence_score < 50` | Media |
| Revisao solicitada | `decision_data.requires_human_review = true` | Media |
| Inconsistencia | Campos criticos vazios (INCI null, categoria null) em produtos `status_operacional >= 'extraido'` | Baixa |

### 5.2 Interface da fila

- Lista ordenada por prioridade (alta -> baixa), depois por data (mais antigo primeiro)
- Cada item mostra: nome do produto, marca, tipo de pendencia, confidence_score, quanto tempo na fila
- Filtros: por tipo de pendencia, por marca, por reviewer atribuido
- Acao rapida: clicar abre o ProductSheet no modo edicao com a aba relevante pre-selecionada
- Contador no nav: badge com total de pendencias (como o quarentena badge atual, mas agregado)

### 5.3 Workflow de revisao

```
Item entra na fila (automatico)
-> Reviewer abre o item
-> status_editorial muda para 'em_revisao' (automatico ao abrir)
-> Reviewer inspeciona, corrige campos se necessario
-> Reviewer decide:
   -> "Aprovar" -> status_editorial = 'aprovado', status_publicacao = 'publicado'
   -> "Corrigir e aprovar" -> edita campos + status_editorial = 'corrigido'
   -> "Rejeitar" -> status_editorial = 'rejeitado' com motivo obrigatorio
-> RevisionHistory registra tudo
-> Item sai da fila
-> Proximo item carrega automaticamente (modo "fluxo continuo")
```

### 5.4 Modo fluxo continuo

Inspirado no Tinder de revisao: ao aprovar/rejeitar, o proximo item da fila carrega automaticamente sem voltar pra lista. Barra de progresso no topo mostra "12 de 47 revisados nesta sessao". Botao "Sair do fluxo" volta pra lista.

O `QuarantineTab` e `SessionProgress` atuais ja fazem algo parecido -- essa logica e extraida e generalizada para qualquer tipo de pendencia, nao so quarentena.

### 5.5 APIs necessarias

```
GET /api/ops/review-queue
  Query: type?, brand?, assigned_to?, page, per_page
  Response: PaginatedResponse<ReviewQueueItem>
  -- agrega as 4 fontes numa unica query ordenada por prioridade

POST /api/ops/review-queue/{product_id}/start
  -- marca status_editorial = 'em_revisao', registra reviewer

POST /api/ops/review-queue/{product_id}/resolve
  Body: { decision: 'approve' | 'correct' | 'reject', notes?: string, corrections?: Record<string, any> }
  -- aplica decisao, gera RevisionHistory, atualiza status
```

### 5.6 Rota

`/ops/review` -- fila de revisao unificada

---

## Secao 6: Fluxo 4 -- Governanca de Ingredientes

**Quem usa**: Admin principalmente
**Objetivo**: Manter a taxonomia de ingredientes limpa, completa e confiavel. Sem isso, parsing e interpretacao degradam.

### 6.1 O que ja existe

- `IngredientORM` com canonical_name, inci_name, cas_number, category, safety_rating
- `IngredientAliasORM` com alias unico por ingrediente
- `ProductIngredientORM` com position, raw_name, validation_status
- API: `GET /api/ingredients` com busca, `GET /api/ingredients/{id}` com aliases e product_count

### 6.2 O que falta

**Tela de lista de ingredientes** (`/ops/ingredients`):
- Tabela com: canonical_name, category, total de aliases, total de produtos que usam, gaps
- Filtros: por category, por "sem categoria", por "sem CAS", por quantidade de produtos
- Ordenacao: por product_count (mais usados primeiro), por gaps

**Tela de detalhe do ingrediente**:
- Editar canonical_name, inci_name, category, safety_rating
- Gerenciar aliases (adicionar, remover, unificar duplicatas)
- Ver todos os produtos que usam este ingrediente
- Flag visual: "ingrediente sem categoria" (gap de taxonomia)

**Deteccao de gaps**:
- Ingredientes sem `category` definida
- `raw_name` em ProductIngredient que nao tem match com nenhum Ingredient (orfaos)
- Aliases potencialmente duplicados (fuzzy match)

### 6.3 APIs necessarias

```
PATCH /api/ingredients/{id}
  -- atualizar campos do ingrediente, gera RevisionHistory

POST /api/ingredients/{id}/aliases
  Body: { alias: string, language?: string }

DELETE /api/ingredients/{id}/aliases/{alias_id}

GET /api/ingredients/gaps
  Response: {
    uncategorized: IngredientSummary[],
    orphan_raw_names: { raw_name: string, product_count: number }[],
    potential_duplicates: { a: string, b: string, similarity: number }[]
  }
```

### 6.4 Acoes em lote

- Selecionar multiplos ingredientes sem categoria -> atribuir categoria
- Selecionar multiplos orfaos -> criar novo ingrediente ou mapear para existente
- Unificar duplicatas: escolher o canonico, mover todos os aliases e product_ingredients

---

## Secao 7: Fluxo 5 -- Autenticacao e Roles

**Objetivo**: Saber quem fez o que. Sem auth, RevisionHistory nao tem autor.

### 7.1 Modelo minimo

- Login com email + password (bcrypt hash)
- JWT token com expiracao de 24h
- 2 roles: `admin`, `reviewer`
- Sem registro aberto -- admin cria contas manualmente
- Sem OAuth/SSO na Fase 1

### 7.2 Protecao de rotas

| Rota | Acesso |
|------|--------|
| `/` , `/brands/*`, `/explorer` | Publica (sem auth) |
| `/ops/*` | Requer login |
| `/ops/review` | Admin + Reviewer |
| `/ops/products` (leitura) | Admin + Reviewer |
| `/ops/products` (edicao/publicacao) | Admin + Reviewer (editar), Admin only (publicar) |
| `/ops/ingredients` | Admin only |
| `/ops/settings` | Admin only |

### 7.3 APIs necessarias

```
POST /api/auth/login
  Body: { email, password }
  Response: { token, user: { id, name, email, role } }

GET /api/auth/me
  Headers: Authorization: Bearer <token>
  Response: { id, name, email, role }

POST /api/auth/users          -- admin only
PATCH /api/auth/users/{id}    -- admin only
```

### 7.4 Tela de settings (`/ops/settings`) -- Admin only

- Lista de usuarios com role
- Criar/desativar usuario
- Sem edicao de permissoes granulares (so 2 roles)

---

## Secao 8: Calculo do Confidence Score

### 8.1 Formula simplificada (Fase 1)

```
confidence_score = (
    completude     * 0.40 +
    parsing_inci   * 0.35 +
    validacao_humana * 0.25
) * 100
```

**Completude** (0.0 - 1.0): Proporcao de campos criticos preenchidos
- Campos criticos: product_name, product_category, brand_slug, description, inci_ingredients, image_url_main
- 6 campos, cada um vale 1/6

**Parsing INCI** (0.0 - 1.0):
- 0.0 se `inci_ingredients` e null ou vazio
- 0.5 se tem INCI mas nenhum match em ProductIngredient com `validation_status = 'validated'`
- 1.0 se tem INCI e todos os ingredientes estao mapeados e validados

**Validacao humana** (0.0 - 1.0):
- 0.0 se `status_editorial = 'pendente'`
- 0.5 se `status_editorial = 'em_revisao'`
- 1.0 se `status_editorial IN ('aprovado', 'corrigido')`

### 8.2 Quando recalcular

- Ao salvar qualquer edicao no produto
- Ao resolver item na fila de revisao
- Ao rodar pipeline de extracao/labels
- Recalculo em batch via CLI: `haira confidence --brand <slug>`

### 8.3 Expansao futura (Fase 2)

Novos fatores entram na formula quando disponveis:
- Consistencia analitica (Moon vs regras)
- Feedback real de usuarios
- Estabilidade da formula (sem suspeita de reformulacao)

---

## Secao 9: Estrutura de Navegacao

### 9.1 Rotas completas

```
Publico (sem auth):
  /                          -- Home (health score, brands, alertas)
  /brands                    -- Lista de marcas
  /brands/:slug              -- Detalhe da marca (produtos, quarentena, cobertura)
  /explorer                  -- Explorador de produtos (tabela)

Operacional (requer login):
  /ops                       -- Dashboard operacional
  /ops/products              -- Lista de produtos (visao operacional)
  /ops/review                -- Fila de revisao unificada
  /ops/ingredients           -- Governanca de ingredientes (admin)
  /ops/settings              -- Gestao de usuarios (admin)
  /login                     -- Tela de login
```

### 9.2 Navegacao

Header atual ganha um botao "Ops" que leva ao `/login` ou `/ops` dependendo se esta autenticado. Dentro de `/ops`, nav lateral minimalista com:
- Dashboard
- Produtos
- Revisao (com badge de contagem)
- Ingredientes
- Settings

### 9.3 Separacao clara

As rotas publicas (`/`, `/brands`, `/explorer`) continuam funcionando exatamente como hoje, sem auth. O `/ops` e um "mundo separado" com layout proprio, nav propria, e requer login. Nenhuma rota publica e quebrada.

---

## Secao 10: Criterios de Sucesso e Verificacao

### 10.1 Definition of Done

A Fase 1 esta completa quando:

1. Admin consegue logar e criar conta de reviewer
2. Dashboard mostra KPIs reais calculados da base
3. Lista de produtos operacional filtra por status editorial, confianca, e "precisa revisao"
4. Detalhe do produto mostra as 4 abas (brutos + interpretacao + 2 placeholders)
5. Edicao de qualquer campo gera registro em RevisionHistory com autor
6. Fila de revisao agrega quarentena + baixa confianca + inconsistencias
7. Modo fluxo continuo funciona (aprovar -> proximo automatico)
8. Confidence score e calculado e visivel em todas as listas e detalhes
9. Painel de ingredientes mostra gaps e permite edicao
10. Todas as rotas publicas continuam funcionando sem auth

### 10.2 Metricas de validacao

- Tempo medio para revisar 1 produto: < 30 segundos no modo fluxo
- Zero migrations que quebram dados existentes
- Build do frontend passa sem erros
- Todas as APIs novas tem pelo menos 1 teste

### 10.3 O que NAO e criterio de sucesso na Fase 1

- Moon produzir interpretation_data (isso e Fase 2)
- Usuarios finais usarem o chat (Fase 3)
- Score de confianca estar "calibrado" (isso vem com uso)
