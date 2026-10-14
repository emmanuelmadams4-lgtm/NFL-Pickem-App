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
  [ -z "$got" ] && { echo "$(date +%H:%M:%S) waiting for a gate lock (b: s217, c: s189) before mutation sweep"; sleep 20; }
done
echo "$(date +%H:%M:%S) holding $got; running mutation sweep"
( cd "$here/../../../../backend" && uv run python "$here/mutate.py" > "$here/mutate.log" 2> "$here/mutate.err" ); rc=$?
$C -C $R --session modelc unlock $got >/dev/null 2>&1
echo "$(date +%H:%M:%S) released $got; mutation sweep exit=$rc"; tail -1 "$here/mutate.log"
