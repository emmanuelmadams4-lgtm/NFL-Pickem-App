#!/usr/bin/env bash
# step 8c gate, lane news. Uses the lane's own Postgres (container nflpi-lane-news-db, 127.0.0.1:15441),
# never the live app on 5432/8000. Usage: bash gate.sh <label>   (logs land beside this file as <label>-<cmd>.log)
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../.." && pwd)"; label="${1:?label}"
db="postgresql+psycopg://nflpi:nflpi@localhost:15441"
export DATABASE_URL="$db/nflpi_test"
fail=0
run() { # name, command...
  local name="$1"; shift
  ( cd "$root" && "$@" ) > "$here/$label-$name.log" 2>&1; local rc=$?
  echo "$([ $rc = 0 ] && echo PASS || echo FAIL) $name exit=$rc :: $(grep -E 'passed|failed|error|All checks|Found|drift|No new upgrade|downgrade ok' "$here/$label-$name.log" | tail -1 | cut -c1-160)"
  [ $rc = 0 ] || fail=1
}
# A skipped test is a failure here: nothing in this suite may be skipped.
run pytest bash -c 'cd backend && out=$(uv run pytest -q 2>&1); rc=$?; echo "$out"; if echo "$out" | grep -qi skipped; then echo "error: skipped tests"; exit 1; fi; exit $rc'
run ruff bash -c 'cd backend && uvx ruff check nflpi tests migrations'
# Migrations on a fresh, empty database: up to head, models match, down to nothing, up again, models match.
run alembic bash -c "docker exec nflpi-lane-news-db psql -q -U nflpi -d postgres -c 'drop database if exists nflpi_alembic' -c 'create database nflpi_alembic' \
  && cd backend && export DATABASE_URL=$db/nflpi_alembic \
  && uv run alembic upgrade head && uv run alembic check \
  && uv run alembic downgrade base && echo 'downgrade ok' \
  && uv run alembic upgrade head && uv run alembic check"
run genapi bash -c 'npm run gen:api && git diff --exit-code -- packages/shared/openapi.json packages/shared/src/api-types.ts && echo "no drift"'
exit $fail
