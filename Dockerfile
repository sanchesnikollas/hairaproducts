FROM python:3.12-slim AS base

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Build frontend
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Copy backend source
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini ./

# Expose port (Railway sets PORT env var)
EXPOSE ${PORT:-8000}

# Start: run migrations then launch server
CMD alembic upgrade head && \
    uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 2
