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

Red: `s8a-red.log`, `ModuleNotFoundError: No module named 'nflpi.analytics.stars'` at collection. Right reason: the module does not exist. One collection error, so none of the 19 cases could run; they were not shown failing one by one. The cases were written together by the coordinator (the builder never writes its own bar), not one per build slice.

### Spec amendments after the freeze
* **Seam line (integrator's grant, 2026-10-13, option a):** `backend/tests/test_hardening.py` pinned the migration list to `0001, 0002`. The integrator granted one line in lane stars so the list reads `0001, 0002, 0003` (commit `808cfac`, recorded in `lanes.md`). Nothing else in that file changed.
* **From review round 1 (section 3), each with a failing case written by the coordinator first (`s8a-red-2.log`: 16 failed, 15 passed):**

| # | Criterion | Layer |
|---|---|---|
| S19 | The parsers reject: a week outside 1 to 22, a blank or over-long club code, a blank snap-file player id, the same player, week and club twice, a stat over 1,000, a snap count over 300. An echoed bad value is cut to 40 characters | operational |
| S20 | The run fails, with the old stars kept, when the snap rows, the stat rows or the id map are empty; when the two files end in different weeks; when the new list ends before the stored one; when it has fewer clubs in its last week than are stored. A parse error names its file | operational |
| S21 | A snap player missing from the id file is joined to the one stats player with the same club and exact name, so he is one star with both his snaps and his production (S6 otherwise unchanged) | functional |
| S22 | A quarterback with no offence snaps and no pass attempts is not a star (S14 applied to the `qb` slot) | functional |
| S23 | `stars_out` also returns `reports_seen`: how many players have a report for this game's week and clubs. Zero means the week is not reported yet, so an empty `out` means "not known", not "nobody is out" | user-facing |

## 3. IMPLEMENTATION
Provider: Codex, every production line. The coordinator wrote the tests, the hand-count script, the real-data check and this log, read each diff (`git status`, `git diff`, untracked files) and reran every proof itself.

| Work order | Rung | Decision | Result | Commit |
|---|---|---|---|---|
| WO-1 table, migration, parsers, ranking, `ingest_stars`, `stars_out` | `gpt-6-sol` medium, try 1 | `JEV: model:stars:wo-1 -> sol 0.97, medium 0.91` | 19 of 19; in scope (5 files); stopped correctly at the seam test instead of editing it | `1ccdfaf` |
| WO-2 review round 1 fixes | `gpt-6-sol` high, try 1 | `JEV: model:stars:wo-2 -> sol 0.59, high 0.64 (unsure)`; taken without an advisor call: same rung as WO-1's sure answer, and the effort table puts a bug fix with edge cases at high | 31 of 31; in scope (3 files); added one guard nobody ordered (removed in CLEANUP) | `09e9c66` |

CLIMBS: none. STRIKES: none. Codex could reach the lane's own test database, so its runs were real; each was rerun by the coordinator.

Proof: `gate.sh wo1`: `FAIL pytest exit=1` 133 passed, 1 failed, the one failure being the seam line above (`wo1-pytest.log`); ruff, alembic, genapi PASS. After the grant and WO-2, `gate.sh wo2`: `PASS pytest exit=0` 146 passed; `PASS ruff`; `PASS alembic` (up, check, down to base, up, check); `PASS genapi` no drift.

**S16, real data (`s8a-realcheck.py`, `s8a-realcheck-wo1.log`, again after each later build):** the full 2025 and 2026 files are loaded into a throwaway database through `ingest_stars` (3,520 and 800 rows); the app's stars are compared row by row with `s8a-handcount.py`. 2026 week 6, eight clubs: MATCH 40 of 40. 2025 week 19 (the whole regular season), eight clubs: MATCH 40 of 40. Then the real schedule and injury files are loaded and `stars_out` is asked about all 15 week 5 games of 2026: 9 stars out or doubtful, equal to a direct read of the injury file (9). Section 5 lists the names.

Review fan-out (standard tier; full reports in `~/.claude/plans/nfl-pickem-lanes-reviews/s8a-r1-*.md`):
* `ecc:code-reviewer` on `696c64f..1ccdfaf`: APPROVE WITH CHANGES, no CRITICAL or HIGH. MEDIUM: an unmapped snap player ranked as two people (S6; fixed, S21); one constant used for three weights (CLEANUP); a quarterback with no playing time stored as a star (S14; fixed, S22).
* `ecc:silent-failure-hunter` on the same range: five HIGH. Fixed with a failing case first: no report yet for the week reads as "nobody is out" (S23); a shorter or cut file replaces a good season (S20); one of three files empty still gives an ok run (S20); the split player (S21). Not built: `checked_at` is not per season and an empty injury file still logs ok; that is `ingest_injuries`, older code outside this step, and `reports_seen` now shows an empty week. Carried to 8a2.
* Security: Dwight (`dwight-mv5mkpow`, with `ecc:security-reviewer` and `ecc:silent-failure-hunter`) on `1ccdfaf`: **PASS**, no CRITICAL or HIGH. His three MEDIUM (unbounded week, a short snap file replacing the season, the split player) and three of his LOW (value bounds, club length, echoed file text) are fixed in WO-2 (S19 to S21). Clean: ORM with bound parameters only, a failed run keeps old data, fixed download paths, migration matches the model, no secrets, no route. A confirmation of the delta was requested (section 5).
* Accepted and carried, not built (reasons in the triage file): name spelling differences for a star with no league id; `stars_week` taken over both clubs; a stale list shows only as `stars_week` below `week`; `age_hours` counts from when the app first saw the status (the nflverse injury file has no report time; now stated in the `stars_out` docstring); control characters in names (strip when 8a2 sends names to the web or the AI); playoff weeks counted on purpose.
* Speed (reviewer L3, not measured by him): the whole real check, two seasons ranked and stored plus the schedule and injuries, runs in about 2 seconds.

## 4. CLEANUP
`/refactor` at coordinator level, scope-locked to the code this step added (`analytics/stars.py`, the `parse_star_*` code in `ingestion/nflverse.py`, `ingest_stars` in `ingestion/service.py`). The coordinator read the code after WO-2 and picked:
1. Name the weights for what they weigh: `SACK_POINTS`, `INTERCEPTION_POINTS` (the touchdown constant had been reused; numbers unchanged).
2. Replace the six-position tuple in `_rank_club` with a row helper.
3. Split `ingest_stars`: one helper parses a file and names it in the error (three try blocks became three calls); one helper checks the new list against the stored one.
4. Remove the row-count guard WO-2 added without an order: a stats correction can shorten a list by one row, which would have blocked every later run. The week and club guards (S20) stay.
5. Format the new code the way the rest of the repository is formatted.
`models.py` and the migration: no change needed (one table, one create and drop).

WO-3 (`gpt-6-luna` medium, try 1; `JEV: model:stars:wo-3-cleanup -> luna 0.49, medium 0.71 (unsure; the lowest rung taken)`): tests green and in scope, but the coordinator's read found a nine-parameter helper and `stars_out` over 50 lines. WO-3b (`gpt-6-luna` high, try 2, one narrow correction, effort one level up): `_rank_club` returns one club's rows and `rank_stars` adds the shared fields; `stars_out` split into `_star_report` and `_listed_star`. Both tries on rung 1 used, no climb needed. Checked against the base: the only earlier lines changed in the three files are two import lines in `service.py` (`delete` and `TeamStar` added); no added function is over 50 lines.

Proof on the cleanup tree (`gate.sh cleanup`): `PASS pytest exit=0` 146 passed; `PASS ruff`; `PASS alembic`; `PASS genapi` no drift. Real-data check again: MATCH 40 of 40, 40 of 40, 9 of 9 (`s8a-realcheck-cleanup.log`). `ruff format --check` on the three files: already formatted. Commit `231bd82`.

## 5. VERIFICATION
**Critic 1 (new `ecc:code-reviewer` subagent, no build transcript) on `4f754de`: FAIL.** Its own gate, twice (`critic1-*.log`, `critic2-*.log`): pytest 146 passed both runs, ruff, alembic, genapi all PASS. 22 of 23 criteria PASS. **S19 FAIL**: five of its eight input checks had no test (snap count over 300, over-long club code, blank snap-file player id, duplicate stat row, the 40-character cut); it proved this by changing the code on a scratch copy and seeing the tests stay green (38 changes, 14 survived). LOW: no test for the quarterback attempts tiebreak, a tie going to offence, a non-quarterback with no playing time, the safety and defensive-touchdown weights, age rounding, a stat that is not a number or is infinite. It also caught two wrong sentences in this log (both corrected above, in place). Lane guard and S18: clean. Report: `~/.claude/plans/nfl-pickem-lanes-reviews/s8a-critic-1.md`.

**Dwight on the delta `1ccdfaf..231bd82`: PASS on security**, no CRITICAL or HIGH; his F1 to F6 confirmed fixed. Two new MEDIUM, "none blocks landing, fix before 8a2 wires the worker": N1 a file with the same last week but rows missing inside it was still accepted (and CLEANUP had removed the row-count guard that caught it); N2 a stats column that is all "NA" was ranked as zeros. Report: `s8a-r2-dwight-delta.md`.

**Mapped FAIL routed back to tests, then the build.** The coordinator wrote the missing cases first (`s8a-red-3.log`: 37 failed, 5 passed; most fail because the hand-made club-total row now has a blank club, Dwight's N4), taking N1, N2, N4 and N6 in the same round:

| # | Criterion | Layer |
|---|---|---|
| S24 | Every (week, club) pair in the snap rows is in the stat rows and the other way round, or the run fails naming the missing pair. On the real 2025 and 2026 files the two sets are equal (570 and 156 pairs). Replaces "the two files end in different weeks" in S20 | operational |
| S25 | A stat column that is blank or "NA" in every row of the season fails the run | operational |
| S26 | A stats row with no player id is skipped before anything else in it is read; a short CSV row still gives an error that names the file | operational |

WO-4 (`gpt-6-sol` medium, try 1; `JEV: model:stars:wo-4 -> sol 0.37 (unsure; the lean taken)`): 42 of 42 star cases, in scope (2 files, about 25 lines), commit `9e1b51c`. New cases also pin every S19 clause and the rule edges the critic listed (`test_tiebreaks_and_the_rarer_weights`, ten more bad-file cases, age rounding). `gate.sh wo4`: `PASS pytest exit=0` 157 passed; ruff, alembic, genapi PASS. Real-data check again: MATCH 40 of 40, 40 of 40, 9 of 9 (`s8a-realcheck-wo4.log`).
CLEANUP after WO-4 (`/refactor`, scope-locked to its two hunks): no change needed. The diff is one moved line, one set and a short loop in `parse_star_stats`, a 9-line helper `_check_star_file_pairs` and two exception types; formatted, no function over 50 lines, nothing duplicated.

**S16, names a fan expects (full real files, app equal to the independent count on all 80 rows):**

| Club, 2025 whole season | Quarterback | Offence | Defence |
|---|---|---|---|
| Philadelphia | Jalen Hurts | Saquon Barkley, A.J. Brown | Zack Baun, Jalyx Hunt |
| Pittsburgh | Aaron Rodgers | Jaylen Warren, Kenneth Gainwell | T.J. Watt, Alex Highsmith |
| Detroit | Jared Goff | Jahmyr Gibbs, Amon-Ra St. Brown | Aidan Hutchinson, Jack Campbell |
| Kansas City | Patrick Mahomes | Travis Kelce, Kareem Hunt | Nick Bolton, Chamarri Conner |
| Cleveland | Shedeur Sanders | Harold Fannin, Quinshon Judkins | Myles Garrett, Carson Schwesinger |

2026 after five weeks (the list the app would use this week): Kansas City: Patrick Mahomes; Kenneth Walker III, Travis Kelce; George Karlaftis III, Nick Bolton. Buffalo: Josh Allen; James Cook, Dalton Kincaid; Gregory Rousseau, Deone Walker. Detroit: Jared Goff; Jahmyr Gibbs, Amon-Ra St. Brown; Aidan Hutchinson, Derrick Barnes.
Coordinator's read: the quarterbacks and offence are the names a fan would say first. Defence finds the pass rushers (Watt, Garrett, Hutchinson, Crosby, Bonitto, Hunter and Anderson in the wider log) but misses some big names with few countable plays: Chris Jones was fourth for Kansas City in 2025, D.K. Metcalf third on Pittsburgh's offence. Two things an owner may trip on, both the cost of "season totals" (section 2): Cleveland's 2025 quarterback is Shedeur Sanders (most snaps over the season), and Washington's 2026 quarterback star is Marcus Mariota, because he has played more snaps so far than the usual starter. D21's revisit trigger covers it.
**Who's out, 2026 week 5, all 15 games (app equal to a direct read of the injury file, 9 of 9):** Lamar Jackson, Baker Mayfield and Marcus Mariota (quarterbacks), Stefon Diggs, DeVonta Smith, Breece Hall, Kyle Monangai (offence), Mason Graham, Amani Hooker (defence).

**Dwight on `231bd82..9e1b51c`: PASS on security**, no CRITICAL, HIGH or MEDIUM; N1, N2, N4 and N6 confirmed fixed. Four LOW, none blocking, carried (see the list at the end of this section). Report: `s8a-r3-dwight-930bc4.md`.

**Coordinator's gate on `e28a2ea`, twice (`final3-*.log`, `final4-*.log`):** pytest 157 passed, ruff PASS, alembic PASS (up, check, down to base, up, check), genapi no drift, both runs.

**Critic 2 (a new `ecc:code-reviewer` subagent, no build transcript) on `e28a2ea`: FAIL, on tests only.** Its own gate, twice (`critic3-*.log`, `critic4-*.log`): pytest 157 passed both runs, ruff, alembic, genapi PASS. It found the code right on all 26 criteria and no false sentence in this log, and re-did six hand counts. It changed the code 24 ways on a scratch copy; these stayed green, so three clauses had no test that could fail:
- S11: the order inside a club (quarterback, offence, defence, then rank). Every earlier case had one listed star per club.
- S24: the "other way round" half (a pair in the stats file that the snap file lacks).
- S26: a short CSV row naming its file.
- Not blocking: S21 two stats players with one name at one club, S25 a column blank in every row (only "NA" was tested), S22 a quarterback with attempts and no snap row, the 64-character name cut, and the gate not looking for skipped tests.

**Routed back to tests. No production code changed, so no work order and no Codex run.** The coordinator added six cases (42 to 48 in `test_stars.py`): `club_missing_from_snaps`, `stat_column_all_blank`, `short_stat_row`, `short_snap_row` (each asserts the text the error must carry, and `club_missing_from_one_file` now asserts its pair too), `test_stars_out_orders_a_club_by_slot_then_rank`, `test_same_name_twins_are_not_joined_and_a_quarterback_needs_no_snap_row`. They pass at once because the code was already right, so a red run cannot be the proof. The proof is `s8a-mutate.py`: it copies `nflpi` and `tests` outside the repository, makes one wrong change at a time and runs the star tests. `s8a-mutations.log`: control 48 passed; 9 wrong changes, 9 caught, 0 survived (slot order reversed, rank dropped from the sort, the stats-over-snaps branch switched off, `AttributeError` no longer wrapped, any name match joined, only "NA" counted as blank, a quarterback needing snaps, the name cut removed in each file).
Two notes on those cases. The order case writes the five stars out of order and switches off index reads for its one query, because the database otherwise hands the rows back in key order and the function's own sort is never tested. `TypeError` in `_parse_star_file` has no case: nothing the CSV reader can produce reaches it (the number helpers already turn it into a `ValueError`); it stays as a guard.
`gate.sh` now fails the pytest step when the output mentions a skipped test.
