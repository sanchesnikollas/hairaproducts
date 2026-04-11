# Plano: Aprimorar Tudo — HAIRA Perfeito

## Estado Atual (09/04/2026)

```
10.697 hair products | 46 marcas | 4.570 ingredientes
INCI:       45.8% (4.894)     ← teto automação, resto = manual/foto
Categoria:  85.3% (9.120)
Descrição:  71.7% (7.673)
Imagem:     83.9% (8.977)
Preço:      51.0% (5.454)
Selos:      85.2% (9.114)
```

Produção: 8 deploys aplicados, 5 usuários, foto upload + selos + Shopify UI live.

---

## Fase 1: Qualidade de Dados (1-2 dias dev)

### 1.1 Validação dupla em todos os campos
**Backend** (`src/api/routes/ops.py` + `src/core/field_validator.py`):
- Nome: min 5 chars, sem URLs, sem nomes genéricos ("Shampoo"), sem artigos de blog
- Categoria: obrigatória, validada contra VALID_CATEGORIES
- INCI: mínimo 3 ingredientes para ser "verified", ingredientes em Title Case
- Preço: R$1-R$5.000, número positivo
- Volume: regex pattern (300ml, 1L, 500g)
- URL: formato válido com scheme
- Descrição: min 20 chars, não pode ser cópia do nome
- Sem ingredientes duplicados no mesmo produto

**Frontend** (`OpsProductDetail.tsx`):
- Bordas vermelhas em campos inválidos
- Tooltips de erro inline
- Save bloqueado se houver ERROR (WARNING permite salvar)

### 1.2 Fix cleanup endpoint em produção
- O endpoint `POST /api/ops/cleanup-ingredients` deu Internal Server Error
- Debugar o SQL (provavelmente `func.text` não existe, trocar por `text()`)
- Rodar em prod para limpar ingredientes-lixo que as meninas viram

### 1.3 Preencher categorias restantes (1.577 sem)
- Script que usa LLM para categorizar por nome do produto
- Ou regras manuais mais agressivas
- Meta: 95%+ com categoria

---

## Fase 2: Upload de Foto Aprimorado (2-3 dias dev)

### 2.1 Melhorar extração por foto
- Testar com fotos reais de diferentes ângulos/qualidades
- Prompt engineering para extrair: nome, marca, INCI, categoria, volume, claims/selos
- Suportar fotos do rótulo frontal (nome + marca) E traseiro (INCI + composição)
- Múltiplas fotos por produto (frente + verso)

### 2.2 Criar novo produto a partir de foto
- Botão "Novo produto via foto" na lista de Produtos
- Fluxo: upload → extração AI → preenche formulário → usuária revisa → salva
- A foto vira evidência (extraction_method="photo_vision")

### 2.3 Melhorar UX do upload
- Drag and drop mais visível
- Preview da foto antes de enviar
- Barra de progresso durante extração
- Comparação lado-a-lado: valores atuais vs extraídos
- Checkboxes para selecionar quais campos aplicar

---

## Fase 3: Rastreio de Origem (1-2 dias dev)

### 3.1 Evidence em toda edição manual
- Toda vez que um campo é editado via ops panel, criar `ProductEvidenceORM`
- Campos: `extraction_method="manual"`, `source_url="ops://manual/{user_id}"`
- Timestamp + user name

### 3.2 Mostrar proveniência no produto
- Ao lado de cada campo no detalhe do produto: "via scraper 03/15" ou "manual por Clarisse 04/09"
- Ícone pequeno + tooltip com detalhes
- Histórico de edições por campo (quem mudou o quê e quando)

### 3.3 Dashboard de atividade da equipe
- Quem editou mais produtos esta semana
- Quais campos foram mais preenchidos
- Meta semanal de edições por pessoa

---

## Fase 4: INCI em Português + Mapeamento (2-3 dias dev)

