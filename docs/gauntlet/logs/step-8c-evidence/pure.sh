#!/usr/bin/env bash
# The tests that need no database: conftest is skipped, so every test that asks for the `session` fixture errors with
# "fixture 'session' not found" (those are run later by the coordinator, who can reach the lane database).
# PASS = no failure, no collection error, and every error is exactly that one.
set -uo pipefail
cd "$(dirname "$0")/../../../../backend"
out=$(COLUMNS=300 .venv/bin/python -m pytest --noconftest -q --color=no -p no:cacheprovider tests/test_news.py 2>&1)
echo "$out" | tail -n 4
if echo "$out" | grep -qE "ImportError|ModuleNotFoundError|errors? during collection"; then echo "FAIL: collection error"; exit 1; fi
if echo "$out" | grep -qE "[0-9]+ failed"; then echo "FAIL: tests failed"; echo "$out" | grep -E "^FAILED" | head -20; exit 1; fi
errs=$(echo "$out" | grep -c '^ERROR ')
nofix=$(echo "$out" | grep -c "fixture 'session' not found")
[ "$errs" = "$nofix" ] || { echo "FAIL: $errs errors but only $nofix are the missing session fixture"; exit 1; }
echo "PURE OK"
