# CODEX WORK ORDER 2 — step 7, lane alerts: server side of alerts (D19 reminder per game day, D20 drastic changes, D47 threshold, test alert)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).
Launch (prompt on stdin, never as an argument): `codex exec -m <model> -c 'model_reasoning_effort="<effort>"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make `backend/tests/test_alerts.py` (N1 to N7) pass, and keep every other backend test green, including the reminder tests in `test_hardening.py` and `test_api.py` that the coordinator has already rewritten to the new rule.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-7.md` section 2 (criteria N1 to N7); owner decisions D19, D20, D47 in `docs/gauntlet/OWNER_DECISIONS_2026-10-12.md`.

ALLOWED SCOPE (edit only these):
- `backend/nflpi/config.py` (`alert_move_threshold` only)
- `backend/nflpi/notify/push.py`
- `backend/nflpi/predictions/engine.py` (`ChangeEvent` and the block in `refresh_predictions` that appends a `ChangeEvent`, near line 280, only)
- `backend/nflpi/api/main.py` (the push routes and the `reminder_minutes` value in `meta` only)
- `backend/nflpi/api/schemas.py` (push shapes only)
- `backend/nflpi/jobs.py` (only if a call signature you change needs it)
- `packages/shared/openapi.json` and `packages/shared/src/api-types.ts`, by running `npm run gen:api` only. Never by hand.

NOT ALLOWED: `backend/nflpi/models.py`, `backend/migrations/**`, `backend/nflpi/ingestion/**`, `backend/nflpi/api/views.py`, anything under `backend/tests/`, `apps/web/`. Another lane owns the models and migrations. If you believe a schema change is needed, stop and tell Jim.

REQUIREMENT

N1. `alert_move_threshold` default is 0.07.

N2. Reminder per game day (replaces the per-game "No pick yet" reminder; keep the name `send_kickoff_reminders(session, now) -> int`).
- A game day is a US Eastern calendar day (`America/New_York`). Only games with status `scheduled` and a clock time (`time_tbd` false) count.
- For each game day, take its first kickoff K. When `K - reminder_minutes <= now < K`, send one alert. One per day; a later game the same day sends nothing. Sent whether or not he has picked.
- `reminder_minutes`: the `app_settings` value; when no value is stored it is 60; 0 is off. `GET /api/meta` and the `PUT /api/settings` reply report 60 when nothing is stored.
- Title: two or more games that day: `Games today: first kickoff 1:00 PM ET`; one game: `Game today: kickoff 8:15 PM ET` (Eastern time, 12-hour, no leading zero). Body: `2 games today. First: MIA @ BUF.`; one game: `1 game today: NYJ @ LV.`. URL `/sheet/`.
- Time to live = whole seconds from `now` to K. Header `Urgency: high`. Request timeout stays 10 s.
- Dedupe key carries the Eastern date and K, so a rescheduled first kickoff reminds again. As today: the alert is recorded only when at least one device took it, so a failed send is retried on the next tick, and a subscription the push service calls gone (404, 410) is deleted.

N3, N4. Drastic changes (D20). In `refresh_predictions`, a change is alert-worthy when any of: the pick flips; the win chance moves by at least the threshold (both exist); the label changes; a starting QB changes.
- Label = `nflpi.analytics.metrics.pick_label(max(p, 1 - p))` of the previous and the new snapshot.
- Starting QB change = `home_qb` or `away_qb` in the new features differs from the previous snapshot's features, and the new value is not empty.
- `ChangeEvent` gains what the alert needs, as fields with defaults: the six-positional call `ChangeEvent(game_id, old_prob, new_prob, old_pick, new_pick, note)` must keep working.
- `alert_prediction_changes` picks one alert per event, in this order: flip (`Pick flipped: A @ H`, unchanged), QB change (`QB change: A @ H`, body names the team and the new QB, then the pick and its chance), label change (`Now a tough matchup: A @ H`, `Now an easy pick: …`, `Now a coin flip: …`; body starts `Was an easy pick.` and so on, then the pick and its chance), big move (unchanged).
- The dedupe key must tell these apart: two different changes for one game are two alerts, the same change seen twice is one.

N5. `alert_prediction_changes(session, events, now=None)`: `now` defaults to the current UTC time. An event for a game that is missing, not `scheduled`, or whose kickoff is at or before `now` sends nothing and records nothing.

N6. `POST /api/push/test` (inside the authenticated `/api` router, so 401 without the token). Sends `{"title": "Test alert", "body": "Alerts work on this device.", "url": "/settings/"}` to every subscription, time to live 60 s, `Urgency: high`, and returns
`{"configured": bool, "devices": int, "delivered": int, "results": [{"host": str, "ok": bool, "status": int | null, "error": str | null}]}` with a response model in `schemas.py`.
- `host` is the host name of the subscription's endpoint, never the whole endpoint (the full address is a secret).
- `status` is the push service's HTTP status when there is one (the `requests` response from `webpush`, or the response on a `WebPushException`), otherwise null. `error` is null on success, otherwise one short sentence in plain words that contains no endpoint, key or token.
- 404 and 410 delete that subscription, as today. Other failures keep it.
- Push not configured: `configured: false`, `devices` = how many are stored, `delivered: 0`, `results: []`, nothing sent.
- The test alert is not written to `notifications`.
- One sending loop: do not copy `_send`. Reshape it so the alerts and the test share it.

N7. Nothing extra to build: it passes when N6 goes through the real `pywebpush.webpush`.

FAILING EVIDENCE: `docs/gauntlet/logs/step-7-evidence/red-wo2.log` (9 failed, 1 passed). After the coordinator's test rewrites, `test_hardening.py` and `test_api.py` also fail on the old reminder titles until N2 is built.

PROOF (run these; the coordinator reruns all of it):
- `cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test uv run pytest -q` if you can reach that database; if you cannot, say so.
- `cd backend && uvx ruff check nflpi tests migrations`
- `npm run gen:api` then `npm run typecheck` from the worktree root.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no new table or column.
- Never log or return a full subscription endpoint, a key or the VAPID private key.
- Match the surrounding style: typed, ruff line length 120, no `print`.
- Never use the default test database on port 5432: that is the live app. Never touch ports 8000 and 5432 or containers `nfl-pickem-app-*`. Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
