# CODEX WORK ORDER 4 — step 7, lane alerts: `scripts/smoke.sh` (criterion O1)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: a short script the owner runs after a deploy to see, check by check, that the app is up. `docs/gauntlet/logs/step-7-evidence/smoke-proof.sh` (the coordinator runs it against the lane test server) must print `smoke-proof: PASS`.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

ALLOWED SCOPE: `scripts/smoke.sh` (new). Nothing else.

REQUIREMENT

Usage: `APP_ACCESS_TOKEN=... scripts/smoke.sh <base-url> [--push]`. Bash, `curl` only (plus `python3` to read JSON, as `scripts/deploy-check.sh` does). `set -uo pipefail`; every `curl` has `--max-time 10`.

Checks, in this order. Each prints exactly one line, `PASS <name>: <detail>` or `FAIL <name>: <detail>`, and a failed check does not stop the later ones:
1. `health`: `GET <base>/api/health` answers 200.
2. `token-required`: `GET <base>/api/meta` with no token answers 401.
3. `token`: `GET <base>/api/meta` with the token answers 200.
4. `meta`: that reply has `current_season` and `current_week`; detail = `season S week W, model <model_version or none>`.
5. `push-configured`: `push_public_key` is not null; detail says how many devices are subscribed. When it is null: `FAIL push-configured: no VAPID keys on the server`.
6. Only with `--push`: `test-alert`: `POST <base>/api/push/test` with the token; PASS when `delivered` is at least 1 and equals `devices`; detail = `delivered D of N`; on a FAIL add each failed result as `<host>: <error>`. Without `--push` this check is not run and no line is printed for it, because it sends a real alert to the phone.

Last line: `smoke: PASS` and exit 0 when every check that ran passed; otherwise `smoke: FAIL (<n> failed)` and exit 1.
Missing base URL or missing `APP_ACCESS_TOKEN`: a usage line on stderr and exit 2, before any request.

The token is read from the environment only, sent only in the `Authorization` header, and never printed, also not on an error (no `curl -v`, no `set -x`). Header comment in the script: what it checks, the usage line, and that `--push` sends a real alert.

PROOF (the coordinator reruns it): `bash -n scripts/smoke.sh`. You cannot bind ports, so say so; the coordinator runs `smoke-proof.sh`.

CONSTRAINTS: smallest script that does this; no new dependency; match the style of `scripts/deploy-check.sh`. Never run it against ports 8000 or 5432 or any `nfl-pickem-app-*` container: that is the live app. Do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the file, a three-line summary, the proof command with its exit code, any blocker.
