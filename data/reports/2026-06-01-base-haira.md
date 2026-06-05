# Relatório da Base HAIRA — Produtos

_Gerado em 2026-06-01 17:55 a partir do Postgres de produção._

## 1. Visão geral

- **Total no banco**: 27,093
- **Capilares (relevantes)**: 22,030 (81%)
- **Não-capilares marcados**: 5,063 (19%)
- **Marcados como kit**: 1,043

**Capilares por status:**

| Status | Quantidade | % |
|---|---:|---:|
| `catalog_only` | 14,224 | 64.6% |
| `verified_inci` | 7,411 | 33.6% |
| `quarantined` | 395 | 1.8% |


**Universo recomendável pela Moon** (verified_inci + tipo + capilar): **6,710**

## 2. Distribuição por tipo de produto (universo recomendável)

| Tipo | Quantidade |
|---|---:|
| shampoo | 1,491 |
| conditioner | 757 |
| mask | 751 |
| cream | 506 |
| oil_serum | 486 |
| coloracao | 419 |
| oxidante | 348 |
| reconstructor | 284 |
| gel | 227 |
| leave_in | 194 |
| ativador | 160 |
| reparador | 147 |
| spray | 135 |
| finisher | 130 |
| tonic | 126 |
| treatment | 115 |
| protetor | 100 |
| ampule | 82 |
| relaxante | 60 |
| descolorante | 46 |
| mousse | 32 |
| exfoliant | 30 |
| wax | 24 |
| paste | 20 |
| pomade | 19 |
| pasta | 8 |
| kit | 8 |
| clay | 3 |
| texturizer | 2 |

## 3. Marcas nacionais (BR) — top 30 por volume

Curadoria manual de marcas nacionais. Conta: total de produtos + verified_inci + kits.

| Marca | Total | Verified INCI | Kits | % INCI |
|---|---:|---:|---:|---:|
| `eudora` | 956 | 236 | 3 | 25% |
| `griffus` | 783 | 96 | 5 | 12% |
| `salon-line` | 774 | 757 | 145 | 98% |
| `amend` | 706 | 629 | 430 | 89% |
| `o-boticario` | 585 | 302 | 34 | 52% |
| `haskell` | 481 | 131 | 43 | 27% |
| `beleza-natural` | 409 | 206 | 17 | 50% |
| `belliz-company` | 405 | 1 | 0 | 0% |
| `dyusar` | 367 | 31 | 0 | 8% |
| `left-cosmeticos` | 360 | 256 | 14 | 71% |
| `felps-professional` | 350 | 219 | 6 | 63% |
| `hidratei` | 328 | 112 | 30 | 34% |
| `natuhair` | 328 | 214 | 0 | 65% |
| `widi-care` | 315 | 44 | 1 | 14% |
| `b-o-b-bars` | 299 | 73 | 14 | 24% |
| `keragen` | 284 | 249 | 6 | 88% |
| `flora-pura` | 262 | 0 | 0 | 0% |
| `spa-cosmetics` | 250 | 12 | 0 | 5% |
| `abelha-rainha` | 249 | 0 | 0 | 0% |
| `red-iron` | 242 | 47 | 1 | 19% |
| `natura` | 234 | 137 | 0 | 59% |
| `brae` | 228 | 1 | 0 | 0% |
| `elseve` | 227 | 5 | 0 | 2% |
| `inoar` | 217 | 201 | 1 | 93% |
| `bio-extratus` | 197 | 0 | 0 | 0% |
| `gota-dourada` | 197 | 4 | 0 | 2% |
| `muriel` | 177 | 5 | 0 | 3% |
| `facinatus-cosmeticos` | 167 | 21 | 0 | 13% |
| `seda` | 146 | 104 | 0 | 71% |
| `aneethun` | 118 | 0 | 0 | 0% |

## 4. Marcas internacionais — top 20 por volume

