# Step 16a of 17: Group picks, backend (tables, checked CSV import, two questions)

Session: owner's Mac, 2026-10-12 (night, US Eastern; 2026-10-13 UTC), lane `group` (worktree `.claude/worktrees/lane-group`, branch `lane/group`, base `main@d88d74e`), wave 4, run beside lanes alerts, news, model, coaches, sdk and scores.
Coordinator: Claude (hive temp "Phyllis", dispatched by the integrator). Builder: Codex. Lane claim `claims/group`, coord task #12.
Evidence folder: `docs/gauntlet/logs/step-16a-evidence/` (every log named below lives there unless a full path is given).
No real member name appears in this file, the tests, the fixtures or any log in this repository. The real files stay outside it.

## 1. PLANNING
* **In the owner's words (D56):** "his Yahoo group's picks and confidence points come into the app"; "he reads the group in his own signed-in browser and supplies files"; "group scoring is straight winners and confidence points only". This step builds the place those files land: two tables, one import that checks every cell before it stores anything, and two questions the app can ask ("how did the group split on this game?" and "what are the standings for this week?"). It replaces nothing. It is not: an upload button, an API route, a Group screen, or anything that changes a pick or the model. Those are the next parts of step 16 (wave 5).
* **Roadmap row:** PLAN.md row 16 (D56), backend half only (lanes.md, lane group).
* **Tier:** T3 (new tables, untrusted file input). One-way doors: none. Two new tables with a clean downgrade and one new package; nothing existing changes shape. Reversibility: two-way.
* **Decisions relied on:** D56 (files from the owner's browser, no scraping, straight winners + confidence points, spread is context); `CLAUDE.md` data rules (never invent data, missing stays missing); research plan `yahoo-group-plan.md` rows Y3 (table shape, nothing but week, game, member, pick, points), Y6 (untrusted input: names capped and control characters stripped, a pick must match the game's two teams), Y7 (use comes later and never changes the recommendation); lanes.md wave 4 seam grants (append models, one migration-list line, migration number 0005).
* **Scope, and what is cut:** `backend/nflpi/group/` (`importer.py`, `queries.py`), `backend/migrations/versions/0004_group_picks.py`, `backend/tests/test_group.py`, `backend/tests/fixtures/group/`, plus the two granted seams: two model classes appended to `backend/nflpi/models.py`, one line in `backend/tests/test_hardening.py`. Cut and carried to wave 5: the upload route and its auth, schemas, the Group screen, shares in the report or the evidence pack, a run log row per import, any scoring by the app itself.
* **Pre-flight:** Problem: the owner cannot see in the app how his 32-member group picked or where he stands. Why now: he supplied weeks 1 to 5 on 2026-10-13 and each week adds a file. Scope: as above. Success signal: his two real files import with zero refused rows and the stored totals equal his weekly file for all 160 member-weeks (hand check, section 5); no usage number, the app has one user. Reversibility: two-way.
* **What the two real files look like (read outside the repository, 2026-10-13):**

| Fact | Picks file | Weekly points file |
|---|---|---|
| Header | `Week,Team,Game,Favored,Spread,Underdog,Pick,Side,Confidence,Week_Total_Pts` | `Rank,Team,Wk1,...,Wk5,Total_Pts` |
| Rows | 2,528 (32 members x 16, 16, 16, 16, 15 games), every row 10 cells, CRLF, no byte order mark, 117 KB | 32, every row 8 cells, 1 KB |
| Member | column `Team` (a nickname, longest 23 characters, a few with `'`, `!`, `)` or a curly quote) | same 32 names |
| Game | `Week` + `Favored` + `Underdog`; codes are Yahoo's, mixed case (`Sea`, `Jax`, `LAR`, `NE`), 32 codes | none |
| Pick | `Pick` is the favored or the underdog code and `Side` says which (0 mismatches); 82 rows have no pick: `Pick` empty, `Side` `none`, `Confidence` empty | none |
| Points | `Confidence` 1 to 16, never repeated by a member inside a week; `Week_Total_Pts` the same on every row of a member-week | each week 0 or more; `Total_Pts` equals the sum of the weeks on all 32 rows |
| Agreement | `Week_Total_Pts` equals the weekly file's cell for all 160 member-weeks | `Rank` is 1 to 32 with no repeats although four totals tie: Yahoo breaks ties by a rule the file does not state |

