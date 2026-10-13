#!/usr/bin/env bash
# The tests that need no database: conftest is skipped, so every test that asks for the `session` fixture errors with
# "fixture 'session' not found" (those are checked later by the coordinator, who can reach the lane database).
# PASS = no failure, no collection error, and every error is exactly that one.
set -uo pipefail
cd "$(dirname "$0")/../../../../backend"
out=$(.venv/bin/python -m pytest --noconftest -q -p no:cacheprovider -rfE tests/test_news.py 2>&1); rc=$?
echo "$out" | tail -n 12
echo "$out" | grep -q "^ERROR collecting\|ImportError\|ModuleNotFoundError" && { echo "FAIL: collection error"; exit 1; }
bad=$(echo "$out" | grep -E '^(FAILED|ERROR) ' | grep -v "fixture 'session' not found")
[ -z "$bad" ] || { echo "FAIL: $bad" | head -20; exit 1; }
echo "$out" | grep -E '[0-9]+ (passed|error)' | tail -1
echo "PURE OK"
