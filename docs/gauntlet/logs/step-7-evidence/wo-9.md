# CODEX WORK ORDER 9 — step 7, lane alerts: the address check can be bypassed with a backslash (security delta)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: the 6 red tests in `backend/tests/test_alerts.py` (list in `red-wo9.log`) go green with no test change; every other test stays green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

ALLOWED SCOPE: `backend/nflpi/api/schemas.py` (`PushSubscriptionIn.valid_push_service` and its constant), `backend/nflpi/notify/push.py` (`alert_prediction_changes`, `alert_injuries`). Nothing else.

THE DEFECT (security reviewer, shown with the lane's own libraries): for `https://evil.com\.push.apple.com/x`, `urlsplit` (the check) sees the host `evil.com\.push.apple.com`, which ends in `.push.apple.com` and is accepted; `urllib3` (the sender) connects to `evil.com`. The two parsers disagree about a backslash.

REQUIRED BEHAVIOUR
1. Before `urlsplit`, refuse the whole address unless it has a strict form: `https://`, then a host of lower-case letters, digits, dots and hyphens only, then nothing or a `/` followed by printable ASCII without backslash and without space. Use `re.fullmatch` (not `match`: a trailing newline must be refused), for example `https://[a-z0-9.-]+(/[!-\[\]-~]*)?`. Keep every existing check after it. One named constant for the pattern.
2. When an alert reached no device, `alert_prediction_changes` and `alert_injuries` log one warning: `alert <key> reached 0 devices` (the dedupe key, nothing else). It is not recorded and not retried, as now.

PROOF (the coordinator reruns it; you cannot reach the test database, so say so): `cd backend && uvx ruff check nflpi tests migrations`.

CONSTRAINTS: smallest diff (Ponytail); no new dependency; no test edits; never log an endpoint or a key; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the changed lines, the proof command with its exit code, any blocker.
