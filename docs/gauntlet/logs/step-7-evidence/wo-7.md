# CODEX WORK ORDER 7 — step 7, lane alerts: review round 1 fixes, server side

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make the 14 red tests in `backend/tests/test_alerts.py` (section "Round 2", list in `red-wo7.log`) green without changing any test, and keep every other test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message. The branch now sits on the new main (step 8a landed under it): read the files fresh.

ALLOWED SCOPE: `backend/nflpi/notify/push.py`, `backend/nflpi/api/schemas.py` (`PushSubscriptionIn` only), `backend/nflpi/predictions/engine.py` (the `moved` comparison only). If `schemas.py` changes the OpenAPI output, run `npm run gen:api` and include the generated files under `packages/shared/src/`. Nothing else. No `models.py`, no migration.

REQUIRED BEHAVIOUR
1. **One reminder per game day (critic B2).** `send_kickoff_reminders` picks the day's first kickoff from the games still `scheduled`, so when the 1:00 PM game goes final the 8:20 PM game becomes "first" and a second reminder goes out. The day's first kickoff is the earliest kickoff of all that Eastern day's games with a clock time, whatever their status. Keep the dedupe key as it is (`test_rescheduled_kickoff_reminds_again` in `test_hardening.py` must stay green). The game count and the matchup in the text stay as the existing tests pin them.
2. **Only real push services may be stored (security S1a).** `PushSubscriptionIn.endpoint` is valid only when it is `https`, has no port and no user info, and its host is one of, or a subdomain of: `push.apple.com`, `fcm.googleapis.com`, `push.services.mozilla.com`, `notify.windows.com`. Anything else is a 422 from the schema, before any row is written. Parse the address (`urllib.parse.urlsplit`); do not match the host with a regular expression on the whole string. One named constant for the host list.
3. **A send failure says its kind (security S2).** The catch-all in `_send` logs the exception's class name beside the host. Never the endpoint path, the exception's message, a key, or a traceback.
4. **A forgotten device is told what to do.** For 404 and 410 the error text is exactly `Push service no longer recognizes this device. Turn alerts off and on again.`
5. **An exact 7 point move counts (critic S4).** `abs(prob - prev.home_win_prob)` is `0.0699…` for 0.57 against 0.50. Round the difference before comparing it with the threshold (4 decimal places is enough); 6.5 points must still not count.

PROOF (the coordinator reruns all of it; you cannot reach the test database, so say so): `cd backend && uvx ruff check nflpi tests migrations` and, if you ran `gen:api`, `npm run typecheck`.

CONSTRAINTS: smallest diff that does each item (Ponytail); no new dependency; no test edits; never log or return a full endpoint or a key; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): per item the changed lines; the proof commands with exit codes; any blocker.

## Try 2 (addendum)

Try 1 made 13 of the 14 red tests green and is kept in the worktree, uncommitted. Two things remain (`red-wo7-try2.log`: 2 failed, 201 passed). Same allowed files, same constraints.

A. **My item 1 was wrong: "whatever their status" let a postponed game be the day's first.** `test_postponed_game_keeps_its_status_and_gets_no_reminder_or_pick_lock` (`test_hardening.py`) is red. The day's first kickoff is the earliest of that day's games with a clock time that are not `postponed` (`scheduled` and `final` both count; `models.py` has only those three statuses). A postponed game is also not in the game count.

B. **An alert that reached no device is not recorded as sent (integrator ruling; security S3, critic S1).** `alert_prediction_changes` and `alert_injuries` store the dedupe row first and then send, ignoring the result: with the push service down the alert is used up. Do it the way `send_kickoff_reminders` already does: skip when the key is already stored, send, and store the row only when at least one device got it. One small helper shared by the three callers is welcome if it makes the three read the same; no other change to them. Red test: `test_n3_an_alert_that_reached_no_device_is_not_recorded_as_sent`.
