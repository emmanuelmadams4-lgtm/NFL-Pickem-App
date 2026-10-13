#!/usr/bin/env bash
# Proof for criterion O1: runs scripts/smoke.sh against the lane test server (127.0.0.1:8123, lane database on
# 15436) and checks its lines and exit codes. Never the live app. Usage: bash smoke-proof.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../../../.." && pwd)"
base="http://127.0.0.1:8123"; smoke="$root/scripts/smoke.sh"; bad=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; bad=1; fi; }

export E2E_DATABASE_URL="postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_e2e"
bash "$root/scripts/e2e-server.sh" > "$here/smoke-server.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null; wait $server 2>/dev/null' EXIT
for _ in $(seq 60); do curl -fsS --max-time 2 "$base/api/health" >/dev/null 2>&1 && break; sleep 2; done

out="$(APP_ACCESS_TOKEN=e2e-token bash "$smoke" "$base" 2>&1)"; rc=$?
echo "$out"
check "good token: exit 0" "[ $rc = 0 ]"
for name in health token-required token meta push-configured; do check "PASS $name" "grep -q '^PASS $name: ' <<< \"\$out\""; done
check "no test alert without --push" "! grep -q 'test-alert' <<< \"\$out\""
check "last line smoke: PASS" "[ \"\$(tail -1 <<< \"\$out\")\" = 'smoke: PASS' ]"
check "token never printed" "! grep -q 'e2e-token' <<< \"\$out\""

out="$(APP_ACCESS_TOKEN=wrong-token-123 bash "$smoke" "$base" 2>&1)"; rc=$?
echo "$out"
check "wrong token: exit 1" "[ $rc = 1 ]"
check "wrong token: FAIL token" "grep -q '^FAIL token: ' <<< \"\$out\""
check "wrong token: health still checked" "grep -q '^PASS health: ' <<< \"\$out\""
check "wrong token: last line smoke: FAIL" "grep -q '^smoke: FAIL (' <<< \"\$(tail -1 <<< \"\$out\")\""
check "wrong token never printed" "! grep -q 'wrong-token-123' <<< \"\$out\""

# --push with no device subscribed: the test alert check runs and fails (delivered 0 of 0).
out="$(APP_ACCESS_TOKEN=e2e-token bash "$smoke" "$base" --push 2>&1)"; rc=$?
echo "$out"
check "--push with no device: exit 1" "[ $rc = 1 ]"
check "--push with no device: FAIL test-alert" "grep -q '^FAIL test-alert: ' <<< \"\$out\""

APP_ACCESS_TOKEN=e2e-token bash "$smoke" >/dev/null 2>&1; check "no base URL: exit 2" "[ $? = 2 ]"
env -u APP_ACCESS_TOKEN bash "$smoke" "$base" >/dev/null 2>&1; check "no token: exit 2" "[ $? = 2 ]"

[ $bad = 0 ] && echo "smoke-proof: PASS" || echo "smoke-proof: FAIL"
exit $bad
