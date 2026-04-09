# Shopify-style Product Management — Design Spec

## Context

A auditoria visual do HAIRA revelou que a experiencia de edicao de produtos e primitiva: um botao "Editar" que troca entre modo leitura e edicao, campos em lista vertical sem agrupamento logico, e sem feedback visual de estado. O objetivo e transformar a gestao de produtos em uma experiencia Shopify-like com always-edit mode, save bar, e layout 2 colunas.

## Scope

Duas paginas afetadas:
1. **OpsProducts** (lista) — redesign visual com thumbnails, filtros como pills, indicadores visuais
2. **OpsProductDetail** (detalhe/edicao) — rewrite completo com layout 2 colunas Shopify

Nao muda: API backend, modelos de dados, outras paginas Ops.

---

## 1. Product Detail Page (OpsProductDetail)

### Layout

```
┌─────────────────────────────────────────────────────┐
│ [Save Bar - dark, sticky top, appears when dirty]   │
│  ● Alteracoes nao salvas    [Descartar] [Salvar]    │
├─────────────────────────────────────────────────────┤
│ ← Produtos / Nome do Produto                        │
├───────────────────────────────┬─────────────────────┤
│  MAIN COLUMN (2/3)            │ SIDEBAR (1/3 sticky)│
│                               │                     │
│  ┌─ Info Basica ────────────┐ │ ┌─ Status ────────┐ │
│  │ Nome (input)             │ │ │ Editorial  ▾    │ │
│  │ Marca    | Categoria ▾   │ │ │ Publicacao ▾    │ │
│  │ Preco    | Volume        │ │ │ Verificacao: _  │ │
│  │ URL do produto           │ │ └─────────────────┘ │
│  └──────────────────────────┘ │                     │
│                               │ ┌─ Imagem ────────┐ │
│  ┌─ Conteudo ───────────────┐ │ │ [preview/drop]  │ │
│  │ Descricao (textarea)     │ │ │ URL input       │ │
│  │ Composicao (textarea)    │ │ └─────────────────┘ │
│  │ Modo de uso (textarea)   │ │                     │
│  └──────────────────────────┘ │ ┌─ Qualidade ─────┐ │
│                               │ │ 75% [========  ] │ │
│  ┌─ INCI ───────────────────┐ │ │ ✓ nome ✗ preco  │ │
│  │ Lista INCI (textarea)    │ │ │ Confianca: 82%  │ │
│  │ 29 ingredientes ✓ verif  │ │ └─────────────────┘ │
│  │ Ver mapeados →           │ │                     │
│  └──────────────────────────┘ │ ┌─ Historico ─────┐ │
│                               │ │ 2 ultimas revs  │ │
│                               │ │ Ver tudo →      │ │
│                               │ └─────────────────┘ │
└───────────────────────────────┴─────────────────────┘
```

### Comportamento

**Always-edit mode:**
- Todos os campos sao inputs/textareas/selects renderizados diretamente
- Nao existe botao "Editar" nem toggle read/edit
- Campos somente-leitura (brand_slug, verification_status, extraction_method) sao exibidos como texto com estilo disabled

**Dirty state tracking:**
- `useRef` guarda snapshot do estado original (produto como veio da API)
- `useState` guarda estado atual editado
- Comparacao shallow entre original e current determina `isDirty`
- Save bar aparece com transicao suave quando `isDirty === true`

**Save bar:**
- Posicao: `sticky top-0 z-50`
- Background: `bg-ink` (escuro)
- Mostra: indicador amarelo "● Alteracoes nao salvas"
- Botoes: "Descartar" (reseta para original) e "Salvar" (chama `opsUpdateProduct`)
- Warn on leave: `beforeunload` event quando dirty

**Sidebar sticky:**
- `position: sticky; top: 80px` (abaixo da save bar)
- Cards: Status, Imagem, Qualidade, Historico

**Cards da coluna principal:**
1. **Info Basica**: nome (input), marca (readonly), categoria (select das VALID_CATEGORIES), preco (input number), volume (input), URL (input readonly com link)
2. **Conteudo**: descricao (textarea), composicao (textarea), modo de uso (textarea)
3. **INCI**: textarea para lista de ingredientes, contador, badge de verificacao, link para ver ingredientes mapeados (expande inline)

**Cards da sidebar:**
1. **Status**: editorial (select), publicacao (select), verificacao (readonly badge)
2. **Imagem**: preview da imagem se existir, input URL para colar, area de drop futura
3. **Qualidade**: barra de progresso, grid de campos presentes/faltantes (reutilizar logica de DataQualityPanel existente), confianca %
4. **Historico**: 2-3 ultimas revisoes resumidas + link "Ver tudo" que expande lista completa inline

### Categoria dropdown

Valores fixos derivados de `VALID_CATEGORIES`:
- shampoo, condicionador, mascara, tratamento, leave_in, oleo_serum, styling, coloracao, transformacao, kit

---

## 2. Product List Page (OpsProducts)

### Mudancas visuais

**Header:**
- Titulo "Produtos" + contagem total
- Botoes: "Exportar" (futuro, disabled) + "+ Novo Produto"

**Filtros como pills:**
- Search bar full-width
- Abaixo: pills/chips para Status, Marca, Categoria, Verificacao
- Cada pill abre dropdown com opcoes
- Pills ativas mostram valor selecionado com X para limpar

**Tabela:**
- Adicionar coluna thumbnail (32x32px, imagem do produto ou placeholder cinza)
- Adicionar coluna categoria (texto pequeno abaixo do nome)
- Coluna INCI: icone check verde + contagem, ou X vermelho
- Coluna Confianca: numero colorido (verde >80, amarelo >50, vermelho <50)
- Coluna Qualidade: mini barra (ja existe, manter)
- Row click navega para detalhe

**Paginacao:**
- Manter estilo atual com "Anterior / Pagina X / Proxima"

### Modal Novo Produto

Manter modal existente, ajustar:
- Categoria como select (dropdown com VALID_CATEGORIES) em vez de input text
- Adicionar campo image_url_main
- Adicionar campo price e size_volume

---

## 3. Componentes Reutilizaveis

**SaveBar** — componente standalone
- Props: `isDirty: boolean, saving: boolean, onSave: () => void, onDiscard: () => void`
- Renderiza barra escura sticky com animacao de entrada/saida

**ProductCard** (sidebar cards) — pattern de card com titulo
- Props: `title: string, children: ReactNode, action?: ReactNode`

**CategorySelect** — dropdown com categorias validas
- Props: `value: string, onChange: (v: string) => void`
- Hardcoded options from VALID_CATEGORIES

---

## 4. Arquivos a Modificar

| Arquivo | Acao |
|---------|------|
| `frontend/src/pages/ops/OpsProductDetail.tsx` | Rewrite completo |
| `frontend/src/pages/ops/OpsProducts.tsx` | Redesign visual |
| `frontend/src/components/ops/SaveBar.tsx` | Novo componente |
| `frontend/src/components/ops/CategorySelect.tsx` | Novo componente |

Nao modifica: API, ORM, outros componentes ops.

---

## 5. Verificacao

1. `npm run build` sem erros
2. Navegar para `/ops/products` — filtros funcionam, thumbnail aparece, click abre detalhe
3. Navegar para `/ops/products/:id` — campos editaveis, save bar aparece ao editar, salvar funciona
4. Testar discard — campos voltam ao original
5. Testar beforeunload — aviso ao sair com alteracoes pendentes
6. Sidebar sticky — scrolla na coluna principal, sidebar acompanha
7. Categoria dropdown — mostra opcoes validas
