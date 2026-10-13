# critic-2, fresh critic, step 15d, HEAD a87424a (code e0da90e)

VERDICT: PASS

Gate rerun on committed HEAD under res:gate (lock released after): pytest 1014 passed (141.59 s), ruff All checks passed, alembic "No new upgrade operations detected" (up/check/down/up/check), genapi "no drift", keyscan "key text found in no file". Logs: critic1-*.log beside gate.sh (untracked).

## Clause check (frozen W1-W9, A1-A8): each has a test that fails when it is broken
W1 eight-hour edge test, post-without-final-probability stays in play. W2 no-game/off-season-week/outside-window tests. W3 30 s gap, 3 h count (300-360), stop when final. W4 Kalshi 5 calls in 600 s and none outside 2 h; Odds 2 calls in 12 h and none beyond 24 h; no key. W5 31-day simulation, restart test, header 49 test. W6 wrapper test, slow-source test, 45 s constants. W7 killed-run test and sweep test (source AND dataset, fresh/ok rows untouched, idempotent). W8 raise isolation, class-only log, real fetch path with DEBUG loggers. W9 run_forever, start daemon, loop starts thread once. A1 no/wrong/right token. A2 one path, GET only, 405 others. A3 mixed-state list, 8 h edge +1 s, past midnight ET, early final late evening, 20-cap and order. A4/A7 field set, 0.0/0.5 passthrough and null, lost game. A5 4:59 vs 5:01 poll age, never heard, row 14:59/15:00/15:01, pregame, final, null newest quote, other sources. A6 None/0/119/120/121 s/3 h, quiet slate, finals alone, lost and final beside live. A8 no writes/no network, no extra fields. No frozen clause lacks a failing-when-broken test.

PLANNING through CLEANUP sections exist in step-15d.md (1 PLANNING, 2 SPECIFICATION, 3 IMPLEMENTATION, 4 CLEANUP, plus 5 VERIFICATION, 6 LANDING). Section 5b is not yet appended (expected until this report lands).

## Findings
1. ADVISORY backend/nflpi/api/live.py:72 A3 says "ordered by kickoff then game id"; the game-id tiebreak is untested (all tests use distinct kickoffs). Breaking the second sort key stays green.
2. ADVISORY backend/nflpi/api/live.py:60 candidates are capped at kickoff <= now + 1 h, so an `in` row for a game kicking off over 1 h ahead (bad data) is never shown; not in a frozen clause.
3. ADVISORY backend/nflpi/live_worker.py:105-119 sources run sequentially (carried as code-review #3); a hung Kalshi run can push the ESPN gap past 120 s and flag stale. Carried.
4. ADVISORY docs/gauntlet/logs/step-15d.md section 5 refers to a section 5b that does not exist yet; append before landing.
5. ADVISORY docs/gauntlet/logs/step-15d-evidence/critic1-*.log: my gate run left five untracked logs; keep or delete at landing.

No BLOCKING findings.