* **Assumptions:** `validated` the two shapes above; `validated` upper-casing a Yahoo code and applying the app's existing `franchise()` map (`LAR` to `LA`) gives the app's code for all 32 (the app uses nflverse codes); `validated` conftest builds tables from the models, so tests see the new tables without the migration, and the gate runs the migration on its own empty database; `validated` the picks file carries no season, so the caller passes it; `assumed` Yahoo only shows other members' picks after a game locks (help page quoted in the research plan), so every imported pick is a locked pick and no kickoff check is needed here; `assumed` a blank weekly cell does not occur (none in the real file): it is refused, and the rule is revisited if Yahoo ever shows one; `unknown, does not change the design` how Yahoo breaks rank ties.
* **Interpretations sent to the decision desk** (`decide.sh`, topic `design:group:import`, all followed, all two-way):
  * `JEV: bad_row -> refuse_whole_file (0.80)` over skipping bad rows. Value: a share or a total is never computed from half a file. Cost: one bad row blocks a week until the file is fixed. Risk: the owner, a minute of his time. Revisit trigger: a real export that fails for a reason he cannot fix.
  * `JEV: rank -> store_on_last_week_only (1.00)` over computing a rank from points. Value: only Yahoo's own rank is ever shown. Cost: earlier weeks have no rank unless a file ending in that week was imported. Revisit trigger: the owner wants a rank for every past week.
  * `JEV: no_pick -> store_row_with_empty_pick (0.88)` over dropping the row. Value: "3 of 4 picked" stays visible. Revisit trigger: none.
* **Migration number:** built as 0005 on `down_revision = "0003"` because 0004 (lane news) was not on this branch. Ruling by the integrator (2026-10-13): main still has no 0004 at landing time, so the file is renamed `0004_group_picks.py` (revision "0004", down revision "0003") and the migration-list line reads `0001, 0002, 0003, 0004` (commit `252add5`). If news lands first, the integrator re-points one line in each file.
* **Instrumentation:** PROCEEDING WITHOUT a metric: single-user app, no analytics. The import returns the kind of file and the row count and raises a line-numbered error; the wave 5 upload route records each import where the owner can see it.
* **Skills:** `/jevgrep`: `~/.claude/plans/nfl-pickem-lanes-logs/s16a-jg-csv-import.log` ranked 2 files; it pinned the owner's own pick import in `api/main.py` (`import_picks`: skips bad rows, no size cap), which this step does not reuse because the group file is all-or-nothing, and `franchise()` in `ingestion/nflverse.py`, which it does reuse. `/graft`: N/A (file homes fixed by the lane map). `tdd`: no project tdd skill; the coordinator wrote the failing tests before any production code. `ponytail`: in every work order. `jev`: loaded before the first decision call. Design Gauntlet: N/A (no screen). `harness-engineering`: N/A (ordinary feature code). Parallel Lanes: claim made, `lane-guard check` at the end.
* **Tools:** `JEVGREP: ready` (`jg` 0.8.0, doctor exit 0). `HEADROOM: not-routed` (doctor exit 2; not a blocker). Codex: `codex-cli 0.156.1`.
* **Test database:** own container `nflpi-lane-group-db` on `127.0.0.1:15445`, no volume. The live stack on 5432 and 8000 is never used. `gate.sh` sets `DATABASE_URL` itself.
* **Baseline at `d88d74e`** (`bash gate.sh baseline`): `PASS pytest exit=0` 172 passed in 30 min 8 s (six lanes share the machine; load average 46); `PASS alembic exit=0`; `PASS genapi exit=0` no drift; `FAIL ruff exit=1`, 1 error, and it is this lane's own new file, not the base: ruff could not yet see the package `nflpi.group`, so it sorted the test file's imports as third-party (I001). It passes once the package exists (section 3). Logs `baseline-*.log`.
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low (Codex builds); VERIFICATION high.

## 2. SPECIFICATION
Public seam (nothing else is pinned by the tests):
* `nflpi.models.GroupPick`: table `group_picks`, key `(game_id, member)`; `game_id` is a foreign key to `games`; columns `picked_team` (may be null), `confidence` (may be null), `imported_at`. Nothing else.
* `nflpi.models.GroupStanding`: table `group_standings`, key `(season, week, member)`; columns `points`, `rank` (may be null), `imported_at`. Nothing else.
* `nflpi.group.importer.import_group_csv(session, season: int, data: bytes) -> ImportResult(kind, rows)`: `kind` is `"picks"` or `"standings"`, chosen from the header; raises `GroupImportError` (a `ValueError`); commits on success. `MAX_BYTES = 1_000_000` is a module constant read at call time.
* `nflpi.group.queries.game_shares(session, game_id) -> dict` and `nflpi.group.queries.standings(session, season, week) -> list[dict]`.

