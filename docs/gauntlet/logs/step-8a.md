# Step 8a of 14: Star players and who is out (backend data only)

Session: owner's Mac, 2026-10-12 (evening, US Eastern), lane `stars` (worktree `.claude/worktrees/lane-stars`, branch `lane/stars`, base `main@696c64f`), run beside lane `alerts` (step 7).
Coordinator: Claude (hive temp "Oscar", dispatched by the integrator). Builder: Codex. Lane claim `claims/stars`, coord task #4.
Evidence folder: `docs/gauntlet/logs/step-8a-evidence/` (every log named below lives there).

## 1. PLANNING
* **In the owner's words (D21, D22, D27):** "A star is decided automatically from this season's playing time and production, re-ranked weekly"; per club "the QB + top 2 on offense + top 2 on defense"; on the game row "a short who's out line, stars only, with its age". This step builds the list of five stars per club for every week and one question the app can ask: "for this game, which stars are out or doubtful, and how old is that report?". It replaces nothing. It is not: a screen, an API route, an alert, a change to any pick, or a news source. Those are steps 8a2, 8b and 8i.
* **Roadmap row:** PLAN.md row 8, sub-step 8a ("stars (5 per team) and who's out from nflverse"; gate: ingestion tests with recorded fixtures, three clubs hand-checked).
* **Tier:** T2. Reversibility: two-way (one new table with a clean downgrade, one new module, one new ingestion function; nothing existing changes shape).
* **Decisions relied on:** D21 (automatic, this season, weekly, no award lists), D22 (five per club), D23 and D27 (out or doubtful, with age), D24 and `CLAUDE.md` (a star being out never moves a pick until it wins walk-forward: that test is step 8b), D51 (free sources only), dispatch: linemen ranked by snaps, accepted that they rarely qualify.
* **Scope, and what is cut:** `backend/nflpi/models.py` (`TeamStar`), `backend/migrations/versions/0003_team_stars.py`, `backend/nflpi/ingestion/nflverse.py` and `service.py` (`ingest_stars`), `backend/nflpi/analytics/stars.py` (`stars_out`), `backend/tests/test_stars.py`, `backend/tests/fixtures/stars/`. Cut and carried: API routes and schemas, the worker loop in `jobs.py`, the freshness list, `apps/web`, `packages/shared` (step 8a2, after step 7); alerts (8i); the star-out model challenger (8b); ESPN (D26); injured reserve, suspension, trade and game-day inactive triggers of D23 (not in the nflverse injury file); Questionable (D23 lists it for alerts, not for the "who's out" line).
* **Pre-flight:** Problem: the owner cannot see at a glance that a club's best players are missing this week. Why now: the injury list already exists per game, but it lists everyone and does not say who matters. Scope: as above. Success signal: for every upcoming game the backend can name the stars who are out or doubtful, with the report's age; no number, the app has one user and no usage tracking. Reversibility: two-way.
* **Checked at the source (nflverse release files, 2026-10-12; the research notes could not verify these):**

| Question | Found |
|---|---|
| Do the files update during the season? | Yes. `snap_counts_2026.csv` (weeks 1 to 5, changed today), `stats_player_week_2026.csv` (weeks 1 to 5, changed today), `injuries_2026.csv` (changed today) |
| How far back do snap counts go? | 2013. `snap_counts_2012.csv` exists but holds only the header; 2011 is not there. Step 8b can test 2013 to 2025, not 2012 |
| Player stats | `stats_player/stats_player_week_<season>.csv` (offence and defence in one file, back to 2012). The older `player_stats/` path answers 404 for 2026 |
| Which id does each file use? | Snap counts use the Pro Football Reference id; stats and injuries use the league (gsis) id. `players/players.csv` maps one to the other: 1,807 of 1,810 players in the 2026 snap file map |
| Club codes | Current codes in 2026. The 2013 snap file still has `OAK`, `SD`, `STL`: the app's existing `franchise()` map is applied |
| Depth charts | `depth_charts_2026.csv` is 61 MB of daily snapshots. Not used: snaps and stats answer D21 |
| Odd rows | Five stats rows have no player id or name (club totals): skipped. No duplicate player-week rows. Longest name 24 characters, ids 10 |

