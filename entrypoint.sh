#!/bin/sh
set -e

echo "=== HAIRA v2 Starting ==="
echo "Working directory: $(pwd)"
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"

echo "Running migrations..."
python -m alembic upgrade head
echo "Migrations complete."

echo "Cleaning non-amend data..."
python -c "
from src.storage.orm_models import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.begin() as conn:
    for table in ['products', 'product_evidence', 'quarantine_details']:
        r = conn.execute(text(f\"DELETE FROM {table} WHERE brand_slug <> 'amend'\"))
        print(f'  {table}: removed {r.rowcount} rows')
    r = conn.execute(text(\"DELETE FROM brand_coverage WHERE brand_slug <> 'amend'\"))
    print(f'  brand_coverage: removed {r.rowcount} rows')
"
echo "Cleanup complete."

echo "Starting server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 2
