"""
Filters Module for REIRA Hair Products Dashboard

This module provides pure functions for filtering the product DataFrame
based on various criteria. All functions are stateless and composable.
"""

from typing import List, Optional

import pandas as pd


def filter_by_brands(df: pd.DataFrame, brands: List[str]) -> pd.DataFrame:
    """
    Filter DataFrame to include only specified brands.

    Args:
        df: Input DataFrame
        brands: List of brand names to include

    Returns:
        Filtered DataFrame
    """
    if not brands:
        return df
    return df[df["Marca"].isin(brands)]


def filter_by_product_types(df: pd.DataFrame, product_types: List[str]) -> pd.DataFrame:
    """
    Filter DataFrame to include only specified product types.

    Args:
        df: Input DataFrame
        product_types: List of product types to include

    Returns:
        Filtered DataFrame
    """
    if not product_types:
        return df
    return df[df["Tipo de Produto"].isin(product_types)]


def filter_by_hair_type(df: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """
    Filter DataFrame by hair type using substring search.

    Args:
        df: Input DataFrame
        search_term: Substring to search for in Tipo de Cabelo

    Returns:
        Filtered DataFrame
    """
    if not search_term or not search_term.strip():
        return df

    search_term = search_term.lower().strip()

    # Handle NaN values and search
    mask = df["Tipo de Cabelo"].fillna("").str.lower().str.contains(search_term, regex=False)
    return df[mask]


def filter_by_claims(df: pd.DataFrame, claims: List[str]) -> pd.DataFrame:
    """
    Filter DataFrame to include products that have ALL specified claims.

    Args:
        df: Input DataFrame
        claims: List of claims that must be present

    Returns:
        Filtered DataFrame
    """
    if not claims:
        return df

    def has_all_claims(product_claims: List[str]) -> bool:
        if not product_claims:
            return False
        product_claims_lower = [c.lower() for c in product_claims]
        return all(claim.lower() in product_claims_lower for claim in claims)

    mask = df["lista_claims"].apply(has_all_claims)
    return df[mask]


def filter_by_claims_any(df: pd.DataFrame, claims: List[str]) -> pd.DataFrame:
    """
    Filter DataFrame to include products that have ANY of the specified claims.

    Args:
        df: Input DataFrame
        claims: List of claims (at least one must be present)

    Returns:
        Filtered DataFrame
    """
    if not claims:
        return df

    def has_any_claim(product_claims: List[str]) -> bool:
        if not product_claims:
            return False
        product_claims_lower = [c.lower() for c in product_claims]
        return any(claim.lower() in product_claims_lower for claim in claims)

    mask = df["lista_claims"].apply(has_any_claim)
    return df[mask]


def filter_by_ingredientes(df: pd.DataFrame, only_with_ingredientes: bool) -> pd.DataFrame:
    """
    Filter DataFrame to include only products with ingredients.

    Args:
        df: Input DataFrame
        only_with_ingredientes: If True, keep only products with ingredients

    Returns:
        Filtered DataFrame
    """
    if not only_with_ingredientes:
        return df
    return df[df["has_ingredientes"] == True]


def filter_by_modo_uso(df: pd.DataFrame, only_with_modo_uso: bool) -> pd.DataFrame:
    """
    Filter DataFrame to include only products with usage instructions.

    Args:
        df: Input DataFrame
        only_with_modo_uso: If True, keep only products with modo de uso

    Returns:
        Filtered DataFrame
    """
    if not only_with_modo_uso:
        return df
    return df[df["has_modo_uso"] == True]


def filter_by_ph(df: pd.DataFrame, only_with_ph: bool) -> pd.DataFrame:
    """
    Filter DataFrame to include only products with pH information.

    Args:
        df: Input DataFrame
        only_with_ph: If True, keep only products with pH

    Returns:
        Filtered DataFrame
    """
    if not only_with_ph:
        return df
    return df[df["has_ph"] == True]


def filter_by_text_search(df: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """
    Filter DataFrame by free text search across multiple fields.
    Searches in: Nome do Produto, Descricao, Ingredientes

    Args:
        df: Input DataFrame
        search_term: Text to search for

    Returns:
        Filtered DataFrame
    """
    if not search_term or not search_term.strip():
        return df

    search_term = search_term.lower().strip()

    # Search in multiple columns
    mask = (
        df["Nome do Produto"].fillna("").str.lower().str.contains(search_term, regex=False) |
        df["Descricao"].fillna("").str.lower().str.contains(search_term, regex=False) |
        df["Ingredientes"].fillna("").str.lower().str.contains(search_term, regex=False)
    )
    return df[mask]


def apply_all_filters(
    df: pd.DataFrame,
    brands: Optional[List[str]] = None,
    product_types: Optional[List[str]] = None,
    hair_type_search: Optional[str] = None,
    claims: Optional[List[str]] = None,
    only_with_ingredientes: bool = False,
    only_with_modo_uso: bool = False,
    only_with_ph: bool = False,
    text_search: Optional[str] = None,
    claims_match_mode: str = "any",  # "any" or "all"
) -> pd.DataFrame:
    """
    Apply all filters to the DataFrame in sequence.

    Args:
        df: Input DataFrame
        brands: List of brands to include
        product_types: List of product types to include
        hair_type_search: Substring to search in hair type
        claims: List of claims to filter by
        only_with_ingredientes: If True, keep only products with ingredients
        only_with_modo_uso: If True, keep only products with modo de uso
        only_with_ph: If True, keep only products with pH
        text_search: Free text search term
        claims_match_mode: "any" to match any claim, "all" to match all claims

    Returns:
        Filtered DataFrame
    """
    result = df.copy()

    # Apply each filter in sequence
    result = filter_by_brands(result, brands or [])
    result = filter_by_product_types(result, product_types or [])
    result = filter_by_hair_type(result, hair_type_search or "")

    if claims:
        if claims_match_mode == "all":
            result = filter_by_claims(result, claims)
        else:
            result = filter_by_claims_any(result, claims)

    result = filter_by_ingredientes(result, only_with_ingredientes)
    result = filter_by_modo_uso(result, only_with_modo_uso)
    result = filter_by_ph(result, only_with_ph)
    result = filter_by_text_search(result, text_search or "")

    return result


def sort_dataframe(
    df: pd.DataFrame,
    sort_by: str,
    ascending: bool = True
) -> pd.DataFrame:
    """
    Sort DataFrame by specified column.

    Args:
        df: Input DataFrame
        sort_by: Column name to sort by
        ascending: Sort order

    Returns:
        Sorted DataFrame
    """
    if sort_by not in df.columns:
        return df

    return df.sort_values(by=sort_by, ascending=ascending, na_position="last")


def truncate_text(text: Optional[str], max_length: int = 100) -> str:
    """
    Truncate text to max length with ellipsis.

    Args:
        text: Input text
        max_length: Maximum length before truncation

    Returns:
        Truncated text
    """
    if not text or pd.isna(text):
        return ""

    text = str(text)
    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."


def format_claims_summary(claims_list: List[str], max_claims: int = 3) -> str:
    """
    Format claims list for display in table (truncated).

    Args:
        claims_list: List of claims
        max_claims: Maximum number of claims to show

    Returns:
        Formatted claims string
    """
    if not claims_list:
        return "-"

    if len(claims_list) <= max_claims:
        return ", ".join(claims_list)

    shown = claims_list[:max_claims]
    remaining = len(claims_list) - max_claims
    return f"{', '.join(shown)} (+{remaining})"


def get_bool_icon(value: bool) -> str:
    """
    Convert boolean to icon for display.

    Args:
        value: Boolean value

    Returns:
        Checkmark or X
    """
    return "✓" if value else "✗"
