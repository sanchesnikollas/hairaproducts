#!/bin/sh
set -e

echo "=== HAIRA v2 Starting ==="
echo "Working directory: $(pwd)"
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"

echo "Running migrations..."
python -m alembic upgrade head
echo "Migrations complete."

echo "Starting server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 2
