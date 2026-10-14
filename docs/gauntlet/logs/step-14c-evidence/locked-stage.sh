#!/usr/bin/env bash
# Usage: locked-stage.sh <stage>. Waits for res:gate-b or res:gate-c (prints every 20 s), runs one bench stage, releases.
C=/Users/emmanueladams/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord
R=/Users/emmanueladams/Projects/NFL-Pickem-App
here="$(cd "$(dirname "$0")" && pwd)"; stage="${1:?stage}"
export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15448/nflpi_test
got=""
while [ -z "$got" ]; do
  $C -C $R --session modelc register >/dev/null 2>&1
  for l in res:gate-b res:gate-c; do
    if $C -C $R --session modelc lock $l 2>&1 | grep -qv rejected; then got=$l; break; fi
  done
  [ -z "$got" ] && { echo "$(date +%H:%M:%S) waiting for a gate lock (b: s217, c: s189) before stage $stage"; sleep 20; }
done
echo "$(date +%H:%M:%S) holding $got; running stage $stage"
( cd "$here/../../../../backend" && uv run python "$here/run.py" "$stage" > "$here/run-$stage.json" 2> "$here/run-$stage.err" ); rc=$?
$C -C $R --session modelc unlock $got >/dev/null 2>&1
echo "$(date +%H:%M:%S) released $got; stage $stage exit=$rc"; tail -3 "$here/run-$stage.err"
