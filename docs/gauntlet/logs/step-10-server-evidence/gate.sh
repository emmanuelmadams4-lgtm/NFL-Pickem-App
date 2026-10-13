#!/bin/bash
# Lane passkey gate. Usage: gate.sh <log-label> [full|pytest-only]
# A second runner (the critic) sets COORD_SESSION and PASSKEY_DB so two runs never share a slot or a database.
# Waits for a free backend gate slot (res:gate-b or res:gate-c), holds it for this ONE run, renews the lease every
# 45 s, and always releases it. Full pytest output goes to $LOGS (outside the repo); the summary to stdout.
set -u
LABEL=${1:?label}
MODE=${2:-full}
WT=$(cd "$(dirname "$0")/../../../.." && pwd)
LOGS=${PASSKEY_LOGS:-$HOME/.claude/plans/nfl-pickem-lanes/logs/passkey}
PG=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15444
coord() { "$HOME/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord" -C /Users/emmanueladams/Projects/NFL-Pickem-App --session "${COORD_SESSION:-passkey}" "$@"; }
mkdir -p "$LOGS"
LOG="$LOGS/$LABEL.log"
: >"$LOG"

SLOT=""
while [ -z "$SLOT" ]; do
  coord register >/dev/null 2>&1
  for s in res:gate-b res:gate-c; do
    if coord lock "$s" >/dev/null 2>&1; then SLOT=$s; break; fi
  done
  [ -z "$SLOT" ] && { echo "$(date -u +%H:%M:%S) waiting for res:gate-b or res:gate-c"; sleep 30; }
done
echo "$(date -u +%H:%M:%S) holding $SLOT for $LABEL at $(git -C "$WT" rev-parse --short HEAD)"
(while sleep 45; do coord heartbeat >/dev/null 2>&1; done) &
BEAT=$!
trap 'kill $BEAT 2>/dev/null; coord unlock "$SLOT" >/dev/null 2>&1; echo "$(date -u +%H:%M:%S) released $SLOT"' EXIT

cd "$WT/backend" || exit 2
rc=0
DATABASE_URL=$PG/${PASSKEY_DB:-nflpi_test} uv run pytest -q ${PYTEST_ARGS:-} >>"$LOG" 2>&1 || rc=1
echo "pytest: $(grep -E '(passed|failed|error)' "$LOG" | tail -1) exit=$rc"
if [ "$MODE" = full ]; then
  uvx ruff check nflpi tests migrations >>"$LOG" 2>&1 && echo "ruff: clean" || { rc=1; echo "ruff: FAIL"; }
  SCRATCH=nflpi_passkey_alembic_$$
  psql() { docker exec nflpi-lane-sdk-db psql -U nflpi -d postgres -qAt -c "$1"; }
  psql "create database $SCRATCH" >>"$LOG" 2>&1
  {
    export DATABASE_URL=$PG/$SCRATCH
    uv run alembic upgrade head && uv run alembic check && uv run alembic downgrade -1 && uv run alembic upgrade head
  } >>"$LOG" 2>&1 && echo "alembic: up, check, down one, up: clean" || { rc=1; echo "alembic: FAIL"; }
  psql "drop database $SCRATCH" >>"$LOG" 2>&1
  (cd "$WT" && npm run gen:api >>"$LOG" 2>&1 && git diff --quiet -- packages/shared) && echo "gen:api: no drift" || { rc=1; echo "gen:api: DRIFT or FAIL"; }
fi
echo "GATE $LABEL exit=$rc log=$LOG"
exit $rc
