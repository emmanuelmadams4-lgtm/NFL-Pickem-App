#!/bin/bash
# usage: gate.sh <n>
cd /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-staralerts
export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15438/nflpi_staralerts
OUT=/private/tmp/claude-501/-Users-emmanueladams-Projects-NFL-Pickem-App--claude-worktrees-lane-staralerts/926ad54b-067a-433a-9527-9c079495523b/scratchpad/gate$1
cd backend
docker exec nflpi-lane-stars-db psql -U nflpi -d postgres -c "DROP DATABASE IF EXISTS nflpi_scratch$1" -c "CREATE DATABASE nflpi_scratch$1" -c "DROP DATABASE IF EXISTS nflpi_gate$1" -c "CREATE DATABASE nflpi_gate$1" >/dev/null
DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15438/nflpi_gate$1 uv run pytest -q > $OUT.pytest.log 2>&1; echo "pytest: $(sed 's/\x1b\[[0-9;]*m//g' $OUT.pytest.log | grep -E 'passed|failed' | tail -1)"
uvx ruff check nflpi tests migrations 2>&1 | tail -1
DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15438/nflpi_scratch$1 uv run alembic upgrade head 2>&1 | tail -1
DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15438/nflpi_scratch$1 uv run alembic check 2>&1 | tail -1
cd ..; npm run gen:api >/dev/null 2>&1; echo "gen:api drift: $(git status --porcelain packages | wc -l)"
docker exec nflpi-lane-stars-db psql -U nflpi -d postgres -c "DROP DATABASE nflpi_scratch$1" -c "DROP DATABASE nflpi_gate$1" >/dev/null
