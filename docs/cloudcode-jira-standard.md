# Padrão operacional — CloudCode → Jira (OBRIGATÓRIO)

> Este é o padrão oficial de documentação e rastreabilidade para trabalho técnico
> feito via CloudCode (Claude Code) neste projeto. **Nada existe só no código ou só
> na conversa — toda alteração vira documentação acionável no Jira.**

## Destino

- **Site:** `sanchescreative.atlassian.net` · cloudId `715ed417-3bdb-4268-aca5-b49c04cbf59e`
- **Projeto:** `HAIRA` · **Épico-log:** [HAIRA-143](https://sanchescreative.atlassian.net/browse/HAIRA-143)
- **Campos:** Sprint = `customfield_10020` (sprint ativa id 966 "Abril, 27") · Start date = `customfield_10015` · Due = `duedate`
- **MCP:** `createJiraIssue`, `editJiraIssue`, `addCommentToJiraIssue`, `searchJiraIssuesUsingJql`

## Regra principal

Toda atividade executada gera **automaticamente**: contexto técnico, documentação,
rastreabilidade, histórico, ticket Jira, atualização de status e registro de decisão.

| Gatilho | Ação no Jira |
|---|---|
| Nova frente de trabalho | Cria **tarefa filha** de HAIRA-143 (estrutura completa abaixo) |
| Wave / lote / fix executado | **Comentário datado** na tarefa relacionada (métricas antes/depois) |
| Commit relevante | Referenciar hash no comentário/ticket |
| Decisão técnica ou incidente | Registrar como comentário (ex: "branch master only", "SQLite single-writer") |
| Comentário solto do usuário ("ajusta X") | Converter em ticket estruturado + subtarefas + critérios de aceite |
| Mudança de escopo / bloqueio | `editJiraIssue` na tarefa + nota |
| Marca/feature concluída | Atualizar status + Release Notes |

## Estrutura obrigatória de todo ticket

```
## Summary            — resumo claro e objetivo
## Context            — cenário atual e motivação
## Problem            — problema identificado
## Objective          — resultado esperado
## Technical Scope    — arquivos, módulos, impacto
## Acceptance Criteria— checklist validável (- [ ])
## Implementation Plan— passos técnicos
## Risks              — possíveis impactos
## Dependencies       — técnicas e operacionais
## QA Validation      — como validar (queries/comandos)
## Release Notes      — resumo para deploy/release
```

Modelo de referência já aplicado: [HAIRA-152](https://sanchescreative.atlassian.net/browse/HAIRA-152).

## Regras de qualidade

- Nunca criar ticket vago. Nunca deixar alteração sem documentação. Nunca perder contexto técnico.
- Toda tarefa rastreável; toda mudança com histórico; clareza operacional sempre.
- Gestão ágil: identificar épico, relacionar tarefas, sugerir prioridade/labels, detectar bloqueio/duplicidade, categorizar sprint.
- Itens de curto prazo entram na **sprint ativa** com `Start date` + `Due` (não ficam ocultos no backlog). Fechamento/infra futura: datados, fora da sprint atual.

## Backlog 0→100 (estado vivo — HAIRA-143)

| Ticket | Frente |
|---|---|
| HAIRA-144 | Cobertura horizontal (loop de waves) |
| HAIRA-145 | Moon AI — deploy MVP |
| HAIRA-146 | Qualidade INCI — fixes de extração |
| HAIRA-147 | Cobertura source-scrape (distribuidores) |
| HAIRA-148 | Limpeza — non_hair + quarantined |
| HAIRA-149 | Qualidade de campos — price + care_usage |
| HAIRA-150 | Infra — PostgreSQL persistente + segurança |
| HAIRA-151 | Critérios de aceite 100% + manutenção |
| HAIRA-152 | Onboarding manual tier_2 (blueprint artesanal) |

## Aplicação global

Para tornar este padrão válido em **todos os projetos CloudCode** (não só HAIRA),
replicar este arquivo + a seção "Documentação no Jira" do `CLAUDE.md` no
`~/.claude/CLAUDE.md` (config global do usuário) ou num hook de sessão.