### 4.1 Suporte bilíngue no banco de ingredientes
- Coluna `inci_name` (inglês/latim) + `canonical_name` (português)
- Autocomplete busca em ambos os idiomas
- Quando Clarisse digita "Água", sugere tanto "Água" quanto "Aqua (Water)"

### 4.2 Mapeamento de ingredientes para categorias
- Categorizar os 4.570 ingredientes: silicone, sulfato, óleo, proteína, conservante, etc.
- Usar LLM para classificar automaticamente em batch
- Isso melhora a detecção de selos (hoje é por keyword, com categorias seria mais preciso)

### 4.3 Página de ingrediente individual
- Clicar num ingrediente mostra: nome, INCI, categoria, sinônimos, em quantos produtos aparece, quais marcas usam
- Útil para análise de tendências

---

## Fase 5: Detecção Automática de Selos (1-2 dias dev)

### 5.1 Escanear página do produto durante scrape
- Detectar keywords na página: "Vegano", "Cruelty Free", "Sem Parabenos", etc.
- Integrar no pipeline de extração (depois do INCI, antes do labels)
- Testado com O Boticário — funciona

### 5.2 Selos por foto da embalagem
- Quando faz upload de foto, o AI Vision também detecta selos visíveis
- Ícones de certificação na embalagem (cruelty free bunny, vegan leaf, etc.)

### 5.3 Selos por claims da descrição
- Escanear campo `description` por claims: "fórmula vegana", "livre de sulfatos"
- Adicionar ao `product_labels.detected` automaticamente

---

## Fase 6: UX Aprimorada (2-3 dias dev)

### 6.1 Dashboard melhorado
- Gráfico de evolução INCI por semana
- Top marcas por completude
- Produtos editados recentemente pela equipe
- Meta de cobertura com progresso visual

### 6.2 Filtros avançados na lista de produtos
- Filtrar por: "sem INCI", "sem descrição", "sem preço", "sem categoria"
- Combinação de filtros (ex: "Haskell + sem INCI")
- Exportar lista filtrada para CSV

### 6.3 Bulk edit
- Selecionar múltiplos produtos e editar campo em lote
- Ex: selecionar 20 shampoos sem categoria → marcar todos como "shampoo"
- Ex: selecionar 10 produtos → marcar como "aprovado"

### 6.4 Modo "Preencher Rápido"
- Interface focada: mostra 1 produto por vez, campos a preencher destacados
- Botões de ação rápida: "Próximo" / "Pular" / "Salvar e Próximo"
- Prioriza produtos com mais campos faltantes
- Ideal para sessões de trabalho da equipe

---

## Fase 7: Migrate + Deploy (1 dia)

### 7.1 Migrate dados limpos local → produção
- Exportar produtos atualizados (categorias, non-hair, confiança)
- Importar via `/api/admin/migrate` em produção
- Verificar que os 4 usuários funcionam

### 7.2 Deploy final com todas as features
- Validação, evidence, foto upload melhorado
- Build + `railway up`

### 7.3 Documentação
- Guia para a equipe: como usar foto upload, como categorizar, como revisar
- Vídeo curto de 2min mostrando o fluxo

---

## Cronograma Sugerido

| Semana | Fases | Foco |
|--------|-------|------|
| S1 (10-14/04) | 1 + 7 | Validação + deploy dados limpos |
| S2 (15-18/04) | 2 + 3 | Foto upload + evidence |
| S3 (21-25/04) | 4 + 5 | INCI bilíngue + selos automáticos |
| S4 (28/04-02/05) | 6 | UX: dashboard, filtros, bulk edit, modo rápido |

## Metas

| Métrica | Atual | Meta S2 | Meta S4 |
|---------|-------|---------|---------|
| INCI | 45.8% | 55% | 70%+ |
| Categoria | 85.3% | 95% | 99% |
| Descrição | 71.7% | 80% | 90% |
| Preço | 51.0% | 60% | 75% |
| Confiança média | 34.8% | 45% | 60% |
