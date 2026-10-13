#!/usr/bin/env bash
# Checks health, token protection, metadata, push setup, and optionally delivery after a deploy.
# Usage: APP_ACCESS_TOKEN=... scripts/smoke.sh <base-url> [--push]
# --push sends a real test alert to subscribed devices.
set -uo pipefail

usage() { echo 'Usage: APP_ACCESS_TOKEN=... scripts/smoke.sh <base-url> [--push]' >&2; exit 2; }
[ $# -ge 1 ] && [ $# -le 2 ] && [ -n "$1" ] && [ -n "${APP_ACCESS_TOKEN:-}" ] || usage
[ $# -eq 1 ] || [ "$2" = --push ] || usage
base="${1%/}"
failed=0

report() {
  if [ "$1" = PASS ]; then
    printf 'PASS %s: %s\n' "$2" "$3"
  else
    printf 'FAIL %s: %s\n' "$2" "$3"
    failed=$((failed + 1))
  fi
}

request() {
  local response
  response=$(curl -sS --max-time 10 -w '\n%{http_code}' "$@" 2>/dev/null) || true
  status="${response##*$'\n'}"
  body="${response%$'\n'*}"
}

request "$base/api/health" -o /dev/null
if [ "$status" = 200 ]; then report PASS health 'HTTP 200'; else report FAIL health "HTTP $status"; fi

request "$base/api/meta" -o /dev/null
if [ "$status" = 401 ]; then report PASS token-required 'HTTP 401'; else report FAIL token-required "HTTP $status"; fi

request -H "Authorization: Bearer $APP_ACCESS_TOKEN" "$base/api/meta"
meta_body="$body"
if [ "$status" = 200 ]; then report PASS token 'HTTP 200'; else report FAIL token "HTTP $status"; fi

meta_detail=$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    season, week = d["current_season"], d["current_week"]
    if not isinstance(season, int) or not isinstance(week, int): raise ValueError()
    model = str(d.get("model_version") or d.get("model_name") or "none")
    model = model.replace(__import__("os").environ["APP_ACCESS_TOKEN"], "[redacted]").replace("\n", " ").replace("\r", " ")
    print(f"season {season} week {week}, model {model}")
except (ValueError, TypeError, KeyError):
    sys.exit(1)
' <<< "$meta_body")
if [ $? -eq 0 ]; then report PASS meta "$meta_detail"; else report FAIL meta 'invalid meta response'; fi

push_detail=$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    count = d["push_subscriptions"]
    if not isinstance(count, int): raise ValueError()
    if d["push_public_key"] is None: print("NO_KEYS")
    else: print(f"{count} devices subscribed")
except (ValueError, TypeError, KeyError):
    sys.exit(1)
' <<< "$meta_body")
if [ $? -ne 0 ]; then
  report FAIL push-configured 'invalid meta response'
elif [ "$push_detail" = NO_KEYS ]; then
  report FAIL push-configured 'no VAPID keys on the server'
else
  report PASS push-configured "$push_detail"
fi

if [ "${2:-}" = --push ]; then
  request -X POST -H "Authorization: Bearer $APP_ACCESS_TOKEN" "$base/api/push/test"
  test_detail=$(python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
    delivered, devices = d["delivered"], d["devices"]
    if not isinstance(delivered, int) or not isinstance(devices, int): raise ValueError()
    detail = f"delivered {delivered} of {devices}"
    if delivered >= 1 and delivered == devices:
        print("PASS|" + detail)
    else:
        for result in d.get("results", []):
            if not result.get("ok"):
                host = str(result.get("host") or "unknown")
                error = str(result.get("error") or "not delivered")
                detail += f"; {host}: {error}"
        detail = detail.replace(os.environ["APP_ACCESS_TOKEN"], "[redacted]").replace("\n", " ").replace("\r", " ")
        print("FAIL|" + detail)
except (ValueError, TypeError, KeyError, AttributeError):
    sys.exit(1)
' <<< "$body")
  test_parse_rc=$?
  if [ "$status" != 200 ] || [ "$test_parse_rc" -ne 0 ]; then
    report FAIL test-alert "HTTP $status or invalid response"
  elif [ "${test_detail%%|*}" = PASS ]; then
    report PASS test-alert "${test_detail#*|}"
  else
    report FAIL test-alert "${test_detail#*|}"
  fi
fi

if [ "$failed" -eq 0 ]; then
  echo 'smoke: PASS'
  exit 0
fi
echo "smoke: FAIL ($failed failed)"
exit 1
