#!/usr/bin/env bash
# Step 15 web gate, lane web. Uses the lane's own Postgres (127.0.0.1:15436), never the live app on 5432/8000.
# Usage: gate.sh <label>. Raw logs stay outside the repo (integrator's rule: nothing over 200 KB committed);
# one summary line per command is appended to gate-summary.txt and failing excerpts are saved beside this file.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../.." && pwd)"; label="${1:?label}"
logs="$HOME/.claude/plans/nfl-pickem-lanes/logs/step-15-web"; mkdir -p "$logs"
export DATABASE_URL="postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test"
export E2E_DATABASE_URL="postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_e2e"
fail=0
run() { # name, command...
  local name="$1"; shift; local log="$logs/$label-$name.log"
  ( cd "$root" && "$@" ) > "$log" 2>&1; local rc=$?
  local clean; clean="$(sed 's/\x1b\[[0-9;]*m//g' "$log" | grep -v WebServer)"
  local line="$([ $rc = 0 ] && echo PASS || echo FAIL) $label $name exit=$rc :: $(echo "$clean" | grep -E '[0-9]+ (passed|failed)|error|All checks|Found|no drift' | tail -2 | tr '\n' ' ' | cut -c1-160)"
  echo "$line"; echo "$(git -C "$root" rev-parse --short HEAD) $line" >> "$here/gate-summary.txt"
  if [ $rc != 0 ]; then echo "$clean" | grep -E '✘|FAILED|^ +(Error:|Expected|Received)|error' | cut -c1-240 | head -60 > "$here/$label-$name-failures.txt"; fail=1; fi
}
run pytest bash -c 'cd backend && uv run pytest -q'
run ruff bash -c 'cd backend && uvx ruff check nflpi tests migrations'
run genapi bash -c 'npm run gen:api && git diff --exit-code -- packages/shared/openapi.json packages/shared/src/api-types.ts && echo "no drift"'
run typecheck npm run typecheck
run e2e npm run e2e
exit $fail
