#!/bin/bash
# Mutation sweep for lane passkey on a throwaway copy of HEAD (the worktree is never mutated).
# Holds one backend gate slot for the sweep, renews the lease, always releases. Output: $LOGS/mutation-<sha>.log
set -u
WT=$(cd "$(dirname "$0")/../../../.." && pwd)
SHA=$(git -C "$WT" rev-parse --short HEAD)
LOGS=${PASSKEY_LOGS:-$HOME/.claude/plans/nfl-pickem-lanes/logs/passkey}
COPY=${TMPDIR:-/tmp}/passkey-mut-$SHA
coord() { "$HOME/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord" -C /Users/emmanueladams/Projects/NFL-Pickem-App --session passkey "$@"; }
mkdir -p "$LOGS"
rm -rf "$COPY" && mkdir -p "$COPY" && git -C "$WT" archive HEAD backend .env.example | tar -x -C "$COPY" || exit 2

# One heavy run of this lane at a time: wait for the lane's own gate run to end before asking for a slot.
while pgrep -f "step-10-server-evidence/gate.sh" >/dev/null; do echo "$(date -u +%H:%M:%S) waiting for this lane's gate run"; sleep 30; done
SLOT=""
while [ -z "$SLOT" ]; do
  coord register >/dev/null 2>&1
  for s in res:gate-c res:gate-b; do
    if coord lock "$s" >/dev/null 2>&1; then SLOT=$s; break; fi
  done
  [ -z "$SLOT" ] && { echo "$(date -u +%H:%M:%S) waiting for res:gate-c or res:gate-b"; sleep 30; }
done
echo "$(date -u +%H:%M:%S) holding $SLOT for the mutation sweep at $SHA"
(while sleep 45; do coord heartbeat >/dev/null 2>&1; done) &
BEAT=$!
trap 'kill $BEAT 2>/dev/null; coord unlock "$SLOT" >/dev/null 2>&1; rm -rf "$COPY"; echo "$(date -u +%H:%M:%S) released $SLOT"' EXIT

export DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15444/nflpi_test_passkey_mut
(cd "$COPY/backend" && uv run pytest -q tests/test_passkey.py -p no:cacheprovider 2>&1 | tail -1 | sed 's/^/unmutated: /')
python3 "$WT/docs/gauntlet/logs/step-10-server-evidence/mutation.py" "$COPY/backend" | tee "$LOGS/mutation-$SHA.log" | grep -v "^caught"
echo "MUTATION exit=${PIPESTATUS[0]} log=$LOGS/mutation-$SHA.log"
