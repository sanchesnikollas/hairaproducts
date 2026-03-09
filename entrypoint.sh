#!/bin/sh

echo "=== HAIRA v2 Starting ==="
echo "Working directory: $(pwd)"
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"

echo "Running migrations..."
python -m alembic upgrade head 2>&1 || echo "WARNING: migrations failed, continuing..."
echo "Migrations step done."

echo "Starting server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 2
