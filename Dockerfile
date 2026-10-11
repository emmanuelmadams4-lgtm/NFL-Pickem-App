# 1) Build the web app into static files
FROM node:22-slim AS web
WORKDIR /src
COPY package.json package-lock.json ./
COPY packages/shared/package.json packages/shared/
COPY apps/web/package.json apps/web/
COPY apps/mobile/package.json apps/mobile/
RUN npm ci --workspace apps/web --include-workspace-root --no-audit --no-fund
COPY packages/shared packages/shared
COPY apps/web apps/web
RUN npm run build -w apps/web

# 2) Python API that also serves the web files
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /src/apps/web/out /app/web
ENV WEB_DIST_DIR=/app/web PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn nflpi.api.main:app --host 0.0.0.0 --port 8000"]