| Marca | Total | Verified INCI | Kits | % INCI |
|---|---:|---:|---:|---:|
| `kerastase` | 272 | 128 | 9 | 47% |
| `keune` | 268 | 251 | 48 | 94% |
| `dove` | 115 | 3 | 0 | 3% |
| `redken` | 112 | 28 | 0 | 25% |
| `pantene` | 54 | 44 | 0 | 81% |
| `tresemme` | 32 | 32 | 0 | 100% |
| `wella` | 23 | 9 | 0 | 39% |
| `head-and-shoulders` | 5 | 0 | 0 | 0% |

## 5. Marcas com gap crítico de INCI (verified ≤ 10% do total)

Marcas que mais precisam de parceria/fonte externa pra fechar INCI.

| Marca | Total | Verified | % |
|---|---:|---:|---:|
| `belliz-company` | 405 | 1 | 0% |
| `fox-for-men` | 375 | 0 | 0% |
| `dyusar` | 367 | 31 | 8% |
| `de-benguela` | 286 | 0 | 0% |
| `london-cosmeticos` | 276 | 2 | 1% |
| `flora-pura` | 262 | 0 | 0% |
| `spa-cosmetics` | 250 | 12 | 5% |
| `abelha-rainha` | 249 | 0 | 0% |
| `brae` | 228 | 1 | 0% |
| `elseve` | 227 | 5 | 2% |
| `loccitane` | 224 | 2 | 1% |
| `philco` | 218 | 0 | 0% |
| `gota-dourada` | 197 | 4 | 2% |
| `bio-extratus` | 197 | 0 | 0% |
| `wbeauty-cosmeticos` | 196 | 0 | 0% |
| `arvensis-cosmeticos-naturais` | 189 | 5 | 3% |
| `muriel` | 177 | 5 | 3% |
| `mahair-cosmetics` | 169 | 16 | 9% |
| `baume` | 158 | 12 | 8% |
| `capicilin` | 151 | 0 | 0% |

## 6. Marcas reportadas pela Clarisse (status atual)

- **truss**: 0 produtos / 0 verified — TRUSS — bloqueada por Cloudflare, blueprint OK, scraper agora roda (HAIRA-159 fixed)
- **davines**: 0 produtos / 0 verified — DAVINES — URL preenchida hoje, ainda sem scrape inicial
- **amend**: 706 produtos / 629 verified — AMEND — site domina catálogo com kits (61% são kits)
- **eudora**: 1804 produtos / 695 verified — EUDORA — na verdade está OK (~700 verified após filtro não-capilares)
- **haskell**: 482 produtos / 132 verified — HASKELL — gap real de INCI no site (~28% verified)
- **elseve**: 228 produtos / 5 verified — ELSEVE — só ~2% verified, padrão BR de não publicar INCI
- **redken**: 112 produtos / 28 verified — REDKEN — gap real (~25% verified)
- **lola-cosmetics**: 5 produtos / 0 verified — LOLA — bloqueada por bug (agora fixed), aguardando re-scrape
- **wella**: 23 produtos / 9 verified — WELLA — só 23 produtos, "sumiram" no histórico

## 7. Base de ingredientes (motor de scoring da Moon)

- **Ingredientes únicos**: 24,542
- **Categorizados** (motor de scoring): 12,347 (50%)
- **Cobertura de ocorrências em produtos**: 80.3%

## 8. Conhecimento proprietário (Doutoras)

- **Documentos**: 4
- **Volume**: 177,342 chars (~44,335 tokens)

| Fonte | Tamanho |
|---|---:|
| Haira-Regras-3.0.docx | 113,416 chars |
| Rotinas e Produtos - Haira.docx | 30,928 chars |
| Dica do Dia.docx | 23,779 chars |
| Scan de Produto.docx | 9,219 chars |

## 9. Uso da Moon (estado atual)

- **Usuários cadastrados**: 7
- **Perfis capilares preenchidos**: 3
- **Conversas persistidas**: 0
- **Mensagens trocadas**: 0
- **Feedback 👍/👎**: 0 total (0 👍 / 0 👎)

