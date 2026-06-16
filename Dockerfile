# Stage 1: Build frontend with Node
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.12-slim

WORKDIR /app

# Copy frontend build from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy all source
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini ./
COPY alembic_central.ini ./
COPY scripts/ ./scripts/
COPY entrypoint.sh ./
# Knowledge base canônico da Moon
COPY iamoon/ ./iamoon/

# Install Python package
RUN pip install --no-cache-dir -e .

# Chromium + system deps para o scraper (HAIRA-159). Sem isso, Playwright
# falha tanto no CLI (haira scrape) quanto em qualquer ferramenta que use
# browser. ~300 MB adicionais na imagem, mas é o necessário pra DOM crawls.
RUN playwright install --with-deps chromium

# Expose port (Railway sets PORT env var)
EXPOSE ${PORT:-8000}

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
