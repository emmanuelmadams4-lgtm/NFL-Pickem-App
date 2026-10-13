#!/usr/bin/env bash
# step 15d gate, lane livewire. Uses the lane's own Postgres (container nflpi-lane-live-db, 127.0.0.1:15447),
# never the live app on 5432/8000. Usage: bash gate.sh <label>   (logs land beside this file as <label>-<cmd>.log)
# Take `coord lock res:gate` before running this.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../.." && pwd)"; label="${1:?label}"
db="postgresql+psycopg://nflpi:nflpi@localhost:15447"
export DATABASE_URL="$db/nflpi_test"
fail=0
run() { # name, command...
  local name="$1"; shift
  ( cd "$root" && "$@" ) > "$here/$label-$name.log" 2>&1; local rc=$?
  echo "$([ $rc = 0 ] && echo PASS || echo FAIL) $name exit=$rc :: $(sed 's/\x1b\[[0-9;]*m//g' "$here/$label-$name.log" | grep -E 'passed|failed|error|All checks|Found|drift|No new upgrade|downgrade ok|key text' | tail -1 | cut -c1-160)"
  [ $rc = 0 ] || fail=1
}
# A skipped test is a failure here: nothing in this suite may be skipped.
run pytest bash -c 'cd backend && out=$(uv run pytest -q 2>&1); rc=$?; echo "$out"; if echo "$out" | grep -qi skipped; then echo "error: skipped tests"; exit 1; fi; exit $rc'
run ruff bash -c 'cd backend && uvx ruff check nflpi tests migrations'
# Migrations on a fresh, empty database: up to head, models match, down to nothing, up again, models match.
run alembic bash -c "docker exec nflpi-lane-live-db psql -q -U nflpi -d postgres -c 'drop database if exists nflpi_alembic' -c 'create database nflpi_alembic' \
  && cd backend && export DATABASE_URL=$db/nflpi_alembic \
  && uv run alembic upgrade head && uv run alembic check \
  && uv run alembic downgrade base && echo 'downgrade ok' \
  && uv run alembic upgrade head && uv run alembic check"
run genapi bash -c 'npm run gen:api && git diff --exit-code -- packages/shared/openapi.json packages/shared/src/api-types.ts && echo "no drift"'
# The real Odds API key (read from the main .env, never printed) must be in no tracked or untracked file of this lane.
run keyscan bash -c 'k=$(grep -E "^ODDS_API_KEY=" /Users/emmanueladams/Projects/NFL-Pickem-App/.env | cut -d= -f2- | tr -d "\"'"'"' "); \
  [ -n "$k" ] || { echo "no real key to scan for"; exit 0; }; \
  if git ls-files -z -co --exclude-standard | xargs -0 grep -lF -- "$k" 2>/dev/null | grep -q .; then echo "FAIL key text found in a file"; exit 1; else echo "key text found in no file"; fi'
exit $fail
