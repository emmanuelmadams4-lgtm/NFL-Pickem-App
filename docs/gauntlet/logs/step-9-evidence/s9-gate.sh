#!/bin/bash
# Step 9 gate, one run. Usage: s9-gate.sh <label>   (run from the worktree root)
# Waits for the shared machine lock res:gate, runs the gate on the lane's own test database, releases the lock.
# PYTEST_ARGS adds pytest arguments (the baseline run ignores the not-yet-built test file).
# Logs: docs/gauntlet/logs/step-9-evidence/s9-<label>-*.log. Never uses the default DATABASE_URL (the live port 5432).
set -u
label=${1:?label}
root=$(git rev-parse --show-toplevel)
ev="$root/docs/gauntlet/logs/step-9-evidence"
db=postgresql+psycopg://nflpi:test@127.0.0.1:15446
coord() { /Users/emmanueladams/.claude/local-mods/coord/bin/coord --session "${COORD_SESSION:-ea852c4e-b120-43df-a80c-3880743839cb}" "$@"; }

until coord lock res:gate 2>&1 | grep -q '"locked": \["res:gate"\]'; do sleep 20; done
trap 'coord unlock res:gate >/dev/null 2>&1' EXIT
trap 'exit 143' TERM INT

fail=0
step() { # name, command...
  local name=$1; shift
  "$@" > "$ev/s9-$label-$name.log" 2>&1
  local rc=$?
  [ $rc -eq 0 ] || fail=1
  echo "$([ $rc -eq 0 ] && echo PASS || echo FAIL) $name exit=$rc :: $(grep -v '^$' "$ev/s9-$label-$name.log" | tail -1)"
}

echo "HEAD $(git rev-parse --short HEAD) $(date -u +%FT%TZ) label=$label"
cd "$root/backend" || exit 2
DATABASE_URL=$db/nflpi_test step pytest uv run pytest -q ${PYTEST_ARGS:-}
step ruff uvx ruff check nflpi tests migrations
DATABASE_URL=$db/nflpi step alembic-upgrade uv run alembic upgrade head
DATABASE_URL=$db/nflpi step alembic-check uv run alembic check
cd "$root" || exit 2
DATABASE_URL=$db/nflpi_test step genapi npm run gen:api
step genapi-drift git diff --exit-code -- packages/shared
echo "GATE $([ $fail -eq 0 ] && echo PASS || echo FAIL) label=$label"
exit $fail