* **Assumptions:** `validated` the three files above carry what the rule needs (table); `validated` `injury_reports` keeps one row per status change with `observed_at`, so the newest row per player is his current status (`service.ingest_injuries`, `views._week_injuries`); `validated` conftest builds tables from the models, so tests see the new table without the migration, and the gate runs the migration on its own empty database; `assumed` a club's stars for week W should use only weeks before W, so the list is a pre-game input that step 8b can test without looking ahead; `unknown, does not change the design` whether the owner will find the defence list right: an automatic rule favours players with countable plays (D21's own revisit trigger covers it).
* **Interpretations sent to the decision desk:** `JEV: design:stars:basis -> season_totals (0.92)` over per-game average; `JEV: design:stars:basis week_one -> no_stars_yet (0.91)` over filling week 1 from last season. Both followed. Both two-way; revisit trigger: the owner wants a star who missed weeks to stay on the list, or wants a list in week 1.
* **Instrumentation:** every run is a row in `ingestion_runs` (`dataset = stars`, row count or the real error). PROCEEDING WITHOUT a usage metric: single-user app, no analytics. Nothing runs it on a schedule until step 8a2 wires the worker.
* **Skills:** `/jevgrep`: `s8a-jg-injury-seam.log` ranked `api/views.py` (`_week_injuries`, newest row per player), `models.py`, `ai/research.py`, `ingestion/service.py`; it showed the newest-row rule to follow and no star code to reuse. `/graft`: N/A (file homes fixed by the lane map). `tdd`: no project tdd skill; the coordinator wrote the failing tests before any production code. `ponytail`: in every work order. Design Gauntlet: N/A (no screen). `harness-engineering`: N/A (ordinary feature code). Parallel Lanes: claim made, lane-guard at the end.
* **Tools:** `JEVGREP: ready` (`jg` 0.8.0, doctor exit 0). `HEADROOM: not-routed` (doctor exit 2; not a blocker). Codex: `codex-cli 0.156.1`.
* **Test database:** own container `nflpi-lane-stars-db` on `127.0.0.1:15438`, no volume. The live stack on 5432 and 8000 is never used. `gate.sh` sets `DATABASE_URL` itself.
* **Baseline at `696c64f`** (`bash gate.sh baseline`): `PASS pytest exit=0` 115 passed; `PASS ruff exit=0`; `PASS alembic exit=0` (up to head, check, down to base, up, check on an empty database); `PASS genapi exit=0` no drift. Logs `baseline-*.log`.
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low (Codex builds); VERIFICATION high.

## 2. SPECIFICATION
Public seam (three names, nothing else is pinned by the tests):
* `nflpi.models.TeamStar`: table `team_stars`, key `(season, week, team, slot, rank)`; `slot` is `qb`, `off` or `def`; columns `player_id` (league id, may be null), `player`, `position`, `snaps`, `production`, `score`, `source`, `computed_at`.
* `nflpi.ingestion.service.ingest_stars(session, season, snaps=None, stats=None, players=None) -> IngestionRun`: downloads the three files when rows are not passed, ranks, replaces that season's rows in one transaction, logged like every other ingestion.
* `nflpi.analytics.stars.stars_out(session, game_id, now=None) -> dict` with keys `game_id, season, week, stars_week, checked_at, out`.

Gate: `backend/tests/test_stars.py` (19 cases; hand-made rows counted by hand in the comments, plus recorded real files), then `bash docs/gauntlet/logs/step-8a-evidence/gate.sh <label>`: full pytest, ruff, the migration up, down and up again with `alembic check`, and `npm run gen:api` with no drift. Last, the stars of three clubs on the full real files against an independent count and against names a fan expects.

