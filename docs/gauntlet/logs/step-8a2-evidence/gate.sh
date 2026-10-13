#!/usr/bin/env bash
# Step 8a2 gate, lane web. Uses the lane's own Postgres (container nflpi-lane-pwa-db, 127.0.0.1:15436),
# never the live app on 5432/8000. Usage: gate.sh <label>   (logs land beside this file as <label>-<cmd>.log)
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../.." && pwd)"; label="${1:?label}"
export DATABASE_URL="postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test"
export E2E_DATABASE_URL="postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_e2e"
fail=0
run() { # name, command...
  local name="$1"; shift
  ( cd "$root" && "$@" ) > "$here/$label-$name.log" 2>&1; local rc=$?
  echo "$([ $rc = 0 ] && echo PASS || echo FAIL) $name exit=$rc :: $(grep -E 'passed|failed|error|All checks|Found|drift' "$here/$label-$name.log" | tail -1 | cut -c1-160)"
  [ $rc = 0 ] || fail=1
}
run pytest bash -c 'cd backend && uv run pytest -q'
run ruff bash -c 'cd backend && uvx ruff check nflpi tests migrations'
run genapi bash -c 'npm run gen:api && git diff --exit-code -- packages/shared/openapi.json packages/shared/src/api-types.ts && echo "no drift"'
run typecheck npm run typecheck
run e2e npm run e2e
exit $fail
