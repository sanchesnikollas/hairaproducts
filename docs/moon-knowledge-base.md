# Moon Knowledge Base — Ordem Canônica

Este documento define a estrutura do conteúdo que alimenta a assistente Moon. A fonte oficial é a pasta `/iamoon/` (entregue em junho/26) — todos os arquivos novos do conhecimento da Moon devem entrar ali e ser ingeridos via `POST /api/admin/knowledge/replace-all`.

## Camadas

| Layer | Arquivo (em `iamoon/`) | Propósito | Onde fica |
|---|---|---|---|
| 0 — Fundação | `COMPÊNDIO HAIRA .docx.md` | Enciclopédia técnica (fisiologia capilar). "Fonte da verdade." | `knowledge_chunks` |
| 0.5 — Premissas | `Inteligência Haira by Fernanda Torres.docx.md` | 16 premissas fundacionais + guia de rotinas. | `knowledge_chunks` |
| 1 — Persona | `Personalidade da Moon - Jun_26.md` | Identidade, tom, situações difíceis. | Hardcoded em `src/core/moon_personality.py` |
| 2 — Q&A técnica | `Perguntas e Respostas - Daniel.md` | 64 Q&A validadas por Dr. Fernanda. | `knowledge_chunks` |
| 2 — Recomendação | `Rotinas e Produtos para Moon.md` | Framework de recomendação por tipo de cabelo. | `knowledge_chunks` |
| 3 — Engagement | `Dica do Dia.docx.md` | +50 dicas curtas com CTA + push. | `knowledge_chunks` |
| 3 — Educação | `Você Sabia.docx.md` | +100 fatos curiosos com profundidade. | `knowledge_chunks` |
| 4 — Suporte | `HAIRA - FAQ.md` | FAQ do app (não vai pra Moon). | `docs/app-faq.md` |

## Ingestão

```bash
# Pré-requisito: pasta iamoon/ presente no container
curl -X POST https://haira-app-production-deb8.up.railway.app/api/admin/knowledge/replace-all \
  -H "Authorization: Bearer <admin-jwt>"
```

O endpoint:
1. Limpa `knowledge_chunks` (tabela inteira)
2. Lê cada arquivo `.md` em `iamoon/`
3. Pula: `HAIRA - FAQ*` e `Personalidade da Moon*` e duplicatas `*(1)*`
4. Encripta e grava em `knowledge_chunks`
5. Reseta cache in-process
6. Próximo `/api/moon/chat` recarrega do DB e injeta no prompt cache Anthropic (5min TTL)

## Persona vs Knowledge

A **persona** da Moon (tom, identidade, situações difíceis) vive **hardcoded** em `src/core/moon_personality.py:MOON_SYSTEM_DEFAULT` — versionado no git. Override via DB através de `/api/admin/moon/config` para ajustes finos sem deploy.

O **conhecimento** (compêndio, Q&A, rotinas, fatos) vive em `knowledge_chunks` — atualizado via endpoint admin.

## Atualizando o conteúdo

1. Coloque a versão nova do arquivo em `iamoon/` (sobrescreva)
2. Rode `POST /api/admin/knowledge/replace-all`
3. Pronto — a Moon usa a versão nova na próxima conversa

## Regra de embasamento da Moon

O system prompt em `moon_personality.py` instrui a Moon a:
- Priorizar `[MATERIAL PROPRIETÁRIO HAIRA]` em toda recomendação
- Citar a fonte ao final (ex.: "(Compêndio)", "(Rotinas e Produtos)")
- Quando não encontrar respaldo no material, dizer "essa orientação ainda não está no nosso material" em vez de improvisar
