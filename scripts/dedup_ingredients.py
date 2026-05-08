"""Deduplicate ingredients table.

Multiple rows exist for the same ingredient due to:
- Case variants: 'AQUA', 'Aqua', 'aqua'
- Language variants: 'Aqua' (la), 'Água' (pt), 'Water' (en)
- Spelling variants: 'Linalool' / 'Linalol' / 'linalool'

Strategy:
1. Build alias groups from a curated PT↔EN INCI dictionary.
2. Group canonical_names by case-insensitive + accent-stripped key.
3. Pick a master row for each group (highest usage in product_ingredients).
4. Re-point product_ingredients to master.
5. Insert ingredient_aliases for non-master variants.
6. Delete non-master ingredient rows.

Usage:
  python scripts/dedup_ingredients.py --dry-run
  python scripts/dedup_ingredients.py --apply
"""
from __future__ import annotations
import argparse
import sqlite3
import unicodedata
from collections import defaultdict

DB_PATH = "haira.db"

# Curated PT -> EN (INCI canonical) translation. The EN form becomes the
# preferred master name (matches global INCI standard).
PT_TO_EN = {
    "agua": "Aqua",
    "água": "Aqua",
    "water": "Aqua",
    "aqua": "Aqua",

    # Glycerin family
    "glicerol": "Glycerin",
    "glicerina": "Glycerin",
    "glycerin": "Glycerin",

    # Phenoxyethanol
    "fenoxietanol": "Phenoxyethanol",
    "phenoxyethanol": "Phenoxyethanol",

    # Linalool
    "linalol": "Linalool",
    "linalool": "Linalool",

    # Limonene
    "limoneno": "Limonene",
    "limonene": "Limonene",
    "d-limonene": "Limonene",

    # Citronellol
    "citronelol": "Citronellol",
    "citronellol": "Citronellol",

    # Citral
    "citral": "Citral",

    # Coumarin
    "cumarina": "Coumarin",
    "coumarin": "Coumarin",

    # Geraniol
    "geraniol": "Geraniol",

    # Tocopherol (Vit E)
    "tocoferol": "Tocopherol",
    "tocopherol": "Tocopherol",
    "acetato de tocoferila": "Tocopheryl Acetate",
    "tocopheryl acetate": "Tocopheryl Acetate",

    # Citric Acid
    "ácido cítrico": "Citric Acid",
    "acido citrico": "Citric Acid",
    "citric acid": "Citric Acid",

    # Hexyl Cinnamal
    "hexil cinamal": "Hexyl Cinnamal",
    "hexyl cinnamal": "Hexyl Cinnamal",

    # Benzyl Alcohol
    "álcool benzílico": "Benzyl Alcohol",
    "alcool benzilico": "Benzyl Alcohol",
    "benzyl alcohol": "Benzyl Alcohol",

    # Benzyl Salicylate
    "salicilato de benzila": "Benzyl Salicylate",
    "benzyl salicylate": "Benzyl Salicylate",

    # Sodium Chloride
    "cloreto de sódio": "Sodium Chloride",
    "cloreto de sodio": "Sodium Chloride",
    "sodium chloride": "Sodium Chloride",

    # Disodium EDTA
    "edetato dissódico": "Disodium EDTA",
    "edta dissódico": "Disodium EDTA",
    "disodium edta": "Disodium EDTA",

    # Potassium Sorbate
    "sorbato de potássio": "Potassium Sorbate",
    "potassium sorbate": "Potassium Sorbate",

    # Sodium Benzoate
    "benzoato de sódio": "Sodium Benzoate",
    "sodium benzoate": "Sodium Benzoate",

    # Caprylic/Capric Triglyceride
    "triglicerídeo caprílico/cáprico": "Caprylic/Capric Triglyceride",
    "trigliceride caprilic capric": "Caprylic/Capric Triglyceride",
    "caprylic/capric triglyceride": "Caprylic/Capric Triglyceride",

    # Caprylyl Glycol
    "caprililglicol": "Caprylyl Glycol",
    "caprylyl glycol": "Caprylyl Glycol",

    # Propylene Carbonate
    "carbonato de propileno": "Propylene Carbonate",
    "propylene carbonate": "Propylene Carbonate",

    # Sodium Gluconate
    "gliconato de sódio": "Sodium Gluconate",
    "sodium gluconate": "Sodium Gluconate",

    # Hydroxycitronellal
    "hidroxicitronelal": "Hydroxycitronellal",
    "hydroxycitronellal": "Hydroxycitronellal",

    # Alpha-isomethyl ionone
    "alfa-isometil ionona": "Alpha-Isomethyl Ionone",
    "alpha-isomethyl ionone": "Alpha-Isomethyl Ionone",

    # Iron oxides
    "óxido de ferro amarelo": "CI 77492",
    "óxido de ferro vermelho": "CI 77491",
    "óxido de ferro preto": "CI 77499",

    # Silicon dioxide
    "dióxido de silício": "Silica",
    "dioxide de silicio": "Silica",
    "silica": "Silica",
    "silicon dioxide": "Silica",

    # Panthenol (provitamin B5)
    "pantenol": "Panthenol",
    "panthenol": "Panthenol",
    "d-pantenol": "Panthenol",
    "d-panthenol": "Panthenol",
    "provitamina b5": "Panthenol",

    # Dimethicone (silicone)
    "dimeticona": "Dimethicone",
    "dimethicone": "Dimethicone",

    # Cetearyl Alcohol
    "álcool cetoestearílico": "Cetearyl Alcohol",
    "alcool cetoestearilico": "Cetearyl Alcohol",
    "cetearyl alcohol": "Cetearyl Alcohol",

    # Cetrimonium Chloride
    "cloreto de cetrimônio": "Cetrimonium Chloride",
    "cetrimonium chloride": "Cetrimonium Chloride",

    # Cocamidopropyl Betaine (anfótero)
    "cocoamidopropil betaína": "Cocamidopropyl Betaine",
    "cocamidopropyl betaine": "Cocamidopropyl Betaine",

    # Propylene Glycol
    "propilenoglicol": "Propylene Glycol",
    "propylene glycol": "Propylene Glycol",

    # Methylisothiazolinone, Methylchloroisothiazolinone (preservativos)
    "metilisotiazolinona": "Methylisothiazolinone",
    "methylisothiazolinone": "Methylisothiazolinone",
    "metilcloroisotiazolinona": "Methylchloroisothiazolinone",
    "methylchloroisothiazolinone": "Methylchloroisothiazolinone",

    # BHT
    "bht": "BHT",
    "butyl hydroxytoluene": "BHT",
    "butil-hidroxitolueno": "BHT",

    # Perfume / Parfum / Fragrance
    "perfume": "Parfum",
    "parfum": "Parfum",
    "fragrância": "Parfum",
    "fragrancia": "Parfum",
    "fragrance": "Parfum",
}


