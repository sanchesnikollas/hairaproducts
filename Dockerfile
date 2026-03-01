FROM python:3.12-slim AS base

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Build frontend
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Copy all source
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini ./
COPY entrypoint.sh ./

# Install Python package (editable so src imports work from /app)
RUN pip install --no-cache-dir -e .

# Expose port (Railway sets PORT env var)
EXPOSE ${PORT:-8000}

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
