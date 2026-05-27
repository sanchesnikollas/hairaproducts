# Moon — Plano de Melhorias & Potencialização (Apify)

**Date:** 2026-05-27
**Status:** Proposto
**Base:** HAIRA-153 (fluxo Moon no ar em produção). Observações reais coletadas
durante o deploy e a validação E2E.

---

## 0. Estado atual (o que está no ar)

Moon em produção (`haira-app-production-deb8.up.railway.app`): perfil capilar
persistido (14 perguntas) → derivação para slugs do motor → chat LLM aterrado em
perfil + análise INCI + alternativas do catálogo. Login das reviewers OK.
25.130 produtos, mas só **~8.5k com `verified_inci`** (única fonte recomendável).

**Limitações observadas na validação (motivam este plano):**
- Alternativas com **scores baixos (0.0–0.1)** e pouco relevantes: `_fetch_alternatives`
  pega os **primeiros N produtos sem `ORDER BY`** e só então pontua — pool quase aleatório.
- **Tipos mal classificados** no catálogo (ex.: "Shampoo Detox em Barra" marcado como `oxidante`).
- Slugs do motor ignoram nuances do perfil (cor, comprimento, exposição sol/mar, couro).
- **Gaps de taxonomia**: `ondulado` e `grosso` não têm regras de compatibilidade.
- Chat **stateless** (sem histórico); sem tela de Scanner; perfil sem auth.

---

## Parte A — Refinar a Moon (produto)

### P0 — Quick wins (dias)
1. **Pool de alternativas inteligente.** Em vez dos primeiros N, pré-selecionar um
   pool maior por relevância (mesma `product_type` da intenção/feature, marcas com
   alto INCI) e pontuar 30–50 candidatos; cachear scores por (produto × perfil).
   *Impacto: acaba com sugestões de score ~0.*
2. **Auth no perfil.** `POST /moon/profile` hoje aceita anônimo — vincular ao usuário
   autenticado (JWT já existe em `auth.py`). Evita perfis órfãos e prepara LGPD.
3. **Feedback loop das reviewers.** 👍/👎 por mensagem da Moon → tabela
   `moon_feedback` (msg, perfil, produto, nota, comentário). É o que transforma o
   teste das meninas em dado de tuning. *Pré-requisito pra medir qualquer melhoria.*
4. **Rotacionar credenciais.** `haira2026` (compartilhada) e admin `haira123` →
   trocar e habilitar `/change-password` na UI.

### P1 — Qualidade da recomendação (1–2 semanas)
5. **Fechar gaps de taxonomia.** Adicionar regras em `ingredient_category_compatibility`
   para `ondulado` (curvatura 2x) e `grosso`. Cada perfil passa a ter sinal completo.
6. **Usar o perfil inteiro no contexto do LLM.** Hoje só os 11 slugs entram no score;
   passar cor, comprimento, exposição sol/mar, couro (sintomas), frequência de lavagem
   direto pro prompt → respostas mais personalizadas sem depender do motor.
7. **Surface da análise no chat.** Quando há produto em contexto, mostrar card com
   score/alertas/benefícios (como o Figma `4.0.x`) — não só texto.
8. **Histórico de conversa.** Tabelas `moon_conversations`/`moon_messages` (Figma
   `4.1.2 ConversationList`). Habilita continuidade e contexto multi-turn real.

### P2 — Fluxo completo do app (3–4 semanas)
9. **Entrada via Scanner.** Tela de scanner (Figma `3.0.x`) → `/moon/chat` com
   `product_id` (endpoint já aceita). Fecha o caso de uso principal do Figma.
10. **Telas mobile pixel-perfect** (hoje é web/ops) + condicionais de química na UI
    (schema já suporta via `conditionals`).
11. **Eval harness.** Conjunto fixo (perfis × perguntas) + rubricas, rodado a cada
    mudança de prompt/modelo, comparando contra o feedback real das reviewers.

---

## Parte B — Potencializar com Apify (dados/cobertura)

