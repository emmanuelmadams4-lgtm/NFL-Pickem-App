#!/usr/bin/env bash
# Usage: locked-gate.sh <label>. Waits for res:gate-b or res:gate-c, runs gate.sh once, releases.
C=/Users/emmanueladams/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord
R=/Users/emmanueladams/Projects/NFL-Pickem-App
here="$(cd "$(dirname "$0")" && pwd)"; label="${1:?label}"
got=""
while [ -z "$got" ]; do
  $C -C $R --session modelc register >/dev/null 2>&1
  for l in res:gate-b res:gate-c; do
    if $C -C $R --session modelc lock $l 2>&1 | grep -qv rejected; then got=$l; break; fi
  done
  [ -z "$got" ] && { echo "$(date +%H:%M:%S) waiting for a gate lock"; sleep 20; }
done
echo "$(date +%H:%M:%S) holding $got; running gate $label"
bash "$here/gate.sh" "$label"; rc=$?
$C -C $R --session modelc unlock $got >/dev/null 2>&1
echo "$(date +%H:%M:%S) released $got; gate $label exit=$rc"
