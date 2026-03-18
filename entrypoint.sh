#!/bin/sh
echo "=== HAIRA v2 Starting ==="
echo "Working directory: $(pwd)"
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"
echo "CENTRAL_DATABASE_URL set: $([ -n "$CENTRAL_DATABASE_URL" ] && echo 'yes' || echo 'NO')"

if [ -n "$CENTRAL_DATABASE_URL" ]; then
    echo "Running central DB migrations..."
    python -m alembic -c alembic_central.ini upgrade head 2>&1 || echo "WARNING: central migrations failed"
    echo "Running brand DB migrations..."
    python scripts/migrate_all_brands.py 2>&1 || echo "WARNING: some brand migrations failed"
else
    echo "Single-DB mode: running standard migrations..."
    python -m alembic upgrade head 2>&1 || echo "WARNING: migrations failed"
fi

echo "Seeding admin user..."
python scripts/seed_admin.py 2>&1 || echo "WARNING: admin seed failed (may already exist)"

echo "Starting server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 2
