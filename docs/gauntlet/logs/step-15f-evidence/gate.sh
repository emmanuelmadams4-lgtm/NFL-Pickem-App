#!/bin/bash
# usage: gate.sh <label>   (run from the worktree root; caller holds coord lock res:gate-b)
set -u
L=$1; E=docs/gauntlet/logs/step-15f-evidence
export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15447/nflpi_test
cd backend
uv run pytest -q > ../$E/$L-pytest.log 2>&1; echo "pytest exit $?" > ../$E/$L-summary.txt; grep -E "passed|failed" ../$E/$L-pytest.log | tail -1 >> ../$E/$L-summary.txt
uvx ruff check nflpi tests migrations >> ../$E/$L-summary.txt 2>&1; echo "ruff exit $?" >> ../$E/$L-summary.txt
uv run alembic check >> ../$E/$L-summary.txt 2>&1; echo "alembic check exit $?" >> ../$E/$L-summary.txt
cd .. && npm run gen:api > $E/$L-genapi.log 2>&1; echo "genapi exit $?" >> $E/$L-summary.txt
git status --short packages/shared >> $E/$L-summary.txt; echo "drift check done" >> $E/$L-summary.txt
