# Step 8i: star alerts and the morning summary (lane staralerts)

Session: owner's Mac, 2026-10-13, lane `staralerts`, branch `lane/staralerts`, base `main@d8276a2`. Tier T2. Server only: no screen, route, schema or migration.

## 1. PLANNING

* **In the owner's words (D23, D25):** an alert when a star is Out or Doubtful, or Questionable; "one morning summary of that day's star changes; in the last 90 minutes before a game, a new change to that game is its own immediate alert". This step builds `backend/nflpi/notify/star_alerts.py`, called from the worker tick. It replaces nothing. It is not: a screen, a per-alert switch, news text in an alert, a change to who is a star, a model change, a new data source.
* **Pre-flight:** problem: he learns a star is out only by opening the app. Why now: week 6 kicks off Thursday 2026-10-15 and the star list (8a/8a2) landed. Scope: the two delivery rules over the data the app already stores. Metric: every star status change before a game reaches his phone once (one push per change or one morning push). Reversibility: two-way door (D23, D25 are two-way).
* **Prior decisions relied on:** `docs/gauntlet/OWNER_DECISIONS_2026-10-12.md` D21-D27, D47; step 7 log (dedupe in `notifications.dedupe_key`; a send that reached no device is not recorded, so the reminder path retries it next round; no second dedupe).
* **What the stored data can show (checked in code):** `injury_reports` has one row per change of (report status, practice status) with `observed_at`, from the nflverse injury file only; statuses stored are Out / Doubtful / Questionable or empty. There is no ESPN source in the code, no transactions feed, no game-day inactive list. So D23's triggers split:
  * **Built:** a star's report status becomes Out, Doubtful or Questionable.
  * **CARRIED, not guessed:** injured reserve, suspension, trade (no data: nflverse injuries has no such status and the app has no transactions source; needs the D26 ESPN source); game-day inactive (no inactives list stored); return after missing games (the games a player missed are not stored per player, and a cleared report row is not proof he missed a game).
* **Assumptions:** `validated` ingest writes a row only when status or practice status changes (`service.ingest_injuries`); `validated` `Notification.dedupe_key` is unique and `push._record` tolerates a repeat; `validated` the worker `tick` runs every 5 minutes and is already guarded by try/except; `assumed` `observed_at` (first time the app saw the row) is a fair "when it changed"; `assumed` the owner prefers one push over two for a starting quarterback, so a change step 7 already alerted (`inj:` key) is not alerted again.
* **Skills:** `/jevgrep`: `jg` binary not used, behaviour questions were answered by reading the five files named in the brief (recorded as N/A: small seam, files named by the brief). `/graft`: N/A, same reason. `/tdd` project skill: none exists in the repo; `/tdd` rules used. `/ponytail`: no new table, no migration, one module. Design Gauntlet: N/A (no UI). `harness-engineering`: no runner or approval boundary changed; surfaces: locked = step 7 alert rules and `analytics/stars.py`; editable = `notify/star_alerts.py`, tests; durable state = `notifications` rows plus one `app_settings` row.

## 2. SPECIFICATION (frozen before production code)

Definitions. A **change** is an `injury_reports` row R with `R.id > baseline`, `R.observed_at` within the last 24 hours (`MAX_CHANGE_AGE`), `R.report_status` in {Out, Doubtful, Questionable}, whose status differs from the status of the previous row for the same (season, week, team, player), and which belongs to a current star (same match rule as `analytics/stars.py`) of a scheduled game of that club that week that has not kicked off.