| # | Criterion | Layer |
|---|---|---|
| S1 | The `qb` star is the club's quarterback with the most offence snaps so far this season (then most pass attempts, then name). Stored: snaps, production = pass attempts, score = snaps | functional |
| S2 | The two `off` stars are the non-quarterbacks with the highest offence score = 0.1 x offence snaps + (rushing + receiving yards) / 10 + 6 x (rushing + receiving touchdowns) + 0.5 x receptions. A lineman has snaps only, so he makes the list only when fewer than two others outscore him | functional |
| S3 | The two `def` stars have the highest defence score = 0.05 x defence snaps + solo tackles + tackles with assist + 0.5 x assists + 6 x sacks + 2 x QB hits + 2 x tackles for loss + 6 x interceptions + 3 x passes defended + 4 x forced fumbles + 6 x defensive touchdowns + 2 x safeties | functional |
| S4 | Stars for week W use only weeks before W of the same season. Lists exist for week 2 up to the week after the last week in the files; none for week 1. Rows of another season in a file are ignored | functional |
| S5 | A player counts for a club only if his latest game before W was with that club, and only his numbers with that club count | functional |
| S6 | Snap rows join stats rows through `players.csv` (Pro Football Reference id to league id). A player with no mapping is still ranked, with `player_id` null. Stats rows with no player id are skipped | functional |
| S7 | Old club codes are mapped with the existing `franchise()` | functional |
| S8 | A rerun replaces the season's rows and leaves other seasons alone | functional |
| S9 | A failed download, a missing column, a value that is not a number, a negative snap count, an id that does not fit, or a ranking that comes out empty fails the run: logged in `ingestion_runs` with the real error, old stars kept | operational |
| S10 | `stars_out` lists a star when the newest injury row for him in the game's season, week and club says Out or Doubtful. Not Questionable, not a practice note, not another week, not a player off the list | functional |
| S11 | Each listed star carries `team, player, player_id, position, slot, rank, status, injury, observed_at, age_hours, source`; `age_hours` = now minus `observed_at`. `checked_at` is the last good injury refresh, or null if there was none. Away club first, then home; quarterback, offence, defence | user-facing |
| S12 | A star and a report match by league id when both have one, else by exact name in the same club | functional |
| S13 | `stars_out` uses the list for the game's week, or the newest earlier list of that season, and says which in `stars_week`. No list: `stars_week` null and `out` empty. A later list is never used. An unknown game raises `LookupError` | functional |
| S14 | A player holds one slot: the side where his score is higher (offence on a tie); a player with no snaps and no production is not ranked. Ties in a list go to the name first in A to Z order | functional |
| S15 | On the recorded 2026 files (KC, BUF, DET, weeks 1 to 5) the app's fifteen stars for week 6 equal `s8a-handcount.py`, an independent count that shares no code with the app | functional |
| S16 | On the full real files the stars of three clubs equal the independent count and read as names a fan expects; recorded in section 5 | user-facing |
| S17 | The migration creates `team_stars` and its downgrade removes it; the models and the migrated database agree (`alembic check`) | operational |
| S18 | Nothing outside the lane's files changes: no route, no schema, no worker job, no prediction | functional |

Decisions (each two-way):
* **The weights** are the coordinator's, set by reading real lists before the build (2025 full season and 2026 so far): offence is fantasy-style scoring plus 0.1 a snap; defence weighs sacks, hits, tackles for loss, interceptions and passes defended above plain tackles, plus 0.05 a snap. With tackles weighted the same as big plays the 2025 lists missed T.J. Watt, Nik Bonitto and Myles Garrett's team-mates in favour of every-down tacklers; with these weights they lead their clubs. Revisit trigger (D21): the list misses a name the owner considers obvious.
* **Season totals, not per-game average** (decision desk, 0.92). Cost: a star who misses several weeks slides down the list as others pile up numbers.
* **No list before a club's first game** (decision desk, 0.91). Cost: the "who's out" line is empty in week 1.
* **Store the stars, not the raw files.** One table. Step 8b can rebuild any past season by running the same function on that season's files.
* **Not added to the freshness list** in `service.STALE_HOURS`: nothing runs this job until step 8a2 wires the worker, so it would show "stale" in the app for no reason. Carried to 8a2.
* `JEV: model:stars:wo-1 -> sol (0.97), effort medium (0.91)`. BUILD_RUNG: gpt-6-sol medium (try 1 of 2). Reason: one table, one migration, three parsers, a ranking with a join across two id systems, one query; nineteen hand-counted cases check it.

Red: `s8a-red.log`, `ModuleNotFoundError: No module named 'nflpi.analytics.stars'` at collection. Right reason: the module does not exist. The cases were written together by the coordinator (the builder never writes its own bar), not one per build slice.
