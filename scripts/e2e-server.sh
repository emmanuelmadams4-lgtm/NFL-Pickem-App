#!/usr/bin/env bash
# Seeds a throwaway database and serves the production web export (apps/web/out) on :8123 for Playwright.
set -euo pipefail
cd "$(dirname "$0")/../backend"
export DATABASE_URL="${E2E_DATABASE_URL:-postgresql+psycopg://nflpi:nflpi@localhost:5432/nflpi_e2e}"
uv run python -m tests.e2e_seed
export APP_ACCESS_TOKEN=e2e-token ANTHROPIC_API_KEY= OPENROUTER_API_KEY= VAPID_PUBLIC_KEY= VAPID_PRIVATE_KEY=
exec uv run uvicorn nflpi.api.main:app --host 127.0.0.1 --port 8123
