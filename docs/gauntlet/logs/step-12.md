# Step 12 of 14: Trends

Session: owner's Mac, 2026-10-12, lane `trends` (worktree `.claude/worktrees/lane-trends`, branch `lane/trends`, base `main@9d41cb0`), run beside lane `pwa` (step 6).
Coordinator: Claude (hive temp "Oscar", dispatched by the integrator). Builder: Codex. Lane claim `claims/trends`, coord task #2.
Evidence folder: `docs/gauntlet/logs/step-12-evidence/` (every log named below lives there).

## 1. PLANNING
* **In the owner's words (D30):** for each game, show "matchups ... like a key player, qb ... has secret trends against a certain team" and "key trends like the jags never lost in London or the browns never lost on Tuesday night". This step builds the records and puts them in front of the chat (Claude or Jev), so it can answer with real counts. It replaces nothing. It is not: a trends panel on the game screen, a change to any pick, or coordinator and non-QB player trends.
* **Roadmap row:** PLAN.md row 12: team, QB, coach, venue and weekday records with sample size, all years and last 5 seasons, 8-game floor, into the chat's evidence pack. Gate: hand-checked counts on known examples; never moves the pick unless it wins walk-forward.
* **Tier:** T2. Reversibility: two-way (one new module, one new key in the evidence pack, no schema or API change).
* **Decisions relied on:** D30 (trends as records with sample size and years, never a claim), D29 (chat reads the evidence pack), D18 and `CLAUDE.md` (a trend moves the pick only after a walk-forward win). The launcher cites "Q3-Q5" in OWNER_DECISIONS: no items carry those labels there. The open items in the D30 notes are the floor (PLAN row 12 fixes it at 8) and a hand-kept coordinator table (needs new data: not built).
* **Scope, and what is cut:** `backend/nflpi/analytics/trends.py` and a `trends` key in `evidence_pack`. Cut: the game-screen panel (needs `api/schemas.py`, `api/views.py` and `apps/web`, which are seams or lane pwa's files; carried to the integrator), coordinators and non-QB players (no data), kickoff slot, bye and short-week, coach against coach, in-division (not in row 12).
* **Pre-flight:** Problem: the owner wants to ask "how do the Jaguars do in London?" and get a real count, not a guess. Why now: the chat exists (D29) and the pack has no history beyond recent meetings. Scope: as above. Success signal: the chat's pack carries hand-checkable records for every upcoming game; no number: the app has one user and no usage tracking. Reversibility: two-way.
* **Assumptions:** `validated` the `games` table already holds teams, scores, QB and coach names, stadium, stadium id, weekday and neutral-site flag (`models.py`); `validated` real data check from the nflverse schedule file (7,354 finished games, 1999-2026): Jaguars at London stadiums, Browns on Tuesday (section 2); `validated` one London game is filed under stadium id `JAX00` with the name "Tottenham Hotspur Stadium", so an id-only count gives 7-6 in 13 where D30 says 8-6 in 14; `assumed` a QB or coach is identified by name (the table stores no id; two people with one name would be merged).
* **Instrumentation:** none added. PROCEEDING WITHOUT: single-user app with no analytics; the operational signal is the `trends` key in every saved prompt's evidence pack, and a failed query fails the AI call loudly (no silent empty list).
* **Skills:** `/jevgrep`: `s12-jg-trends-seam.log` ranked `api/views.py` (season records, recent meetings), `ai/research.py` and `models.py`; it showed no all-years record code to reuse. `/graft`: N/A (file homes known after jg). `tdd`: no project tdd skill; the coordinator wrote the failing tests before any production code. `ponytail`: in every work order. Design Gauntlet: N/A (no screen). `harness-engineering`: N/A.
* **Tools:** `JEVGREP: ready`. `HEADROOM: not-routed` (doctor exit 2; not a blocker). Codex: `codex-cli 0.156.1`, probe answered.
* **Test database:** own container `nflpi-lane-trends-db` on `127.0.0.1:15437`, no volume. The live stack on 5432 and 8000 is never used.
* **Baseline at `9d41cb0`:** `PASS uv run pytest -q exit=0` 99 passed (`s12-baseline-pytest.log`); `PASS uvx ruff check nflpi tests migrations exit=0` (`s12-baseline-ruff.log`).
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low (Codex builds); VERIFICATION high.

## 2. SPECIFICATION
Public seam: `nflpi.analytics.trends.game_trends(session, game_id) -> list[dict]` and `evidence_pack(...)["trends"]`. Gate: `backend/tests/test_trends.py` (9 tests, every expected number counted by hand from the rows in the test), then the full suite, ruff, and `npm run gen:api` with no drift.

| # | Criterion | Layer |
|---|---|---|
| T1 | A record counts only finished games that kicked off before this game. The game itself, later games and unplayed games never count | functional |
| T2 | Six kinds, each for the home and the away side: `team_vs_team`, `qb_vs_team` (this side's listed QB against the opponent, for any club), `coach_vs_team`, `team_at_stadium` (same stadium id, across renames), `team_at_site` (neutral-site games only: every stadium sharing the id's 3-letter prefix, or one of their names), `team_on_weekday` | functional |
| T3 | Two windows: `all` and `last_5_seasons` = the five finished seasons before the game's season | functional |
| T4 | A record with fewer than 8 games is left out. `MIN_GAMES = 8` | functional |
| T5 | Each row carries `kind, team, person, context, window, wins, losses, ties, games, first_season, last_season` | functional |
| T6 | A missing QB, coach or stadium id gives no row for that kind. Missing stays missing. An unknown game id raises `LookupError` | functional |
| T7 | `evidence_pack` has `trends = {min_games, note, records}`; the system prompt tells the AI that trends are context with a sample size and never change the pick | user-facing |
| T8 | Trends never reach the model: no new prediction row, nothing under `nflpi/predictions` mentions trends | functional |
| T9 | On the real schedule file the app's counts equal an independent hand count for known examples (Jaguars in London 8-6 in 14, Browns on Tuesday no record, and four more) | user-facing |
| T10 | A database error inside the trends query fails the AI call with its real error; it is never swallowed into an empty list | operational |

Decisions (each two-way):
* `JEV: model:trends:wo1 -> sol 0.45 (unsure), effort medium 0.92`. `ADVISOR: sonnet -> sol`. Start rung `gpt-6-sol`, medium.
* `JEV: window -> current_plus_four 0.58 (unsure)`. `ADVISOR: sonnet -> five_completed` (a part season inside a "last 5 seasons" label misleads; "all years" already holds this season). Followed the advisor. Revisit trigger: the owner wants the season in progress counted.
* Playoff games count in every record (coordinator; a win is a win). Revisit trigger: the owner wants regular season only.
* Site grouping matches the stadium id prefix or the stadium name, because of the misfiled London game above.

Red: `s12-red.log`, `ModuleNotFoundError: No module named 'nflpi.analytics.trends'` at collection. Right reason: the module does not exist. The nine tests were written together by the coordinator (the builder never writes its own bar), not one per build slice.
BUILD_RUNG: gpt-6-sol medium (try 1 of 2). Reason: one module, six record kinds with a before-kickoff cutoff and a prefix-or-name site match; nine hand-counted tests check it.
