"""
Data Loader Module for REIRA Hair Products Dashboard

This module handles:
- Discovery of brand subfolders in ./data
- Loading *_final.json or *_final.csv files (ignoring extract_* files)
- Normalization and enrichment of product data
- Loading and parsing .md summary files
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


# Standard columns expected in the product data
STANDARD_COLUMNS = [
    "Nome do Produto",
    "Marca",
    "Tipo de Produto",
    "Tipo de Cabelo",
    "Descricao",
    "Ingredientes",
    "Modo de Uso",
    "Fase Cronograma",
    "Cabelos Finos",
    "pH",
    "Claims Detectados",
]

# Values to treat as missing/null
MISSING_VALUES = {"N/A", "VAZIO", "n/a", "vazio", "NA", "na", ""}


def discover_data_folders(data_path: str = "./data") -> List[Path]:
    """
    Discover all subfolders in the data directory.

    Args:
        data_path: Path to the root data directory

    Returns:
        List of Path objects for each subfolder
    """
    data_dir = Path(data_path)
    if not data_dir.exists():
        return []

    subfolders = [f for f in data_dir.iterdir() if f.is_dir()]
    return sorted(subfolders)


def find_final_file(folder: Path) -> Optional[Path]:
    """
    Find the *_final.json or *_final.csv file in a folder.
    Prioritizes JSON over CSV. Ignores extract_* files.

    Args:
        folder: Path to the brand subfolder

    Returns:
        Path to the final file, or None if not found
    """
    # First try to find *_final.json
    json_files = list(folder.glob("*_final.json"))
    json_files = [f for f in json_files if not f.name.startswith("extract_")]
    if json_files:
        return json_files[0]

    # Fallback to *_final.csv
    csv_files = list(folder.glob("*_final.csv"))
    csv_files = [f for f in csv_files if not f.name.startswith("extract_")]
    if csv_files:
        return csv_files[0]

    return None


def find_md_file(folder: Path) -> Optional[Path]:
    """
    Find the .md summary file in a folder.

    Args:
        folder: Path to the brand subfolder

    Returns:
        Path to the markdown file, or None if not found
    """
    md_files = list(folder.glob("*.md"))
    if md_files:
        # Return the first .md file found (typically there's only one)
        return md_files[0]
    return None


def load_product_file(file_path: Path) -> pd.DataFrame:
    """
    Load a product file (JSON or CSV) into a DataFrame.

    Args:
        file_path: Path to the file

    Returns:
        DataFrame with product data
    """
    if file_path.suffix.lower() == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    elif file_path.suffix.lower() == ".csv":
        return pd.read_csv(file_path, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def normalize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert N/A, VAZIO, and empty strings to NaN.

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with normalized missing values
    """
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == object:
            # Replace known missing value strings with None
            df[col] = df[col].apply(
                lambda x: None if (pd.isna(x) or str(x).strip() in MISSING_VALUES) else x
            )

    return df


def ensure_standard_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure all standard columns exist in the DataFrame.

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with all standard columns
    """
    df = df.copy()

    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df


def generate_product_id(row: pd.Series) -> str:
    """
    Generate a unique ID for a product based on name and brand.

    Args:
        row: DataFrame row

    Returns:
        Unique hash string
    """
    name = str(row.get("Nome do Produto", ""))
    brand = str(row.get("Marca", ""))
    combined = f"{name}|{brand}"
    return hashlib.md5(combined.encode()).hexdigest()[:12]


def parse_claims(claims_str: Optional[str]) -> List[str]:
    """
    Parse claims string into a list of individual claims.

    Args:
        claims_str: Comma-separated claims string

    Returns:
        List of claims (stripped of whitespace)
    """
    if pd.isna(claims_str) or not claims_str:
        return []

    claims = [c.strip() for c in str(claims_str).split(",")]
    return [c for c in claims if c]


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns to the DataFrame.

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with additional columns
    """
    df = df.copy()

    # Generate unique product ID
    df["product_id"] = df.apply(generate_product_id, axis=1)

    # Parse claims into list
    df["lista_claims"] = df["Claims Detectados"].apply(parse_claims)

    # Boolean flags for completeness
    df["has_ingredientes"] = df["Ingredientes"].notna() & (df["Ingredientes"] != "")
    df["has_modo_uso"] = df["Modo de Uso"].notna() & (df["Modo de Uso"] != "")
    df["has_ph"] = df["pH"].notna() & (df["pH"] != "")
    df["has_claims"] = df["lista_claims"].apply(lambda x: len(x) > 0)

    return df


def load_all_products(data_path: str = "./data") -> pd.DataFrame:
    """
    Load all products from all brand subfolders.

    Args:
        data_path: Path to the root data directory

    Returns:
        Concatenated DataFrame with all products
    """
    folders = discover_data_folders(data_path)

    all_dfs = []

    for folder in folders:
        final_file = find_final_file(folder)
        if final_file:
            try:
                df = load_product_file(final_file)
                df["_source_folder"] = folder.name
                all_dfs.append(df)
            except Exception as e:
                print(f"Warning: Could not load {final_file}: {e}")

    if not all_dfs:
        # Return empty DataFrame with standard columns
        return pd.DataFrame(columns=STANDARD_COLUMNS + ["product_id", "lista_claims",
                                                        "has_ingredientes", "has_modo_uso",
                                                        "has_ph", "has_claims", "_source_folder"])

    # Concatenate all DataFrames
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # Normalize and enrich
    combined_df = ensure_standard_columns(combined_df)
    combined_df = normalize_missing_values(combined_df)
    combined_df = enrich_dataframe(combined_df)

    return combined_df