| ID | Clause | Layer |
|---|---|---|
| A1 | A new row with an alert status on a star of an upcoming game is a change; a row with the same status as the previous row for that player and week (only the practice status changed), a row with no status, a row for a player who is not a star, and a row for a club with no game that week are not. | functional |
| A2 | The first run with a star list stores the baseline (highest injury row id) and sends nothing, however many stars already have a status. With no star list there is no baseline and nothing is sent; the first run after a list appears is the baseline run. Later rows are changes. | functional |
| A3 | One alert per change: key `star:<row id>` in `notifications` (step 7's dedupe). A second round, a new database session (a restart) or a repeat call sends nothing. A change whose `inj:` quarterback alert (step 7) was already recorded is not alerted again. | functional |
| A4 | The 90-minute rule on `now`: for a game with kickoff K, a change goes out on its own when `K - 90 min <= now < K`; at `K - 90 min - 1 s` it does not (it waits for the morning summary); at `now >= K` nothing is sent. | functional |
| A5 | Nothing is sent for a game that has kicked off, is final, or is postponed: neither its own alert nor a line in the summary. | functional |
| A6 | Morning summary: sent once per Eastern calendar day, when the Eastern clock is at or past `star_summary_hour` and before that hour + 3 (`SUMMARY_GRACE_HOURS`); not before; not twice; setting `star_summary_hour` (default 8, 0 to 23) in `config.py`. It holds only changes not yet delivered, observed in the last 24 hours, for games more than 90 minutes away; a change older than 24 hours is not in it. A star with two changes the same day appears once, with the newest status, and both changes are consumed. | functional |
| A7 | No changes pending: no summary is sent and none is recorded. | functional |
| A8 | The summary is bounded: at most 4 stars listed, then `+N more`; every name is plain text, control characters removed, at most 40 characters; the whole body stays under 300 characters. | functional |
| A9 | A failed send (push service error, network error) is logged without the address or keys, records nothing, never raises out of the round, and the change is sent on a later round while it is still eligible. A gone subscription is dropped by step 7's `_send`. | operational |
| A10 | With no push subscription, no VAPID keys, no star list or no injury rows the round completes and returns zero. | operational |
| A11 | Alert text is built only from the player name, club code, status (a fixed set), the injury text and the kickoff time of our own tables. No news item is read. Names and injury text pass through the same cleaner (A8). | security |
| A12 | The worker tick calls the module, and an exception from it is logged and does not stop the tick (the reminders still run). `jobs.py` gains at most 10 lines. | operational |
| A13 | Exact texts. Immediate: title `Star out: <name> (<club>)` (word `out`, `doubtful` or `questionable`), body `<AWAY> @ <HOME>, <h:mm AM/PM> ET. <injury>.` (injury sentence left out when the report has none), link `/game/?id=<id>`, high urgency, time to live until kickoff. Summary: title `Star report: N change(s) today`, body one line per star `<name> (<club>) <Status>`, link `/`. | user-facing |
| A14 | Instrumentation: each send logs one line (`star alerts: immediate=<n> summary=<n>`), rows in `notifications` kind `star` / `starsum` are the history. Guardrail: the morning summary is the only push for changes more than 90 minutes out. | operational |

Out of the frozen clauses and carried: the triggers named under PLANNING; per-alert switches; a screen; alert history.

Choice of hour (A6): 8 AM Eastern. It lands after the Wednesday-to-Friday practice reports are in, before the 9:30 AM London kickoffs' own 90-minute window, and early enough that a Sunday-noon change is seen over breakfast. It is a setting because the owner never chose it.

Gate: `cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15438/nflpi_staralerts uv run pytest -q && uvx ruff check nflpi tests migrations && uv run alembic check`; `npm run gen:api` shows no drift. Tests: `backend/tests/test_star_alerts.py` (new file, mine).

## 3. IMPLEMENTATION

* **Provider.** `codex exec` run once with no model flag (14:55 UTC, `codex-cli 0.156.1`): refused with `The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account.` (status 400, twice). Codex counts as unavailable; work order 1 (`step-8i-evidence/wo-1.md`) went to a Sonnet subagent (Claude rung 1, try 1 of 2). The coordinator wrote the spec and the tests, and inspects the diff and reruns every proof itself. EFFORT: build at low (a hand-traced test list is the contract).
