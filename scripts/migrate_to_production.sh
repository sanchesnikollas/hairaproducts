#!/bin/bash
# Migrate all local SQLite data to Railway PostgreSQL production
set -e

cd /Users/nikollasanches/Documents/hairaproducts
source .venv/bin/activate
export PYTHONPATH=/Users/nikollasanches/Documents/hairaproducts

echo "=== Migrate to Production - $(date) ==="
echo ""

# Show local stats
python3 -c "
import sqlite3
conn = sqlite3.connect('haira.db')
rows = conn.execute('SELECT brand_slug, COUNT(*) FROM products GROUP BY brand_slug ORDER BY COUNT(*) DESC').fetchall()
print(f'Local DB: {sum(r[1] for r in rows)} products across {len(rows)} brands')
for slug, count in rows:
    print(f'  {slug}: {count}')
conn.close()
"

echo ""
echo "Migrating to production..."

export MIGRATION_SECRET="haira-migrate-2026-temp"
export RAILWAY_URL="https://haira-app-production-deb8.up.railway.app"

python3 scripts/migrate_to_railway_api.py

echo ""
echo "=== Migration Complete - $(date) ==="
