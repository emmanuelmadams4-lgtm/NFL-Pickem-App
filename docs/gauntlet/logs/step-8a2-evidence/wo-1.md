# CODEX WORK ORDER 1 — step 8a2, lane web: stars and who is out, server side

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make the 10 red tests listed below green without changing any test, and keep every other test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message. Read `docs/gauntlet/logs/step-8a2.md` section 2 ("Frozen contract" and criteria B1 to B6) first: it is the spec.

ALLOWED SCOPE: `backend/nflpi/analytics/stars.py`, `backend/nflpi/api/schemas.py`, `backend/nflpi/api/views.py`, `backend/nflpi/jobs.py`, and the two generated files `packages/shared/openapi.json` and `packages/shared/src/api-types.ts` (run `npm run gen:api`; never hand-edit them). Nothing else: no `models.py`, no migration, no `ingestion/`, no `config.py`, no web code, no test file.

REQUIRED BEHAVIOUR
1. **B1 each club's own list** (`stars_out`): today one `stars_week` is taken over both clubs and only rows of that week are read, so the club with the older list loses its stars. Read, per club, that club's newest list of the game's season at or before the game's week. `stars_week` in the result stays the newest of the two (existing tests pin it). Order of `out` stays: away club first, then slot (qb, off, def), then rank.
2. **B2 the full five** (new `game_stars(session, game_id, now=None)` in `analytics/stars.py`): shape in the frozen contract. Both clubs, away first; each with its own `stars_week` (None and an empty list when the club has no list); every star in slot then rank order with his newest report of the game's week: `status` (the report's `report_status`, or None when he has no report or the report has no game status), `injury`, `observed_at`, `age_hours` (None when no status). Unknown game: `LookupError`, as `stars_out` does. Share the lookup code with `stars_out`; do not copy it.
3. **B3 names spelled two ways** (`_star_report`): when both sides have an id, only the id decides (as today). Otherwise compare names after: lower case, dots and apostrophes removed, one trailing suffix `jr`, `sr`, `ii`, `iii`, `iv`, `v` removed, runs of spaces collapsed. Same club only (as today). One small named helper.
4. **B4 the API carries it** (`schemas.py`, `views.py`): `StarStatus`, `StarsOut`, `TeamStars` as in the contract; `GameSummary.stars_out` (so `GameDetail` has it too) and `GameDetail.stars`. `StarStatus` has no `age_hours` (the web works the age out from `observed_at`). Every `player`, `position`, `status` and `injury` text has Unicode categories Cc and Cf removed before it leaves the API (one helper in `views.py`, `unicodedata.category`); the result is stripped of leading and trailing spaces and inner runs of spaces are collapsed. A game with nothing known: empty `out`, `reports_seen` 0, no error.
5. **B5**: nothing in `predictions/` or the pick sheet reads any of this. Do not touch them.
6. **B6 the worker** (`jobs.ingest`): after injuries, call `service.ingest_stars(session, season)` for the current season and put its `.status` in the returned dict under `stars`. `ingest_stars` already logs its own failure and returns a run with status `failed`; additionally an exception from it must not stop the round (log it, roll the session back, report `failed`), the way `tick` treats reminders.

RED TESTS (`step-8a2-evidence/red-1-stars.log`, `red-1-api.log`)
* `backend/tests/test_stars.py`: `test_stars_out_uses_each_clubs_own_latest_list`, `test_game_stars_lists_every_star_of_both_clubs_with_his_status`, `test_a_star_with_no_id_is_matched_when_the_two_files_spell_his_name_differently` (6 cases).
* `backend/tests/test_api.py`: `test_week_board_says_which_stars_are_out_and_the_game_view_lists_all_of_them`, `test_the_worker_refreshes_the_star_list_and_a_failure_does_not_stop_the_round`.
* NOT yours: `test_freshness_lists_the_star_list_and_the_head_coaches` stays red. It needs a file outside this lane; the integrator is deciding.

PROOF (the coordinator reruns all of it; you cannot reach the test database or bind a port, so say so): `cd backend && uvx ruff check nflpi tests migrations`, `npm run gen:api`, `npm run typecheck`.

CONSTRAINTS: smallest diff that does each item (Ponytail: no new module, no new dependency, no speculative option); match the surrounding code; ruff line length 120; no test edits; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): per item the changed lines; the proof commands with exit codes; anything you could not run; any blocker.
