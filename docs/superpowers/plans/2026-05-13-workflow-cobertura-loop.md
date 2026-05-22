# Workflow automático de cobertura — Loop até 100%

> **Jira:** documentado sob o épico-log [HAIRA-143](https://sanchescreative.atlassian.net/browse/HAIRA-143),
> tarefa [HAIRA-144](https://sanchescreative.atlassian.net/browse/HAIRA-144) (cobertura).
> Cada wave vira um comentário datado na HAIRA-144.

## Objetivo

Loop in-session que avança a cobertura de marcas até a meta, documentando cada
passo. Meta primária: **250 marcas com ≥10 produtos** (hoje: 127 → faltam 123).
Meta de catálogo: ≥600 marcas com qualquer produto (hoje: 146).

## Motor: `scripts/next_wave.py`

Escolhe a próxima leva priorizando por probabilidade de sucesso (afinado pelas waves 1-7):

1. **tier_2 com blueprint, 0 prod** (51) — maior poço inexplorado
2. **tier_1 com 1-9 prod** (15) — re-scrape pode subir pra ≥10
3. **tier_2 sem blueprint, 0 prod** (116) — precisa `haira blueprint` antes
4. **tier_1 com blueprint, 0 prod** (17) — já falharam nas waves 6-7, fim da fila

Fila total atual: **199 marcas**. Comandos:
```bash
.venv/bin/python scripts/next_wave.py            # resumo humano do backlog
.venv/bin/python scripts/next_wave.py --size 8 --json  # próxima leva (loop consome)
```

## Ciclo do loop (cada iteração)

```
1. next_wave.py --size 8 --json  → lê próxima leva (slug + needs_blueprint)
2. cp haira.db haira.db.bak.<ts>_pre_loop_wave   (1 backup por wave)
3. Para cada marca da leva (em paralelo, até 8 — SQLite aguenta scrapes curtos):
     - se needs_blueprint:  haira blueprint --brand <slug>
     - haira scrape --brand <slug>
     - haira labels  --brand <slug>
4. Medir delta: produtos +N, marcas ≥10 +M, INCI global
5. git add config/blueprints/*.yaml data/waves/ + commit "feat(loop): wave NN"
6. Comentar resultado na HAIRA-144 (tabela marca|prod|INCI%, delta acumulado)
7. Se queue_remaining == 0 OU brands_ge10 >= 250 → PARAR loop
   Senão → próxima iteração
```

**Regra SQLite:** nunca rodar re-scrape pesado (o-boticario, 90 min) concorrente
com a wave — causa "database is locked". Waves curtas de 8 em paralelo são OK.

## Backlog completo até 100% (frentes)

| # | Frente | Estado | Mecanismo |
|---|---|---|---|
| 1 | Cobertura tier_2 c/ blueprint (51) | fila | este loop |
| 2 | Cobertura tier_1 low re-scrape (15) | fila | este loop |
| 3 | Cobertura tier_2 sem blueprint (116) | fila | este loop (+blueprint) |
| 4 | Re-triagem tier_4 (345) via source-scrape | pendente | inci-enricher + VTEX API ([HAIRA-146](https://sanchescreative.atlassian.net/browse/HAIRA-146)) |
| 5 | Cleanup non_hair global (2.357) | pendente | script + data-quality-auditor |
| 6 | Quarantined sweep (2.652 → <50) | pendente | auto_resolve layered |
| 7 | Moon deploy MVP | pendente | [HAIRA-145](https://sanchescreative.atlassian.net/browse/HAIRA-145) |
| 8 | Infra Postgres (SQLite efêmero) | pendente | escopo separado |

## Definition of done (cobertura)

```sql
-- Meta primária
SELECT COUNT(*) FROM (SELECT brand_slug FROM products GROUP BY brand_slug HAVING COUNT(*) >= 10); -- >= 250
-- Meta catálogo
SELECT COUNT(DISTINCT brand_slug) FROM products; -- >= 600
```

## Como retomar / parar

- **Retomar:** rodar o loop de novo — `next_wave.py` recalcula a fila do estado atual do DB, então é idempotente (marcas já com ≥10 saem da fila).
- **Parar:** interromper a sessão a qualquer momento; o progresso já commitado e comentado no Jira persiste.
