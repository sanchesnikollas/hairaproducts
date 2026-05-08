"""Load ingredient_compatibility.yaml into ingredient_category_compatibility table."""
import sqlite3
import yaml
from pathlib import Path

DB = "haira.db"
YAML_PATH = "config/ingredient_compatibility.yaml"


def main():
    data = yaml.safe_load(Path(YAML_PATH).read_text())
    categories = data["categories"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Clear existing
    c.execute("DELETE FROM ingredient_category_compatibility")

    n = 0
    for cat, info in categories.items():
        by_hair = info.get("by_hair_type", {}) or {}
        for hair_type, entry in by_hair.items():
            c.execute(
                "INSERT INTO ingredient_category_compatibility (category, hair_type, score, reason) VALUES (?, ?, ?, ?)",
                (cat, hair_type, entry["score"], entry.get("reason", "")),
            )
            n += 1
    conn.commit()
    conn.close()
    print(f"Loaded {n} compatibility rules across {len(categories)} categories")


if __name__ == "__main__":
    main()
