CODEX WORK ORDER (step 8i, work order 1)

GOAL: make `backend/tests/test_star_alerts.py` pass. Create `backend/nflpi/notify/star_alerts.py`; add `star_summary_hour` to `backend/nflpi/config.py`; add the call to `tick()` in `backend/nflpi/jobs.py` (at most 10 added lines).

BASELINE: branch lane/staralerts, commit just made (tests red: `cannot import name 'star_alerts'`).

ALLOWED SCOPE (only these): backend/nflpi/notify/star_alerts.py (new), backend/nflpi/config.py (add one field, nothing else), backend/nflpi/jobs.py (import + a try/except block in tick(), nothing else). Do NOT edit tests, push.py (import and reuse its `_send`, `_record`, `configured`, `game_url`, `EASTERN`), analytics/stars.py (import `_star_report` and `ALERT_STATUSES` from it, read only), models, migrations, api, apps/web.

REQUIREMENT (spec: docs/gauntlet/logs/step-8i.md, clauses A1-A14; the tests are the contract). Public: `run(session, now) -> {"immediate": int, "summary": int}` (alerts delivered, not devices), `BASELINE_KEY = "star_alerts_baseline"`.
Algorithm:
1. If `team_stars` has no rows: return zeros, store nothing. If AppSetting BASELINE_KEY is missing: store {"report_id": max(InjuryReport.id) or 0}, commit, return zeros.
2. Changes: InjuryReport rows with id > baseline, observed_at >= now - 24h (MAX_CHANGE_AGE), report_status in stars.ALERT_STATUSES, whose status differs from the previous row (largest smaller id) of the same (season, week, team, player_id or player) (no previous row = a change). Game for the row: the club's Game that season/week (home or away), status == "scheduled", kickoff_utc > now, earliest kickoff; none -> skip. Star: TeamStar rows of that club for the latest star week <= game.week; a row matches when `stars._star_report(star, [report])` is not None; none -> skip. Skip a change that already has Notification dedupe_key `star:<id>` or (for any change) `inj:<season>:<week>:<player_id or player>:<status>` (step 7's quarterback alert).
3. Immediate: a change whose game has kickoff - 90 min <= now < kickoff is sent on its own via `push._send(session, title, body, push.game_url(game_id), ttl=int((kickoff-now).total_seconds()), headers={"Urgency": "high"})`; if delivered >= 1, `push._record(session, "star", game_id, f"star:{id}", {"title":..., "body":...})` and count it. Not delivered: record nothing (it is retried next round while eligible). Wrap each change so one exception is logged (`log.exception`) and the next continues; rollback the session on error.
4. Summary: let hour = settings.star_summary_hour; Eastern now = now.astimezone(EASTERN); send only when date's hour H <= eastern.hour < H + 3 (SUMMARY_GRACE_HOURS) and no Notification key `starsum:<eastern date iso>`. Pending = changes from step 2 not delivered and whose game is NOT in its 90-minute window (kickoff - 90 min > now). Group by star (club + star player), newest change wins the status; none -> send nothing, record nothing. Title `Star report: N change today` / `N changes today` (N = distinct stars). Body: up to 4 lines `<name> (<club>) <Status>`, joined by "\n", then `+K more` line if more. Url "/". Send with push._send (default ttl); if delivered, record `starsum:<date>` (kind "starsum") and a `star:<id>` row (kind "star") for EVERY pending change in the group (so they are never sent again), count 1.
5. Immediate text: title `Star <status lower>: <name> (<club>)`, body `<AWAY> @ <HOME>, <h:mm AM/PM> ET.` + ` <injury>.` when the report has injury text (kickoff via `kickoff.astimezone(EASTERN).strftime("%-I:%M %p")`).
6. Text cleaner `_plain(text, limit)`: collapse any whitespace run (incl. newlines) to one space, drop other non-printable characters, strip, cut to `limit` characters (name 40, injury 30). Names come from the star row (`TeamStar.player`), never from news.
7. Log once per run that sent anything: `log.info("star alerts: immediate=%d summary=%d", ...)`. Never log endpoints, keys or subscriptions. Commit the session at the end of each part.
8. config.py: `star_summary_hour: int = Field(default=8, ge=0, le=23)` beside the other alert settings (import Field if missing); comment: 8 AM Eastern.
9. jobs.py `tick()`: after the kickoff reminders block add
   try: star_alerts.run(session, now)
   except Exception: log.exception("star alerts failed"); session.rollback()
   (import `star_alerts` from nflpi.notify next to `push`.)

PROOF: from `backend/`: `DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15438/nflpi_staralerts uv run pytest tests/test_star_alerts.py -q` (coordinator runs it; Codex cannot reach Postgres, so also run `uvx ruff check nflpi tests`).

CONSTRAINTS (ponytail): smallest correct diff; module under ~170 lines; no new dependency, table, migration, class hierarchy or config beyond one field; no mutation of arguments; early returns; named constants (MAX_CHANGE_AGE, IMMEDIATE_WINDOW, SUMMARY_GRACE_HOURS, SUMMARY_LINES, NAME_LIMIT, INJURY_LIMIT); line length 120; match push.py style. Do not commit. Do not push.
RETURN: changed files, summary, ruff result, blockers.
