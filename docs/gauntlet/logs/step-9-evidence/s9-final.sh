#!/bin/bash
# Step 9 final evidence, one job: mutation pass, then the gate twice. Run from the worktree root.
# Takes the shared machine lock res:gate for the mutation pass; s9-gate.sh takes it again for each gate run.
set -u
root=$(git rev-parse --show-toplevel)
ev="$root/docs/gauntlet/logs/step-9-evidence"
coord() { /Users/emmanueladams/.claude/local-mods/coord/bin/coord --session "${COORD_SESSION:-ea852c4e-b120-43df-a80c-3880743839cb}" "$@"; }
until coord lock res:gate 2>&1 | grep -q '"locked": \["res:gate"\]'; do sleep 20; done
(cd "$root/backend" && DATABASE_URL=postgresql+psycopg://nflpi:test@127.0.0.1:15446/nflpi_wo uv run python "$ev/s9-mutate.py") > "$ev/s9-mutate.log" 2>&1
echo "MUTATION exit=$? :: $(tail -1 "$ev/s9-mutate.log")"
coord unlock res:gate >/dev/null 2>&1
git -C "$root" status --short -- backend
"$ev/s9-gate.sh" "${1:-final}1" | tee "$ev/s9-${1:-final}1-gate.log"
"$ev/s9-gate.sh" "${1:-final}2" | tee "$ev/s9-${1:-final}2-gate.log"
