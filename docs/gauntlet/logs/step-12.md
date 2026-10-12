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

### Spec amendments after the freeze
* **Owner decisions, relayed by the integrator (card HAG-9, 2026-10-12, both two-way):** (1) the sample floor is **4 games**, not 8 ("I would say 4 games"): T4 and `MIN_GAMES` are now 4. (2) Play callers are wanted ("I want play callers and news about switching play calls"). New criterion **T11**: records by offensive and defensive play caller (`off_caller_vs_team`, `def_caller_vs_team`) from a hand-kept table `backend/nflpi/analytics/play_callers.py`, one row per (team, season, side, name, first week, source link), same floor; the caller for a game is the row with the latest first week not after that game's week, so a mid-season switch is followed. News about play-calling switches is step 8, not this lane. Revisit trigger for both: the owner says so.
* **The real play-caller table ships empty.** Nothing was entered because 32 clubs by two sides by many seasons could not be sourced reliably inside this step, and a record needs 4 games against one opponent, so a few rows would show nothing anyway. The mechanism is tested on made-up fixture people. Until rows are added, no play-caller record appears and the pack note says why.
* **"Last 5 seasons":** both lines recorded above (Jev 0.58 unsure for current-plus-four; advisor chose five finished seasons). The integrator confirmed: take the advisor's answer.
* **From review round 1 (section 3):** T1 also requires both scores present; `team_at_site` counts only neutral-site games; site names come only from counted games; an empty id or name is treated as missing; the pack note states the limits (floor, window meaning, playoffs counted, name matching, projected QB, play callers).
* Red for each amendment, written by the coordinator before the fix: `s12-red-2.log` (3 failed: null score counted as a tie, own home games counted as a neutral-site record, note without the limits), `s12-red-3.log` (`No module named 'nflpi.analytics.play_callers'`).

## 3. IMPLEMENTATION
Provider: Codex, every production line. The coordinator wrote the tests, the hand-count script and this log, inspected each diff (`git status`, `git diff`, untracked files) and reran every proof itself.

| Work order | Rung | Decision | Result | Commit |
|---|---|---|---|---|
| WO-1 trends module + evidence pack key | `gpt-6-sol` medium, try 1 | `JEV: model:trends:wo1 -> sol 0.45 (unsure), medium 0.92`; `ADVISOR: sonnet -> sol` | 9 of 9 tests, in scope (2 files) | `eccc4ae` |
| WO-2 review round 1 fixes | `gpt-6-luna` medium, try 1 | `JEV: model:trends:wo2 -> luna 0.83, medium 0.44 (unsure; taken)` | 13 of 13, in scope | `f1cad1b` |
| WO-3 owner amendment (floor 4, play callers) | `gpt-6-sol` medium, try 1 | `JEV: model:trends:wo3 -> sol 0.38 (unsure), medium 0.88`; same size class as WO-1, where the advisor chose sol, so no second advisor call | 15 of 15, in scope (3 files) | `8f6a42a` |

CLIMBS: none. STRIKES: none. Codex could reach the lane's own test database, so its test runs were real; each was still rerun by the coordinator.

Proof after the builds: `PASS uv run pytest -q exit=0` 108 passed at `eccc4ae` (`s12-impl-pytest.log`); `PASS uvx ruff check nflpi tests migrations exit=0` (`s12-impl-ruff.log`); `PASS npm run gen:api exit=0`, no change to `packages/shared/openapi.json` or `api-types.ts` (`s12-genapi.log`).

**T9, real data (`s12-handcount.py`, `s12-handcount.log`):** the schedule file from nflverse (6,577 finished games from 2002) is loaded into a throwaway database; an independent count that reads the CSV directly and shares no code with the module is compared with the app, both windows. 12 of 12 MATCH. Jaguars in London: 8-6 in 14, 2013-2026 (D30's number); last five finished seasons 4-2 in 6. Chiefs against Raiders 35-14 in 49. Mahomes against Broncos 13-2 in 15. Andy Reid against Broncos 18-10 in 28 (includes his Eagles years). Cowboys on Thursday 24-15 in 39. Packers at Lambeau 145-62-2 in 209. Browns on Tuesday: 0 games in the file, so no record is shown.

Review fan-out (standard tier; reports returned in the reviewers' final messages, findings summarised here):
* `ecc:code-reviewer` on `9d41cb0..7dc8423`: APPROVE with changes, no CRITICAL or HIGH. MEDIUM: whole-table select (done in CLEANUP); site names taken from unplayed games (fixed, WO-2); no test for T10 or a null stadium id (tests added). LOW: note hardcoded 8 (fixed), readability of `_matches`/`_record` (CLEANUP).
* `ecc:silent-failure-hunter` on the same range: two HIGH, both mapped and fixed in WO-2 with a failing test first: a final game with a null score raised or counted as a tie (T1, "never invent data"); the neutral-site record counted a club's ordinary home games when the neutral game was in its own stadium (T2). MEDIUM, accepted and stated in the pack note instead of built: QB and coach matched by name, the listed QB is a projection, playoffs pooled, window meaning. MEDIUM fixed: empty id treated as missing.
* Security: Dwight (`dwight-mv5mkpow`, hive security reviewer, with `ecc:security-reviewer`) on `7dc8423`: **PASS**, no CRITICAL or HIGH. His two asks are done: null scores filtered in SQL with a test; the one SQL `startswith` now uses `autoescape=True`. Clean: bound parameters only, names reach the prompt through `json.dumps`, no new route, no secrets, no future data. A re-review of the later commits was requested (section 5).
* Not built, on purpose: a guard that turns a trends error into an empty or null list. T10 keeps the failure loud; the test pins it.

## 4. CLEANUP
`/refactor` at coordinator level, scope-locked to `trends.py` (the skill's `guide.md` was not re-read; its smell list was applied). Picked two transformations, both behaviour-preserving; `play_callers.py` and the `research.py` block: no change needed (a constant and one dict entry).
1. Unify duplicated per-kind branching: `_matches` (8 parameters) and the side logic inside `_record` became one `_home_side` that returns home, away or not counted; `_record` only tallies.
2. Narrow the select to games involving either club (every kind only counts those); stadium names for a neutral site come from a second small query.

WO-4 (`gpt-6-luna` medium, try 1; `JEV: model:trends:wo4-cleanup -> luna 0.69 (unsure), medium 0.88`): tests green, but the coordinator's read found a regression the tests did not cover (a null stadium name broke the sort), an 85-line function and chained conditionals. A failing test was added first, then WO-4b (`gpt-6-luna` high, try 2, one narrow correction, effort one level up): fixed. Ladder: both tries on rung 1 used, no climb needed.
Proof on `5d7dd4f`: `PASS uv run pytest -q exit=0` **115 passed** (`s12-cleanup-pytest.log`; baseline 99 + 16 trends tests); `PASS uvx ruff check nflpi tests migrations exit=0` (`s12-cleanup-ruff.log`); hand count 12 of 12 MATCH again (`s12-handcount.log`); `lane-guard.py check ... trends 9d41cb0`: `OK`.
Remaining, classified: `_home_side` is about 50 lines of plain branches (accepted: one branch per record kind); kind names are repeated as strings (accepted, no abstraction for six names).
