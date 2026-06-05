"""Push categorized ingredients from local DB to production via admin endpoint."""
import os
import sqlite3
import sys
import time
import httpx

BASE = os.environ.get("RAILWAY_URL", "https://haira-app-production-deb8.up.railway.app")
SECRET = os.environ.get("MIGRATION_SECRET", "")
BATCH = 500


def main():
    if not SECRET:
        print("Set MIGRATION_SECRET")
        sys.exit(1)

    conn = sqlite3.connect("haira.db")
    rows = list(conn.execute(
        "SELECT canonical_name, category FROM ingredients WHERE category IS NOT NULL"
    ))
    conn.close()
    print(f"Total to sync: {len(rows)}")

    client = httpx.Client(timeout=60)
    total_updated = 0
    total_not_matched = 0
    for i in range(0, len(rows), BATCH):
        batch = [{"canonical_name": r[0], "category": r[1]} for r in rows[i:i + BATCH]]
        try:
            resp = client.post(
                f"{BASE}/api/admin/sync-ingredient-categories",
                json={"secret": SECRET, "updates": batch},
            )
            data = resp.json()
            up = data.get("updated", 0)
            nm = data.get("not_matched", 0)
            total_updated += up
            total_not_matched += nm
            print(f"  batch {i//BATCH+1}: updated={up} not_matched={nm}", flush=True)
        except Exception as e:
            print(f"  batch {i//BATCH+1}: ERROR {e}", flush=True)
        time.sleep(0.3)

    print(f"\nTotal updated: {total_updated} / not matched: {total_not_matched}")
    client.close()


if __name__ == "__main__":
    main()