Gate: `backend/tests/test_group.py`, then `bash docs/gauntlet/logs/step-16a-evidence/gate.sh <label>`: full pytest (a skipped test fails the gate), ruff on `nflpi tests migrations`, the migrations up, down and up again with `alembic check` on an empty database, and `npm run gen:api` with no drift. Last, the hand check: the owner's two real files imported into the lane's test database and compared with an independent count (section 5).

Order of checks inside a file: size, text encoding, header, then row by row: number of cells, then each cell's own form and bounds (and the name), then the matchup, then pick, side and confidence, then "this game twice", then "confidence repeated". The first problem found is the one reported. Row numbers count the header as line 1.

| # | Criterion (frozen) | Layer |
|---|---|---|
| P1 | A picks file stores one row per member and game: the game's `game_id`, the member, the picked team as the app's code, the confidence number. The result says `picks` and the number of rows | functional |
| P2 | `Favored`, `Underdog` and `Pick` codes are read in any letter case and mapped with the app's `franchise()` (`LAR` is `LA`) | functional |
| P3 | A row with `Side` `none`, an empty `Pick` and an empty `Confidence` is stored with pick and confidence missing (null) | functional |
| P4 | `Favored` and `Underdog` must be the two teams of exactly one game of the given season and that week; otherwise the file is refused ("no game"). Codes are not trimmed. Another season's games never match | functional |
| P5 | `Side` is exactly `Favorite`, `Underdog` or `none`. `Favorite` needs `Pick` = the favored team, `Underdog` needs `Pick` = the underdog, both need a confidence; `none` needs an empty pick and an empty confidence | functional |
| P6 | Bounds: `Week` 1 to 22, `Game` 1 to 16, `Confidence` 1 to 16, `Week_Total_Pts` 0 to 136, `Spread` one or two digits with at most one decimal digit (`0` to `99.9`) | functional |
| P7 | A whole number is plain ASCII digits only: no sign, decimal point, underscore, space, other script or empty cell | functional |
| P8 | A member has a game once in a file (after name cleaning); a second row is refused ("twice") | functional |
| P9 | A member uses each confidence number once per week in a file; a repeat is refused. Another week or another member may use the same number | functional |
| P10 | The group scores straight winners with confidence points: `Spread`, `Favored`, `Underdog`, `Side`, `Game` and `Week_Total_Pts` are checked and never stored, and swapping favored and underdog or changing the spread stores the same rows. Each table has exactly the columns in the seam | functional |
| N1 | A file larger than `MAX_BYTES` (1,000,000) is refused ("too large") before it is decoded; exactly `MAX_BYTES` is allowed | operational |
| N2 | Bytes that are not UTF-8 are refused ("UTF-8"); a leading byte order mark is accepted | operational |
| N3 | The header must be exactly the picks header, or exactly `Rank,Team,Wk1..WkN,Total_Pts` with the weeks in order from `Wk1`, N from 1 to 22. Anything else is refused ("columns") | functional |
| N4 | Every row has exactly as many cells as the header ("cells", with its line); a blank line is a bad row; a file with a header and no rows is refused ("no rows") | functional |
| N5 | Member names are cleaned before use: the name is put in Unicode form NFC (amended after review r1), then every character whose Unicode category starts with `C` (control, format, private use, surrogate, unassigned) is removed, then runs of white space become one space and the ends are trimmed. Any other text, markup included, is stored unchanged as plain text | functional |
| N6 | A name that is empty, or longer than 64 characters, after cleaning is refused ("name") | functional |
| N7 | Any refusal writes nothing: rows stored before stay as they were, and good rows earlier in the same file are not written | operational |
| N8 | A row error starts `line N: ` and names the column or the rule. No error contains a member name or any other text from a cell (amended after review r1: the first wording allowed 40 characters of a cell, and a name typed into another column would have been echoed). `GroupImportError` is a `ValueError` | operational |
| N9 | Importing the same file again leaves the same rows (idempotent) | functional |
| N10 | A corrected file updates the matching rows in place (a pick, a confidence, pick to no pick and back); rows not in the file are left alone. `imported_at` of every row a file writes is the time of that import (amended after review r1) | functional |
| N11 | A valid file of any size up to the cap is stored whole: the rows are written in batches, so the number of rows is not limited by one database statement (added after WO-1, red 2) | operational |
| N12 | A database failure is not a bad file: the import is rolled back and a `RuntimeError` that is not a `GroupImportError` is raised, naming only the kind of database error, with no chained cause (the database's own message lists stored values, which are member names). After any error at all the caller's session is not left inside a transaction (added after review r1) | operational |
| W1 | A weekly file stores one row per member and week with that week's points. `Rank` is stored on the rows of the file's last week only; earlier weeks get no rank from this file. The result says `standings` and the number of rows | functional |
| W2 | Weekly bounds: `Rank` 1 to 9999, each week 0 to 136, `Total_Pts` plain digits and equal to the sum of the weeks ("total"); a member appears once ("twice") | functional |
| W3 | A later file never clears a rank an earlier file gave a week: on a week that is not its last, it updates points and keeps the stored rank. On its own last week it sets the rank | functional |
| W4 | Seasons are kept apart: the season is the caller's and part of the key | functional |
| Q1 | `game_shares` returns `game_id`, `members` (rows stored for the game), `picked` (rows with a pick), and for `away` and `home`: `team`, `picks`, `share` = picks / picked, `avg_confidence` = the mean confidence of that side's picks | user-facing |
| Q2 | Missing is missing: `share` is null for both sides when nobody picked, and `avg_confidence` is null for a side with no picks. A game with no rows returns zero counts, not an error | user-facing |
| Q3 | `game_shares` for an unknown game raises `LookupError` | functional |
| Q4 | `standings(season, week)` returns one entry per member with a row that week: `member`, `points` (that week), `total` (the member's points in weeks up to and including it, that season only), `rank` (stored, or null). Order: total high to low, then rank low to high, then name A to Z ignoring letter case (amended after review r1). No rows gives an empty list | user-facing |
| H1 | Hand check: the owner's two real files import with no refusal; stored rows equal an independent count of the files (rows, picks per team per game, points per member-week); straight-winner scoring from real results equals the weekly file for every member-week; recorded in section 5 with made-up labels in place of names | user-facing |

Operational layer note: N1, N2, N7 and N8 are what an operator sees when an import goes wrong. A run-log row per import belongs to the upload route (wave 5) and is carried.

First failing tests: `backend/tests/test_group.py` (red at `ModuleNotFoundError: No module named 'nflpi.group'`, the intended reason: the seam does not exist yet). Log `red-pytest.log`.

## 3. IMPLEMENTATION
Provider: Codex (`codex-cli 0.156.1`), one bounded work order at a time, prompt on stdin, in this worktree only. Work orders: `~/.claude/plans/nfl-pickem-lanes/wo/group-wo-*.md`. Codex logs: `~/.claude/plans/nfl-pickem-lanes-logs/s16a-wo*-codex.log`. Codex cannot reach the lane database from its sandbox, so every proof below is the coordinator's own rerun. CLIMBS: none. STRIKES: none.

| Commit | What | Builder | Proof (coordinator's rerun) |
|---|---|---|---|
| `4a6a677` | Spec, fixtures, first failing tests | coordinator | red: `ModuleNotFoundError: No module named 'nflpi.group'` |
| `af18571` | WO-1: two models, migration 0004, `importer.py`, `queries.py`, the one migration-list line | `gpt-6-sol` xhigh, try 1 (`JEV: model:group:wo-1 -> sol 0.94, xhigh 0.93`) | `tests/test_group.py` 100 passed; diff read: only the allowed files |
| `49aab7c` | Red 2 (found by the coordinator reading the diff): a valid file of 16,000 rows fails, one INSERT over 65,535 values | coordinator | `red2-pytest.log`: 1 failed |
| `977c5d9` | Red 3: review round 1 as failing tests | coordinator | `red3-pytest.log`: 67 failed, 65 passed |
| `5ff61e0` | WO-2: batched upserts (N11), rollback and database failures (N12), no cell text in errors (N8), `imported_at` on update (N10), NFC (N5), name order ignoring case (Q4) | `gpt-6-sol` high, try 1 (`JEV: model:group:wo-2 -> sol 0.45, unsure`; `ADVISOR: sonnet -> sol, high`) | 132 passed; ruff clean |
| `54b10a8`, `37d861b` | Red 4 and WO-3: any error at all rolls the import's session back | `gpt-6-luna` medium, try 1 (`JEV: model:group:wo-3 -> luna 0.85`; effort unsure at 0.29, so the table's `low` was raised one level to Jev's leading answer, `medium`, with no advisor call for an effort level) | 133 passed; ruff clean |

**Review round 1** at `af18571` (read-only, tier large; reports with the coordinator's ruling on each finding in `~/.claude/plans/nfl-pickem-lanes-reviews/s16a-r1-*.md`):

| Reviewer | Verdict | Taken into WO-2 / WO-3 | Not taken, and why |
|---|---|---|---|
| `ecc:code-reviewer` | APPROVE, no CRITICAL or HIGH | `imported_at` not refreshed; session left in a transaction after a refusal; name order by letter case | line number counts rows, as section 2 says; dead code went to CLEANUP |
| `ecc:security-reviewer` | PASS | a database error kept as the cause would carry member names into a traceback; a name typed into another column was echoed (against N8); NFC | look-alike and invisible letters (carried); no member cap (the 1 MB cap bounds it) |
| `ecc:silent-failure-hunter` | 2 HIGH | a database outage was reported as a bad file; no rollback on other errors | rank kept across files and rows never deleted are by design (W3, N10); a member with no row in a week is dropped from that week (carried) |
| `ecc:python-reviewer` | 1 HIGH (migration 0004 points at 0003: known, planned, LANDING) | `imported_at`; narrow error handling | style-only items (ponytail: no extra helpers) |
| `ecc:pr-test-analyzer` | 10 clauses with no killing test | a test for each: two games in one week, weekly cell count, name in every error kind, unassigned code point, any white space, length after cleaning, the order of checks (16 two-fault cases), rank before no rank, weekly duplicate after cleaning, a quoted line break in a number | none |
| Dwight (hive security reviewer, required) | **PASS at `af18571`**, no CRITICAL, no HIGH; fix G1 and N11 before landing | G1 (cause carries names) and G2 (cell echo) fixed in WO-2, N11 fixed in WO-2, L1 `imported_at` | G3 case and look-alike names, G5 a re-import never deletes: carried; G4 migration number: LANDING; L2, L3: wave 5 route. Report: `/Users/emmanueladams/HarnessAgents/hive/agents/dwight-mv5mkpow/reports/2026-10-13-lane-group-16a-af18571.md`. Delta `af18571..HEAD` sent for confirmation: see section 5 |

Amended criteria (each marked in section 2): N5 (NFC), N8 (no cell text at all), N10 (`imported_at`), Q4 (ignore letter case); added: N11, N12. All were written as failing tests before the fix.

`lane-guard check` after IMPLEMENTATION: two lines, both the granted seams (`backend/nflpi/models.py`, `backend/tests/test_hardening.py`); nothing else.

## 4. CLEANUP
Explicit scope-locked `/refactor` pass (skill loaded; analysis by the coordinator, edits by Codex) on the two touched production files, after all review fixes. Behaviour had to stay identical.

| Smell | Ruling |
|---|---|
| `importer.py` `_number`: three identical `raise` lines and a three-step check | **Changed** (WO-4): one condition, one raise |
| `_pick_row` returned `confidence` twice; `_pick_rows(width)` was always `len(PICKS_HEADER)` | **Changed** (WO-4) |
| `favored == underdog or` could never decide (a one-team set never equals a game's two-team key) | **Removed** (WO-4), with a comment that `Game` and `Week_Total_Pts` are checked and never stored (P10) |
| `_csv_rows` header test is one long boolean; `_rows` is a manual loop; list vs tuple header; two passes per side in `game_shares` | **No change needed**: each works, is under 15 lines, and an extra helper would add code (ponytail) |
| Longest function `_pick_row`, 33 lines; file 216 lines; nesting 3 | **No change needed**: inside the limits |

Commit `8bac149` (WO-4, `gpt-6-luna` medium; try 2 at `high`). The coordinator's own work order was wrong on one point: it told Codex to return `int(cell)` where the code had `int(digits)`, and a cell of 5,000 zeros and a digit then raised Python's own digit-limit `ValueError`. Caught by reading the diff, pinned by a new test (`test_p7_leading_zeros_are_still_plain_digits_however_many`, red first), corrected by Codex in try 2. That is a spec fault, not a builder fault: no climb, no strike.
Proof after the edit: `tests/test_group.py` 134 passed; ruff clean.

## 5. VERIFICATION
Tested commit: `252add5` (last commit that changes code or tests; rebased on main `53b1c89`). Mutation pass and hand check below ran on `c04949c`, the same group code before the rebase and WO-5.
* **Mutation pass** (`s16a-mutate.py`, 124 single wrong changes, one per frozen clause or more): run 1 killed 120 (`mutate-1.log`); 1 survivor was an equivalent change, 3 were test gaps, closed with tests; rerun of the four: all killed (`mutate-2.log`).
* **Gate twice in a row on `c04949c`** (`final-gate-summary.log`, logs `final1-*.log`, `final2-*.log`): both runs `PASS pytest exit=0` 308 passed, `PASS ruff exit=0`, `PASS alembic exit=0` (up, check, down, up, check on an empty database), `PASS genapi exit=0` no drift.
* **Hand check H1 on `c04949c`** (`handcheck.log`, the owner's two real files, lane database `nflpi_hand`): 2,528 pick rows and 160 weekly rows stored, 0 different from an independent count; 82 no-pick rows stored as missing; `game_shares` equal an independent tally on 79 games; straight winners x confidence equals Yahoo's weekly points for all 160 member-weeks; `standings()` equals the file for 5 weeks x 32 members, week 5 in Yahoo's rank order; a second import changes nothing. **PASS.**
* **Names:** every file changed on this branch scanned for the 32 real member names: 0 hits.
* **Dwight (required security review):** PASS at `af18571`, then **PASS at `8bac149`** on the delta, no CRITICAL, HIGH or MEDIUM; nothing to fix before landing. `c04949c` adds tests and logs only. His open advice (carried): normalise names once more after the strip (L2), `hide_parameters=True` in `db.py` (seam), case and look-alike names (G3), a re-import never deletes (G5), wave 5 route items.
* **Gate twice in a row on `252add5`** (labels `w5a`, `w5b`): both `PASS pytest exit=0` 320 passed, `PASS ruff exit=0`, `PASS alembic exit=0` (No new upgrade operations detected), `PASS genapi exit=0` (no drift). The `c04949c` gate (308 passed) above predates the rebase.
* **WO-5** (`252add5`, `gpt-6-luna` medium, try 1; plan `wo/group-wo-5.md`): migration renamed `0004_group_picks.py` (revision "0004", down "0003"), migration list `0001..0004`, `hide_parameters=True` in `db.py` (granted seam, Dwight L1), test `test_database_errors_hide_bound_values`. Red without the argument (assertion error, marker in the message), green with it; the coordinator ran both, since Codex's sandbox cannot reach the database.
* **CRITIC 1 (fresh `ecc:code-reviewer`, HEAD `4a378d1`): PASS.** Gate on its own run: `PASS pytest exit=0` 320 passed, `PASS ruff exit=0`, `PASS alembic exit=0`, `PASS genapi exit=0` (logs `critic1-*.log`). It broke 12 clauses of its own: 10 killed, 1 equivalent change, 1 survivor (Q1: `avg_confidence` with a null-confidence pick row, which P5 stops the importer from producing). Removing `hide_parameters=True` fails the new test. Migration matches the models; no real names; only the granted seams outside the lane.
* **Carried (advisory):** (1) size, UTF-8 and header errors are raised before the importer's `try` (`importer.py` `import_group_csv`), so they do not roll back a session the caller already opened; the test helper rolls back first, so no test covers it. If the owner reads N12 as covering a caller's open transaction, this becomes a real finding. (2) Q1 with a null-confidence row is untested. (3) Dwight's G3 (look-alike and case-variant names) and G5 (a re-import never deletes rows). (4) One old hit of a member name in `docs/gauntlet/logs/step-2.md` on main, not this lane's file.
* **JEV job 4:** `JEV: passed -> 0.75 (unsure)`; `ADVISOR: sonnet passed? -> PASS` (all gates green, critic PASS, no open finding tied to a criterion; the early-error rollback is outside N12's wording). Decision line in `~/.claude/plans/nfl-pickem-lanes/decisions.jsonl` (topic `verify:group:16a`).
* **lane-guard check** (`group`, base `53b1c89`): 4 findings, all accepted: `0004_group_picks.py` is owned by no lane (the renamed migration; god's ruling a), `db.py` and `models.py` are seams granted to this lane (ruling b; models append), `test_hardening.py` is the one granted migration-list line.
* **Names:** every file in the repo scanned for the 32 real member names again after the rebase: 0 hits in this lane's files.
* **Result:** gate green twice on the code commit, critic PASS, Dwight PASS. Ready for the integrator.

## 6. LANDING
Pending the integrator: the lane does not push, open a PR or merge. If lane news lands first with its own 0004, re-point this migration to the next number and the one list line in `test_hardening.py`; lane-guard will name the renamed file. Wave 5 upload route (16b) uses `import_group_csv`.