def parse_md_metrics(md_content: str) -> Dict[str, Optional[str]]:
    """
    Extract metrics from a markdown summary file.

    Args:
        md_content: Raw markdown content

    Returns:
        Dictionary with extracted metrics
    """
    metrics = {
        "total_produtos": None,
        "taxa_sucesso": None,
        "pct_ingredientes": None,
        "pct_modo_uso": None,
        "pct_claims": None,
    }

    # Try to extract total products
    total_match = re.search(r"\*\*Total de produtos extraídos\*\*:\s*(\d+)", md_content)
    if total_match:
        metrics["total_produtos"] = total_match.group(1)

    # Try to extract success rate
    taxa_match = re.search(r"\*\*Taxa de sucesso\*\*:\s*([\d,\.]+%?)", md_content)
    if taxa_match:
        metrics["taxa_sucesso"] = taxa_match.group(1)

    # Try to extract from comparison table (more structured)
    # Pattern: | Com ingredientes | XX% |
    ing_match = re.search(r"Com ingredientes\s*\|\s*([\d,\.]+%?)", md_content)
    if ing_match:
        metrics["pct_ingredientes"] = ing_match.group(1)

    modo_match = re.search(r"Com modo de uso\s*\|\s*([\d,\.]+%?)", md_content)
    if modo_match:
        metrics["pct_modo_uso"] = modo_match.group(1)

    claims_match = re.search(r"Com claims\s*\|\s*([\d,\.]+%?)", md_content)
    if claims_match:
        metrics["pct_claims"] = claims_match.group(1)

    return metrics


def load_brand_summaries(data_path: str = "./data") -> Dict[str, Dict]:
    """
    Load all markdown summaries and parse metrics.

    Args:
        data_path: Path to the root data directory

    Returns:
        Dictionary mapping folder names to summary info
    """
    folders = discover_data_folders(data_path)

    summaries = {}

    for folder in folders:
        md_file = find_md_file(folder)
        if md_file:
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                metrics = parse_md_metrics(content)
                summaries[folder.name] = {
                    "file_name": md_file.name,
                    "content": content,
                    "metrics": metrics,
                }
            except Exception as e:
                print(f"Warning: Could not load {md_file}: {e}")
                summaries[folder.name] = {
                    "file_name": None,
                    "content": None,
                    "metrics": {},
                }
        else:
            summaries[folder.name] = {
                "file_name": None,
                "content": None,
                "metrics": {},
            }

    return summaries


def get_all_unique_claims(df: pd.DataFrame) -> List[str]:
    """
    Extract all unique claims from the DataFrame.

    Args:
        df: DataFrame with lista_claims column

    Returns:
        Sorted list of unique claims
    """
    all_claims = set()
    for claims_list in df["lista_claims"]:
        if claims_list:
            all_claims.update(claims_list)

    return sorted(all_claims)


def get_all_unique_brands(df: pd.DataFrame) -> List[str]:
    """
    Extract all unique brands from the DataFrame.

    Args:
        df: DataFrame with Marca column

    Returns:
        Sorted list of unique brands
    """
    brands = df["Marca"].dropna().unique().tolist()
    return sorted(brands)


def get_all_unique_product_types(df: pd.DataFrame) -> List[str]:
    """
    Extract all unique product types from the DataFrame.

    Args:
        df: DataFrame with Tipo de Produto column

    Returns:
        Sorted list of unique product types
    """
    types = df["Tipo de Produto"].dropna().unique().tolist()
    return sorted(types)


def calculate_completeness_stats(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate completeness statistics for the DataFrame.

    Args:
        df: Input DataFrame

    Returns:
        Dictionary with completeness percentages
    """
    total = len(df)
    if total == 0:
        return {
            "pct_ingredientes": 0.0,
            "pct_modo_uso": 0.0,
            "pct_ph": 0.0,
            "pct_claims": 0.0,
        }

    return {
        "pct_ingredientes": (df["has_ingredientes"].sum() / total) * 100,
        "pct_modo_uso": (df["has_modo_uso"].sum() / total) * 100,
        "pct_ph": (df["has_ph"].sum() / total) * 100,
        "pct_claims": (df["has_claims"].sum() / total) * 100,
    }


def calculate_brand_stats(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Calculate statistics per brand.

    Args:
        df: Input DataFrame

    Returns:
        Dictionary mapping brand names to their stats
    """
    brand_stats = {}

    for brand in df["Marca"].dropna().unique():
        brand_df = df[df["Marca"] == brand]
        total = len(brand_df)

        brand_stats[brand] = {
            "total": total,
            "pct_ingredientes": (brand_df["has_ingredientes"].sum() / total) * 100 if total > 0 else 0,
            "pct_modo_uso": (brand_df["has_modo_uso"].sum() / total) * 100 if total > 0 else 0,
            "pct_claims": (brand_df["has_claims"].sum() / total) * 100 if total > 0 else 0,
        }

    return brand_stats


if __name__ == "__main__":
    # Quick test
    df = load_all_products()
    print(f"Loaded {len(df)} products")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Brands: {get_all_unique_brands(df)}")
    print(f"Claims: {get_all_unique_claims(df)[:10]}...")

    summaries = load_brand_summaries()
    for folder, info in summaries.items():
        print(f"\n{folder}: {info['metrics']}")