def normalize(name: str) -> str:
    """Lowercase + strip accents for grouping key."""
    if not name:
        return ""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return n.lower().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        print("Pass --dry-run or --apply")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch all ingredients with usage count
    rows = list(c.execute("""
        SELECT i.id, i.canonical_name, COUNT(pi.id) as usage
        FROM ingredients i
        LEFT JOIN product_ingredients pi ON pi.ingredient_id = i.id
        GROUP BY i.id
    """))
    print(f"Total ingredients: {len(rows)}")

    # Build groups
    # Key 1: PT↔EN dictionary mapping
    # Key 2: case-insensitive accent-stripped name
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        norm = normalize(r["canonical_name"])
        # Use dictionary mapping if known
        canonical_en = PT_TO_EN.get(norm, None)
        key = canonical_en or norm  # group by EN form, else by normalized
        groups[key].append(r)

    # Filter groups with >1 row
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"Duplicate groups: {len(dup_groups)}")
    total_to_merge = sum(len(v) - 1 for v in dup_groups.values())
    print(f"Rows to merge into masters: {total_to_merge}")

    if args.dry_run:
        # Show top 10 by usage
        sorted_groups = sorted(dup_groups.items(),
                               key=lambda x: -sum(r["usage"] for r in x[1]))
        print("\nTop 20 dup groups by total usage:")
        for k, v in sorted_groups[:20]:
            names = " | ".join(f"{r['canonical_name']}({r['usage']})" for r in v)
            print(f"  {k:<25} → {names}")
        conn.close()
        return

    # Apply: merge each group
    merged = 0
    aliased = 0
    for key, group in dup_groups.items():
        # Pick master: highest usage; tiebreaker = English-looking (uses PT_TO_EN value if any)
        en_form = key if key in PT_TO_EN.values() else None
        master = None
        if en_form:
            for r in group:
                if r["canonical_name"] == en_form:
                    master = r
                    break
        if master is None:
            master = max(group, key=lambda r: (r["usage"], -len(r["canonical_name"])))

        master_id = master["id"]
        master_name = master["canonical_name"]

        for r in group:
            if r["id"] == master_id:
                continue
            # Update product_ingredients to master
            try:
                # Avoid creating duplicate (product_id, ingredient_id) pairs
                c.execute("""UPDATE OR IGNORE product_ingredients
                             SET ingredient_id = ?
                             WHERE ingredient_id = ?""", (master_id, r["id"]))
                # Delete remaining rows (those that conflicted)
                c.execute("DELETE FROM product_ingredients WHERE ingredient_id = ?", (r["id"],))
                # Save alias
                c.execute("""INSERT OR IGNORE INTO ingredient_aliases (id, ingredient_id, alias, language)
                             VALUES (lower(hex(randomblob(16))), ?, ?, ?)""",
                          (master_id, r["canonical_name"], "auto"))
                aliased += 1
                # Delete the merged ingredient
                c.execute("DELETE FROM ingredients WHERE id = ?", (r["id"],))
                merged += 1
            except sqlite3.IntegrityError as e:
                print(f"  WARN: {r['canonical_name']} -> {master_name}: {e}")

    conn.commit()
    conn.close()
    print(f"\nDeleted {merged} duplicate ingredients, created {aliased} aliases.")


if __name__ == "__main__":
    main()
