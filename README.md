# HAIRA - Dashboard de Produtos Capilares

Dashboard interativo para explorar e analisar produtos capilares de diversas marcas profissionais.

## Funcionalidades

- **Tabela interativa** com ordenacao e paginacao
- **Visualizacao em cards** com ingredientes visiveis
- **Detalhes completos** de cada produto
- **Filtros avancados**: marca, tipo de produto, claims, tipo de cabelo
- **Busca textual** em nome, descricao e ingredientes
- **Resumo por marca** com estatisticas de completude

## Marcas Incluidas

- Kerastase
- L'Oreal Professionnel
- La Roche-Posay Kerium
- Redken

## Estrutura do Projeto

```
hairaproducts/
├── app.py              # Aplicacao Streamlit principal
├── data_loader.py      # Carregamento e normalizacao de dados
├── filters.py          # Funcoes de filtragem
├── requirements.txt    # Dependencias Python
├── Procfile           # Config para Railway/Heroku
├── railway.json       # Config especifica Railway
├── runtime.txt        # Versao Python
└── data/              # Dados dos produtos
    ├── Kerasterse/
    ├── LaRoche/
    ├── Loreal/
    └── Redken/
```

## Instalacao Local

```bash
# Clonar o repositorio
git clone https://github.com/SEU_USUARIO/hairaproducts.git
cd hairaproducts

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# ou: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Rodar o dashboard
streamlit run app.py
```

O dashboard estara disponivel em `http://localhost:8501`

## Deploy no Railway

1. Faca fork/clone deste repositorio
2. Conecte ao Railway (railway.app)
3. Crie um novo projeto a partir do GitHub
4. O Railway detectara automaticamente o Streamlit
5. Deploy automatico a cada push

## Estrutura dos Dados

Cada produto contem:

| Campo | Descricao |
|-------|-----------|
| Nome do Produto | Nome completo do produto |
| Marca | Marca/linha do produto |
| Tipo de Produto | Categoria (Shampoo, Mascara, etc) |
| Tipo de Cabelo | Indicacao de tipo de cabelo |
| Descricao | Descricao detalhada |
| Ingredientes | Lista de ingredientes (INCI) |
| Modo de Uso | Instrucoes de uso |
| Fase Cronograma | Fase do cronograma capilar |
| pH | Valor de pH (quando disponivel) |
| Claims Detectados | Beneficios e claims do produto |

## Tecnologias

- Python 3.11+
- Streamlit
- Pandas

## Licenca

Projeto desenvolvido para fins educacionais e de pesquisa.