**Por que faz sentido:** o teto de qualidade da Moon é a **cobertura de INCI** e a
**largura do catálogo** (alternativas exigem `verified_inci`; hoje 39%). Esses são
exatamente os pontos que o roadmap 0→100 lista como mais difíceis (M2 onboarding de
~538 marcas, M3 source-scrape em distribuidores, Q1 INCI 39%→80%) — e onde o Apify
ataca direto. Apify **não substitui** a lógica de domínio do HAIRA (extração INCI,
`qa_gate`, `label_engine`, normalização) — ele resolve a parte de **aquisição** (HTML/JSON
+ anti-bloqueio + escala), entregando dados que o pipeline atual normaliza.

**Fit técnico (alto):** Apify usa **Crawlee** com Playwright/BeautifulSoup — o mesmo
stack do HAIRA (`src/discovery`, `platform_adapters`). Reaproveitamento direto.

| Dor atual do HAIRA | O que o Apify resolve |
|---|---|
| M3 travado: Beleza na Web/Época são **SPA + Cloudflare** (roadmap registrou detection bug, tier_3=0) | **Proxies residenciais + unblocking + headless** resolvem JS-render e anti-bot — destrava o source-scrape de distribuidores |
| Onboarding manual de 538 marcas (blueprint por marca) | **Actors prontos** (e-commerce genérico, Shopify, etc.) + Crawlee reduzem trabalho por marca |
| INCI 39% → meta 80% | Mais páginas raspadas com sucesso = mais INCI extraído = mais produtos recomendáveis pela Moon |
| Re-scrape periódico (preço/estoque) feito à mão | **Scheduling + webhooks** do Apify → chamam a API do HAIRA pra ingestão |
| Infra de Playwright/proxies local (HEADLESS, REQUEST_DELAY) | Apify roda em nuvem com auto-scale, rotação e retries |

**Arquitetura de integração proposta:**
1. Actor Apify (custom via Crawlee ou da store) raspa URLs/HTML da marca/distribuidor.
2. Output cai no **dataset** do Apify; **webhook** dispara → endpoint novo
   `POST /api/ingest/apify` no HAIRA.
3. HAIRA roda a lógica existente (extração JSON-LD/CSS, `inci_extractor`, `qa_gate`,
   `label_engine`) e faz `repository.upsert_product` — preservando "never downgrade INCI".
4. MCP do Apify permite orquestrar actors direto daqui (CloudCode), alinhado ao
   padrão de agentes (`brand-onboarding`, `inci-enricher`).

**Trade-offs a validar (PoC antes de comprometer):**
- **Custo:** Apify é usage-based (compute units + proxies residenciais são o caro).
  Faz sentido para as marcas **bloqueadas/SPA** (onde o scraper próprio falha), não
  necessariamente para VTEX/Shopify simples que o HAIRA já resolve barato.
- **Lock-in:** mitigado usando **Crawlee** (open-source) — dá pra rodar dentro ou
  fora do Apify.
- **Esforço de integração:** ~1 endpoint de ingestão + mapeamento do output do actor
  pro schema do HAIRA.
- $500 em créditos grátis pra creators → cobre uma PoC.

**PoC sugerida (1 semana):** pegar 1 distribuidor bloqueado (Beleza na Web) +
3–5 marcas tier_3 que hoje retornam 0 → rodar via Apify (residential proxy) →
medir produtos/INCI ganhos vs. o scraper atual. Critério: se destravar ≥X marcas
inviáveis, vale escalar pro M3.

---

## Ordem recomendada

```
Semana 1   P0 (pool de alternativas, auth perfil, feedback loop, credenciais)
           + PoC Apify (1 distribuidor bloqueado)
Semana 2-3 P1 (taxonomia, perfil completo no LLM, análise no chat, histórico)
           + decisão Apify: escalar M3/Q1 se a PoC provar ganho
Semana 4+  P2 (scanner, telas mobile, eval harness)
```

**Métrica-norte:** % de respostas da Moon avaliadas como úteis pelas reviewers
(feedback loop do P0) — é o que diz se as melhorias estão lapidando de verdade.

---

## Referências
- HAIRA-153 (fluxo Moon) · `docs/superpowers/specs/2026-05-27-moon-flow-perfil-cliente.md`
- `docs/superpowers/plans/2026-05-12-roadmap-0-a-100.md` (M2/M3/Q1 — onde o Apify entra)
- Apify: Actors, Crawlee (Python/JS, Playwright/BeautifulSoup), proxies residenciais,
  scheduling, datasets, MCP. Pricing usage-based, $500 créditos creators.
