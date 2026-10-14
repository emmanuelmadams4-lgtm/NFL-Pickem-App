#!/usr/bin/env bash
# Usage: locked-stage.sh <stage>. Waits for res:gate-b or res:gate-c (prints every 20 s), runs one bench stage, releases.
C=/Users/emmanueladams/.claude/local-mods/coord/bin/coord
S=6a8452f5-91cf-48f9-8f1f-a95b22031000
here="$(cd "$(dirname "$0")" && pwd)"; stage="${1:?stage}"
export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15442/nflpi_bench18g
got=""
while [ -z "$got" ]; do
  for l in res:gate-b res:gate-c; do
    if $C --session $S lock $l 2>&1 | grep -q '"locked"'; then got=$l; break; fi
  done
  [ -z "$got" ] && { echo "$(date +%H:%M:%S) waiting for a gate lock before stage $stage"; sleep 20; }
done
echo "$(date +%H:%M:%S) holding $got; running stage $stage"
( cd "$here/../../../../backend" && uv run python "$here/run.py" "$stage" > "$here/run-$stage.json" 2> "$here/run-$stage.err" ); rc=$?
$C --session $S unlock $got >/dev/null 2>&1
echo "$(date +%H:%M:%S) released $got; stage $stage exit=$rc"; tail -3 "$here/run-$stage.err" | cut -c1-300
