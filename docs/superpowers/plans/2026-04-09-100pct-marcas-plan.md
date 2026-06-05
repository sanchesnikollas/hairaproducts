# Plano: 100% das Marcas Concluídas

## Contexto

Estado atual (09/04/2026):
- **Produção**: 49 marcas | 10.981 produtos | 5.784 INCI (52.7%)
- **Local**: 48 marcas | 12.877 produtos | 6.163 INCI | 2.076 ingredientes limpos
- **Meta**: 42 Marcas Principais da planilha com cobertura INCI máxima
- Interface unificada Shopify-style com tag input de ingredientes + autocomplete

## Estado por Marca Principal

### Tier 1: Concluídas (>80% INCI) — 14 marcas
| Marca | Produtos | INCI | Taxa |
|-------|----------|------|------|
| TRESemmé | 32 | 32 | 100% |
| Salon Line | 792 | 771 | 97% |
| Keune | 271 | 254 | 94% |
| Granado | 61 | 57 | 94% |
| Inoar | 218 | 202 | 93% |
| Amend | 706 | 629 | 89% |
| Kerastase | 268 | 231 | 86% |
| Pantene | 58 | 49 | 85% |
| Aussie* | 16 | 12 | 80% |
| Alphahall* | 151 | 140 | 93% |
| Amazonico Care* | 14 | 13 | 93% |
| Avatim | 105 | 95 | 90% |
| Mustela | 21 | 19 | 90% |
| Balai* | 21 | 20 | 95% |

### Tier 2: Em progresso (20-79% INCI) — 15 marcas
| Marca | Produtos | INCI | Taxa | Bloqueio |
|-------|----------|------|------|----------|
| Seda | 128 | 101 | 79% | Boom line sem INCI |
| All Nature* | 215 | 159 | 76% | Kits sem INCI |
| Joico | 279 | 168 | 60% | Site não publica tudo |
| O Boticário | 1.884 | 1.139 | 60% | Muitos non-hair |
| Apice* | 558 | 164 | 29% | Site VTEX sem INCI |
| Eudora | 1.809 | 695 | 38% | Muitos non-hair |
| Wella | 24 | 9 | 38% | Poucas páginas |
| Hidratei | 330 | 115 | 35% | JS-rendered |
| Haskell | 486 | 132 | 27% | Site não publica |
| Griffus | 791 | 99 | 13% | Site não publica |
| Widi Care | 302 | 38 | 13% | JS-rendered |
| Redken | 68 | ? | ? | Importar de prod |
| Acquaflora | 100 | 0 | 0% | Site não publica |
| Forever Liss | 190 | 138 | 73% | Parcial |
| L'Occitane | 256 | ? | ? | Importar de prod |

### Tier 3: Não iniciadas (0% ou sem dados) — 13 marcas
Brae, Elseve, Dove, Bio Extratus, Aneethun, Clear, Head & Shoulders, Johnson's Baby, Kimberly-Clark, La Roche Posay, Loreal Prof, Vichy, Natura

## Estratégia por Tipo de Bloqueio

### A) Marcas que publicam INCI online (scrape automático)
**Ação**: Re-rodar `haira scrape --brand <slug>` com blueprints atualizados
**Marcas**: Seda, All Nature, Joico, Forever Liss, Wella, Redken
**Esforço**: 1-2h por marca (ajustar blueprint + rodar)
**Resultado esperado**: +500 produtos INCI

### B) Marcas com INCI parcial (enrichment externo)
**Ação**: Usar BelezaNaWeb/Época Cosméticos como fonte externa via `haira enrich`
**Marcas**: Haskell, Griffus, Hidratei, Widi Care, Acquaflora, Apice
**Bloqueio**: WAF/IP blocking em datacenter — scrape local + migrate
**Esforço**: 2-3h por marca
**Resultado esperado**: +800 produtos INCI

### C) Marcas sem INCI online (entrada manual)
**Ação**: Clarisse/Fernanda usam a interface INCI tag input para inserir da embalagem
**Marcas**: Brae (224), Elseve (228), Bio Extratus (197), Dove (116), Aneethun (118)
**Prioridade**: Brae e Elseve primeiro (maior volume)
**Esforço**: ~2min por produto, ~15h total para todas
**Resultado esperado**: +883 produtos INCI

### D) Marcas não scrapeadas ainda (onboarding completo)
**Ação**: `brand-onboarding` agent — registro, blueprint, discovery, scrape
**Marcas**: Natura, Clear, H&S, Johnson's, Kimberly-Clark, La Roche Posay, L'Oréal Prof, Vichy
**Bloqueio**: Maioria multinacional sem INCI no site → combinar scrape + manual
**Esforço**: 3-5h por marca
**Resultado esperado**: depende da disponibilidade de INCI nos sites

### E) Non-hair cleanup (O Boticário + Eudora)
**Ação**: Rodar taxonomy filter para marcar ~3.000 produtos non-hair (desodorante, batom, etc.)
**Resultado**: Números de cobertura INCI ficam mais precisos (excluindo non-hair do cálculo)
**Esforço**: 1h (script + validação)

## Fases de Execução

### Fase 1: Quick wins (1-2 dias)
1. Re-scrape Tier 2 marcas com blueprint (A): Seda, Joico, Forever Liss, Wella, Redken
2. Non-hair cleanup de O Boticário + Eudora (E)
3. Deploy dados limpos

### Fase 2: Enrichment externo (3-5 dias)
1. Configurar enrichment local (BelezaNaWeb source)
2. Rodar para Haskell, Griffus, Hidratei, Widi Care, Acquaflora, Apice (B)
3. Migrate para produção

### Fase 3: Onboarding novas marcas (1 semana)
1. Brand onboarding para Natura, Clear, H&S, etc. (D)
2. Scrape + enrich + migrate

### Fase 4: Entrada manual (ongoing)
1. Treinar Clarisse/Fernanda na interface de tag input
2. Priorizar Brae, Elseve, Bio Extratus (C)
3. Meta: 10 produtos/dia por pessoa

## Meta Final

| Métrica | Atual | Meta |
|---------|-------|------|
| Marcas Principais ativas | 14/42 | 42/42 |
| INCI Coverage geral | 52.7% | >80% |
| Produtos com INCI | 5.784 | >9.000 |
| Ingredientes padronizados | 2.076 | 2.500+ |
