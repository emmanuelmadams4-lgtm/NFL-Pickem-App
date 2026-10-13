#!/usr/bin/env bash
# usage: gate.sh <label>   (run from the repo root; caller holds coord lock res:gate-b, this renews it)
set -u
L=$1; D=docs/gauntlet/logs/step-8g-server-evidence
C=/Users/emmanueladams/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord
export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15441/nflpi_test
( while true; do sleep 45; $C -C . --session newswire register >/dev/null 2>&1; $C -C . --session newswire lock res:gate-b >/dev/null 2>&1; done ) & KEEP=$!
trap 'kill $KEEP 2>/dev/null' EXIT
S=$D/$L-summary.txt; : > $S
echo "load: $(uptime)" >> $S
( cd backend && uv run pytest -q --color=no > ../$D/$L-pytest.log 2>&1 ); echo "pytest exit=$? :: $(grep -E 'passed|failed' $D/$L-pytest.log | tail -1)" >> $S
( cd backend && uvx ruff check nflpi tests migrations > ../$D/$L-ruff.log 2>&1 ); echo "ruff exit=$? :: $(tail -1 $D/$L-ruff.log)" >> $S
docker exec nflpi-lane-news-db psql -U nflpi -d postgres -qc "drop database if exists nflpi_alembic_8g" -c "create database nflpi_alembic_8g" > /dev/null 2>&1
( cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15441/nflpi_alembic_8g bash -c 'uv run alembic upgrade head && uv run alembic check' > ../$D/$L-alembic.log 2>&1 ); echo "alembic (fresh db: upgrade head, check) exit=$? :: $(tail -1 $D/$L-alembic.log)" >> $S
docker exec nflpi-lane-news-db psql -U nflpi -d postgres -qc "drop database if exists nflpi_alembic_8g" > /dev/null 2>&1
npm run gen:api > $D/$L-genapi.log 2>&1; echo "genapi exit=$?" >> $S
git status --short packages/shared > $D/$L-genapi-status.txt; echo "genapi drift lines: $(wc -l < $D/$L-genapi-status.txt)" >> $S
echo "GATE-DONE $L" >> $S
