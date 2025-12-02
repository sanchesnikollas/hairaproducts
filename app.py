"""
HAIRA - Dashboard de Produtos Capilares

A Streamlit-based dashboard for exploring hair care product data.
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from data_loader import (
    load_all_products,
    load_brand_summaries,
    get_all_unique_claims,
    get_all_unique_brands,
    get_all_unique_product_types,
    calculate_completeness_stats,
    calculate_brand_stats,
)
from filters import (
    apply_all_filters,
    sort_dataframe,
    truncate_text,
    format_claims_summary,
    get_bool_icon,
)


# Page configuration
st.set_page_config(
    page_title="HAIRA - Dashboard de Produtos Capilares",
    page_icon="💇",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=300)
def load_data():
    """Load and cache all product data."""
    return load_all_products()


@st.cache_data(ttl=300)
def load_summaries():
    """Load and cache brand summaries."""
    return load_brand_summaries()


def render_header_metrics(df: pd.DataFrame):
    """Render the header with global statistics."""
    st.title("HAIRA")
    st.caption("Dashboard de Produtos Capilares")
    st.divider()

    # Calculate stats
    total_products = len(df)
    unique_brands = df["Marca"].nunique()
    stats = calculate_completeness_stats(df)

    # Display metrics in columns
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total de Produtos", total_products)

    with col2:
        st.metric("Marcas", unique_brands)

    with col3:
        st.metric("Com Ingredientes", f"{stats['pct_ingredientes']:.1f}%")

    with col4:
        st.metric("Com Modo de Uso", f"{stats['pct_modo_uso']:.1f}%")

    with col5:
        st.metric("Com Claims", f"{stats['pct_claims']:.1f}%")


def render_sidebar_filters(df: pd.DataFrame):
    """Render sidebar with all filters. Returns filter parameters."""
    st.sidebar.header("Filtros")

    # Brand filter
    all_brands = get_all_unique_brands(df)
    selected_brands = st.sidebar.multiselect(
        "Marca",
        options=all_brands,
        default=[],
        help="Selecione uma ou mais marcas"
    )

    # Product type filter
    all_types = get_all_unique_product_types(df)
    selected_types = st.sidebar.multiselect(
        "Tipo de Produto",
        options=all_types,
        default=[],
        help="Selecione um ou mais tipos de produto"
    )

    # Hair type search
    hair_type_search = st.sidebar.text_input(
        "Tipo de Cabelo (busca)",
        value="",
        help="Digite para buscar no tipo de cabelo"
    )

    # Claims filter
    all_claims = get_all_unique_claims(df)
    selected_claims = st.sidebar.multiselect(
        "Claims",
        options=all_claims,
        default=[],
        help="Selecione claims para filtrar"
    )

    # Claims match mode
    if selected_claims:
        claims_mode = st.sidebar.radio(
            "Modo de busca de claims",
            options=["any", "all"],
            format_func=lambda x: "Qualquer um" if x == "any" else "Todos",
            index=0,
            horizontal=True
        )
    else:
        claims_mode = "any"

    st.sidebar.divider()
    st.sidebar.subheader("Completude")

    # Completeness checkboxes
    only_ingredientes = st.sidebar.checkbox("Apenas com ingredientes", value=False)
    only_modo_uso = st.sidebar.checkbox("Apenas com modo de uso", value=False)
    only_ph = st.sidebar.checkbox("Apenas com pH informado", value=False)

    st.sidebar.divider()

    # Free text search
    text_search = st.sidebar.text_input(
        "Busca livre",
        value="",
        help="Busca em nome, descricao e ingredientes",
        placeholder="Digite para buscar..."
    )

    return {
        "brands": selected_brands,
        "product_types": selected_types,
        "hair_type_search": hair_type_search,
        "claims": selected_claims,
        "claims_match_mode": claims_mode,
        "only_with_ingredientes": only_ingredientes,
        "only_with_modo_uso": only_modo_uso,
        "only_with_ph": only_ph,
        "text_search": text_search,
    }


def render_table_view(df: pd.DataFrame):
    """Render the table view of products with expandable rows."""
    st.subheader(f"Produtos ({len(df)} resultados)")

    if len(df) == 0:
        st.info("Nenhum produto encontrado com os filtros aplicados.")
        return

    # Sorting options
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sort_by = st.selectbox(
            "Ordenar por",
            options=["Nome do Produto", "Marca", "Tipo de Produto"],
            index=0,
            key="table_sort"
        )
    with col2:
        sort_order = st.selectbox(
            "Ordem",
            options=["Crescente", "Decrescente"],
            index=0,
            key="table_order"
        )
    with col3:
        items_per_page = st.selectbox(
            "Itens por pagina",
            options=[10, 20, 50],
            index=1,
            key="table_items"
        )

    # Sort dataframe
    sorted_df = sort_dataframe(df, sort_by, ascending=(sort_order == "Crescente"))

    # Pagination
    total_pages = max(1, (len(sorted_df) + items_per_page - 1) // items_per_page)

    if "table_page" not in st.session_state:
        st.session_state.table_page = 1

    if st.session_state.table_page > total_pages:
        st.session_state.table_page = 1

    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("Anterior", key="table_prev", disabled=st.session_state.table_page <= 1):
            st.session_state.table_page -= 1
            st.rerun()
    with col_info:
        st.markdown(f"**Pagina {st.session_state.table_page} de {total_pages}**")
    with col_next:
        if st.button("Proximo", key="table_next", disabled=st.session_state.table_page >= total_pages):
            st.session_state.table_page += 1
            st.rerun()

    start_idx = (st.session_state.table_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(sorted_df))
    page_df = sorted_df.iloc[start_idx:end_idx]

    # Render each product as an expandable row with tags
    for _, product in page_df.iterrows():
        with st.container(border=True):
            # Main row
            col_name, col_brand, col_type, col_status = st.columns([3, 2, 1, 2])

            with col_name:
                st.markdown(f"**{product['Nome do Produto']}**")

            with col_brand:
                st.caption(product['Marca'] or "-")

            with col_type:
                if pd.notna(product.get('Tipo de Produto')):
                    st.markdown(f"`{product['Tipo de Produto']}`")

            with col_status:
                has_ing = bool(pd.notna(product.get('Ingredientes')) and product.get('Ingredientes'))
                has_modo = bool(pd.notna(product.get('Modo de Uso')) and product.get('Modo de Uso'))
                has_ph = bool(pd.notna(product.get('pH')) and product.get('pH'))
                st.write(f"{'✅' if has_ing else '❌'}Ing {'✅' if has_modo else '❌'}Modo {'✅' if has_ph else '❌'}pH")

            # Claims as tags
            claims = product.get('lista_claims', [])
            if claims:
                # Create tag-like display using columns
                st.markdown("**Claims:**")
                num_cols = min(5, len(claims))
                if num_cols > 0:
                    tag_cols = st.columns(num_cols)
                    for i, claim in enumerate(claims[:10]):
                        with tag_cols[i % num_cols]:
                            st.success(claim)
                    if len(claims) > 10:
                        st.caption(f"+{len(claims) - 10} mais claims")

            # Expandable details
            with st.expander("Ver detalhes completos"):
                if pd.notna(product.get('Tipo de Cabelo')):
                    st.info(f"**Tipo de Cabelo:** {product['Tipo de Cabelo']}")

                if pd.notna(product.get('Descricao')):
                    st.markdown("**Descricao:**")
                    st.write(product['Descricao'])

                if pd.notna(product.get('Ingredientes')):
                    st.markdown("**Ingredientes:**")
                    st.code(product['Ingredientes'], language=None)

                if pd.notna(product.get('Modo de Uso')):
                    st.markdown("**Modo de Uso:**")
                    st.write(product['Modo de Uso'])

    st.caption(f"Mostrando {start_idx + 1}-{end_idx} de {len(sorted_df)} produtos")


def render_product_card(product: pd.Series, show_ingredients: bool = True):
    """Render a single product card using native Streamlit components."""
    with st.container(border=True):
        # Header
        st.markdown(f"**{product['Nome do Produto']}**")
        st.caption(f"{product['Marca'] or 'Marca nao informada'}")

        # Product type badge
        if pd.notna(product.get("Tipo de Produto")):
            st.markdown(f"`{product['Tipo de Produto']}`")

        # Hair type
        if pd.notna(product.get("Tipo de Cabelo")):
            hair_text = truncate_text(product["Tipo de Cabelo"], 100)
            st.info(f"**Cabelo:** {hair_text}")

        # Phase
        if pd.notna(product.get("Fase Cronograma")):
            st.warning(f"**Fase:** {product['Fase Cronograma']}")

        # Claims
        claims = product.get("lista_claims", [])
        if claims:
            claims_display = ", ".join(claims[:6])
            if len(claims) > 6:
                claims_display += f" (+{len(claims) - 6} mais)"
            st.success(f"**Claims:** {claims_display}")

        # Status row
        col1, col2, col3 = st.columns(3)
        with col1:
            has_ing = bool(pd.notna(product.get('Ingredientes')) and product.get('Ingredientes'))
            st.write(f"{'✅' if has_ing else '❌'} Ingredientes")
        with col2:
            has_modo = bool(pd.notna(product.get('Modo de Uso')) and product.get('Modo de Uso'))
            st.write(f"{'✅' if has_modo else '❌'} Modo de Uso")
        with col3:
            has_ph = bool(pd.notna(product.get('pH')) and product.get('pH'))
            st.write(f"{'✅' if has_ph else '❌'} pH")

        # Description
        if pd.notna(product.get("Descricao")):
            with st.expander("Ver Descricao"):
                st.write(product["Descricao"])

        # Ingredients - visible by default when checkbox is on
        if pd.notna(product.get("Ingredientes")) and show_ingredients:
            st.divider()
            st.markdown("**Ingredientes:**")
            st.text(product["Ingredientes"])

        # Modo de Uso
        if pd.notna(product.get("Modo de Uso")):
            with st.expander("Ver Modo de Uso"):
                st.write(product["Modo de Uso"])


def render_cards_view(df: pd.DataFrame):
    """Render the cards view of products."""
    st.subheader(f"Produtos ({len(df)} resultados)")

    if len(df) == 0:
        st.info("Nenhum produto encontrado com os filtros aplicados.")
        return

    # View options
    col1, col2, col3 = st.columns(3)
    with col1:
        columns_count = st.radio(
            "Colunas",
            options=[1, 2, 3],
            index=1,
            horizontal=True,
            key="card_columns"
        )
    with col2:
        show_ingredients = st.checkbox(
            "Mostrar ingredientes",
            value=True,
            key="show_ingredients"
        )
    with col3:
        page_size = st.selectbox(
            "Cards por pagina",
            options=[6, 12, 24],
            index=0,
            key="cards_page_size"
        )

    # Pagination
    total_pages = max(1, (len(df) + page_size - 1) // page_size)

    if "cards_page" not in st.session_state:
        st.session_state.cards_page = 1

    # Ensure page is within bounds
    if st.session_state.cards_page > total_pages:
        st.session_state.cards_page = 1

    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.button("Anterior", key="cards_prev", disabled=st.session_state.cards_page <= 1):
            st.session_state.cards_page -= 1
            st.rerun()

    with col_info:
        st.markdown(f"**Pagina {st.session_state.cards_page} de {total_pages}**")

    with col_next:
        if st.button("Proximo", key="cards_next", disabled=st.session_state.cards_page >= total_pages):
            st.session_state.cards_page += 1
            st.rerun()

    start_idx = (st.session_state.cards_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(df))

    # Display cards in grid
    products_to_show = df.iloc[start_idx:end_idx]

    cols = st.columns(columns_count)
    for idx, (_, product) in enumerate(products_to_show.iterrows()):
        with cols[idx % columns_count]:
            render_product_card(product, show_ingredients=show_ingredients)

    st.caption(f"Mostrando {start_idx + 1}-{end_idx} de {len(df)} produtos")


def render_product_detail(df: pd.DataFrame):
    """Render detailed view of a single product."""
    st.subheader("Detalhe do Produto")

    if len(df) == 0:
        st.info("Nenhum produto disponivel.")
        return

    # Product selector
    product_names = df["Nome do Produto"].tolist()
    selected_product = st.selectbox(
        "Selecione um produto para ver detalhes completos",
        options=product_names,
        index=0,
        key="product_detail_selector"
    )

    if selected_product:
        product = df[df["Nome do Produto"] == selected_product].iloc[0]

        with st.container(border=True):
            # Header
            st.markdown(f"## {product['Nome do Produto']}")
            st.markdown(f"**Marca:** {product['Marca'] or 'Nao informada'}")

            st.divider()

            # Info columns
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Tipo de Produto**")
                st.write(product.get('Tipo de Produto') or "Nao informado")

            with col2:
                st.markdown("**Fase Cronograma**")
                st.write(product.get('Fase Cronograma') or "Nao informado")

            with col3:
                st.markdown("**pH**")
                st.write(product.get('pH') or "Nao informado")

            st.divider()

            # Tipo de Cabelo
            st.markdown("### Tipo de Cabelo")
            if pd.notna(product.get('Tipo de Cabelo')):
                st.info(product['Tipo de Cabelo'])
            else:
                st.write("Nao informado")

            # Claims
            claims = product.get('lista_claims', [])
            if claims:
                st.markdown("### Claims Detectados")
                # Display claims as chips using columns
                claim_cols = st.columns(min(4, len(claims)))
                for i, claim in enumerate(claims):
                    with claim_cols[i % 4]:
                        st.success(claim)

            # Descricao
            st.markdown("### Descricao")
            if pd.notna(product.get('Descricao')):
                st.write(product["Descricao"])
            else:
                st.write("Nao informada")

            # Ingredientes
            st.markdown("### Ingredientes")
            if pd.notna(product.get('Ingredientes')):
                st.code(product["Ingredientes"], language=None)
            else:
                st.warning("Ingredientes nao informados para este produto.")

            # Modo de Uso
            st.markdown("### Modo de Uso")
            if pd.notna(product.get('Modo de Uso')):
                st.write(product["Modo de Uso"])
            else:
                st.write("Nao informado")


def render_brand_summaries(df: pd.DataFrame, summaries: dict):
    """Render the brand summaries section."""
    st.subheader("Resumo por Marca")

    brand_stats = calculate_brand_stats(df)

    for brand, stats in sorted(brand_stats.items()):
        with st.container(border=True):
            col_header, col_count = st.columns([3, 1])
            with col_header:
                st.markdown(f"### {brand}")
            with col_count:
                st.metric("Produtos", stats['total'])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Com Ingredientes", f"{stats['pct_ingredientes']:.1f}%")
            with col2:
                st.metric("Com Modo de Uso", f"{stats['pct_modo_uso']:.1f}%")
            with col3:
                st.metric("Com Claims", f"{stats['pct_claims']:.1f}%")

            # Find matching summary
            matching_folder = None
            for folder_name, summary_info in summaries.items():
                if (folder_name.lower() in brand.lower() or
                    brand.lower().replace(" ", "").replace("-", "") in folder_name.lower() or
                    folder_name.lower() in brand.lower().replace(" ", "").replace("-", "")):
                    matching_folder = folder_name
                    break

            if matching_folder and summaries[matching_folder].get("content"):
                with st.expander("Ver resumo completo da extracao"):
                    st.markdown(summaries[matching_folder]["content"])


def main():
    """Main application entry point."""
    # Load data
    df = load_data()
    summaries = load_summaries()

    if len(df) == 0:
        st.error("Nenhum dado encontrado. Verifique a pasta ./data e seus arquivos.")
        st.stop()

    # Render header with metrics
    render_header_metrics(df)

    # Render sidebar filters
    filter_params = render_sidebar_filters(df)

    # Apply filters
    filtered_df = apply_all_filters(df, **filter_params)

    # Show filter status
    if len(filtered_df) < len(df):
        st.success(f"Filtros aplicados: {len(filtered_df)} de {len(df)} produtos")

    # Main content tabs
    tab_table, tab_cards, tab_detail, tab_summary = st.tabs([
        "Tabela",
        "Cards",
        "Detalhe",
        "Resumo por Marca"
    ])

    with tab_table:
        render_table_view(filtered_df)

    with tab_cards:
        render_cards_view(filtered_df)

    with tab_detail:
        render_product_detail(filtered_df)

    with tab_summary:
        render_brand_summaries(df, summaries)


if __name__ == "__main__":
    main()
