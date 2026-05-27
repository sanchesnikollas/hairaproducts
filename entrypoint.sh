#!/bin/sh
echo "=== HAIRA v2 Starting (build 20260320) ==="
echo "Working directory: $(pwd)"
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"
echo "CENTRAL_DATABASE_URL set: $([ -n "$CENTRAL_DATABASE_URL" ] && echo 'yes' || echo 'NO')"

# Ensure src package is importable
export PYTHONPATH="/app:${PYTHONPATH}"

# Fail-fast on DB hangs: bound connection + lock waits so a stuck migration
# surfaces a real error in the logs instead of silently blocking healthcheck.
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-15}"
export PGOPTIONS="${PGOPTIONS:- -c lock_timeout=15s -c statement_timeout=120s}"

echo "DB connectivity pre-check..."
python - <<'PYCHK' 2>&1 || echo "DB PRE-CHECK FAILED (see error above)"
import os
url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgres"):
    import psycopg2
    u = url.replace("postgres://", "postgresql://", 1)
    psycopg2.connect(u, connect_timeout=15).close()
    print("DB connect OK")
else:
    print("Non-Postgres DATABASE_URL, skipping pre-check")
PYCHK

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

echo "Seeding reviewer users..."
python scripts/seed_reviewers.py 2>&1 || echo "WARNING: reviewer seed failed"

echo "Starting server..."
exec uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 2
