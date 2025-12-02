# Resumo da Extração de Produtos L'Oréal Professionnel

## Estatísticas Gerais

- **Total de produtos no site**: 83 produtos
- **Produtos com informações extraídas**: 67 produtos (81%)
- **Produtos sem informações**: 16 produtos (19%)

## Detalhamento das Informações Extraídas

| Campo | Produtos com Dados | Percentual |
|-------|-------------------|------------|
| Nome do Produto | 67 | 81% |
| Tipo de Produto | 67 | 81% |
| Descrição | 67 | 81% |
| Modo de Uso | 56 | 67% |
| Ingredientes | 33 | 40% |
| Claims Detectados | 34 | 41% |
| Tipo de Cabelo | Variável | - |

## Tipos de Produtos Encontrados

1. **Shampoo**: 17 produtos
2. **Máscara**: 9 produtos
3. **Condicionador**: 7 produtos
4. **Oxidante**: 5 produtos
5. **Leave-in**: 3 produtos
6. **Mousse**: 2 produtos
7. **Revelador creme**: 2 produtos
8. **Outros**: Sérum, Argila, Spray, etc.

## Principais Linhas/Coleções

- Metal Detox
- Curl Expression
- Absolut Repair Molecular
- Vitamino Color Spectrum
- Scalp Advanced
- Pro Longer
- Blondifier
- Inforcer

## Observações Importantes

1. **Campos não disponíveis no site**:
   - pH: Não encontrado em nenhum produto
   - Fase Cronograma: Raramente especificado (apenas alguns produtos)
   - Cabelos Finos: Raramente especificado

2. **Ingredientes**: Disponíveis em aproximadamente 40% dos produtos. Alguns produtos redirecionam para informações gerais do grupo L'Oréal.

3. **Claims**: Detectados em 41% dos produtos, incluindo:
   - Sem Parabenos
   - Sem Sulfatos
   - Vegano
   - Proteção Térmica
   - Proteção UV
   - Sem Silicones
   - Cruelty-Free

4. **Marca**: Todos os produtos são da marca "L'Oréal Professionnel"

## Arquivos Gerados

1. **produtos_loreal_final.csv** - Formato CSV com todos os produtos
2. **produtos_loreal_final.json** - Formato JSON com todos os produtos
3. **extract_loreal_products.csv** - Dados brutos da extração
4. **extract_loreal_products.json** - Dados brutos em JSON

## Estrutura dos Dados

Cada produto contém os seguintes campos:
- Nome do Produto
- Marca
- Tipo de Produto
- Tipo de Cabelo
- Descrição
- Ingredientes
- Modo de Uso
- Fase Cronograma
- Cabelos Finos
- pH
- Claims Detectados

Campos marcados como "N/A" indicam que a informação não estava disponível no site.
Campos marcados como "VAZIO" indicam que o campo existe mas não foi preenchido.
