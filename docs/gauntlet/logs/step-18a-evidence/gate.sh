#!/usr/bin/env bash
# Step 18a gate, lane audit (same shape as step 14's). Uses the lane's own Postgres (container nflpi-lane-model-db,
# 127.0.0.1:15442), never the live app on 5432/8000. Usage: bash gate.sh <label>
# Raw logs go outside the repository: ~/.claude/plans/nfl-pickem-lanes/logs/step-18a-<label>-<cmd>.log
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../.." && pwd)"; label="${1:?label}"
logs="$HOME/.claude/plans/nfl-pickem-lanes/logs"
db="postgresql+psycopg://nflpi:nflpi@127.0.0.1:15442"
export DATABASE_URL="$db/nflpi_test"
fail=0
run() { # name, command...
  local name="$1"; shift
  ( cd "$root" && "$@" ) > "$logs/step-18a-$label-$name.log" 2>&1; local rc=$?
  echo "$([ $rc = 0 ] && echo PASS || echo FAIL) $name exit=$rc :: $(grep -E 'passed|failed|error|All checks|Found|drift|No new upgrade' "$logs/step-18a-$label-$name.log" | tail -1 | cut -c1-160)"
  [ $rc = 0 ] || fail=1
}
echo "HEAD $(git -C "$root" rev-parse --short HEAD) label $label $(date -u +%Y-%m-%dT%H:%M:%SZ)"
# A skipped test is a failure here: nothing in this suite may be skipped.
run pytest bash -c 'cd backend && out=$(uv run pytest -q --color=no 2>&1); rc=$?; echo "$out"; if echo "$out" | grep -qi skipped; then echo "error: skipped tests"; exit 1; fi; exit $rc'
run ruff bash -c 'cd backend && uvx ruff check nflpi tests migrations ../docs/gauntlet/logs/step-18a-evidence'
run alembic bash -c "docker exec nflpi-lane-model-db psql -q -U nflpi -d postgres -c 'drop database if exists nflpi_alembic' -c 'create database nflpi_alembic' \
  && cd backend && export DATABASE_URL=$db/nflpi_alembic && uv run alembic upgrade head && uv run alembic check"
run genapi bash -c 'npm run gen:api && git diff --exit-code -- packages/shared/openapi.json packages/shared/src/api-types.ts && echo "no drift"'
exit $fail
