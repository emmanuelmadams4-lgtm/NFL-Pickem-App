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
* **Scope, and what is cut:** `backend/nflpi/group/` (`importer.py`, `queries.py`), `backend/migrations/versions/0005_group_picks.py`, `backend/tests/test_group.py`, `backend/tests/fixtures/group/`, plus the two granted seams: two model classes appended to `backend/nflpi/models.py`, one line in `backend/tests/test_hardening.py`. Cut and carried to wave 5: the upload route and its auth, schemas, the Group screen, shares in the report or the evidence pack, a run log row per import, any scoring by the app itself.
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
* **Migration number:** lanes.md assigns 0005 with down revision 0004 (lane news). 0004 is not on this branch, so here `down_revision = "0003"` and the migration-list line reads `0001, 0002, 0003, 0005`; the gate cannot pass any other way. The integrator re-points one line in each file when news has landed (named again in LANDING).
* **Instrumentation:** PROCEEDING WITHOUT a metric: single-user app, no analytics. The import returns the kind of file and the row count and raises a line-numbered error; the wave 5 upload route records each import where the owner can see it.
* **Skills:** `/jevgrep`: `~/.claude/plans/nfl-pickem-lanes-logs/s16a-jg-csv-import.log` ranked 2 files; it pinned the owner's own pick import in `api/main.py` (`import_picks`: skips bad rows, no size cap), which this step does not reuse because the group file is all-or-nothing, and `franchise()` in `ingestion/nflverse.py`, which it does reuse. `/graft`: N/A (file homes fixed by the lane map). `tdd`: no project tdd skill; the coordinator wrote the failing tests before any production code. `ponytail`: in every work order. `jev`: loaded before the first decision call. Design Gauntlet: N/A (no screen). `harness-engineering`: N/A (ordinary feature code). Parallel Lanes: claim made, `lane-guard check` at the end.
* **Tools:** `JEVGREP: ready` (`jg` 0.8.0, doctor exit 0). `HEADROOM: not-routed` (doctor exit 2; not a blocker). Codex: `codex-cli 0.156.1`.
* **Test database:** own container `nflpi-lane-group-db` on `127.0.0.1:15445`, no volume. The live stack on 5432 and 8000 is never used. `gate.sh` sets `DATABASE_URL` itself.
* **Baseline at `d88d74e`** (`bash gate.sh baseline`): see section 3, first row.
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
| N5 | Member names are cleaned before use: every character whose Unicode category starts with `C` (control, format, private use, surrogate, unassigned) is removed, then runs of white space become one space and the ends are trimmed. Any other text, markup included, is stored unchanged as plain text | functional |
| N6 | A name that is empty, or longer than 64 characters, after cleaning is refused ("name") | functional |
| N7 | Any refusal writes nothing: rows stored before stay as they were, and good rows earlier in the same file are not written | operational |
| N8 | A row error starts `line N: `. No error contains a member name, and none echoes more than 40 characters of a cell. `GroupImportError` is a `ValueError` | operational |
| N9 | Importing the same file again leaves the same rows (idempotent) | functional |
| N10 | A corrected file updates the matching rows in place (a pick, a confidence, pick to no pick and back); rows not in the file are left alone | functional |
| W1 | A weekly file stores one row per member and week with that week's points. `Rank` is stored on the rows of the file's last week only; earlier weeks get no rank from this file. The result says `standings` and the number of rows | functional |
| W2 | Weekly bounds: `Rank` 1 to 9999, each week 0 to 136, `Total_Pts` plain digits and equal to the sum of the weeks ("total"); a member appears once ("twice") | functional |
| W3 | A later file never clears a rank an earlier file gave a week: on a week that is not its last, it updates points and keeps the stored rank. On its own last week it sets the rank | functional |
| W4 | Seasons are kept apart: the season is the caller's and part of the key | functional |
| Q1 | `game_shares` returns `game_id`, `members` (rows stored for the game), `picked` (rows with a pick), and for `away` and `home`: `team`, `picks`, `share` = picks / picked, `avg_confidence` = the mean confidence of that side's picks | user-facing |
| Q2 | Missing is missing: `share` is null for both sides when nobody picked, and `avg_confidence` is null for a side with no picks. A game with no rows returns zero counts, not an error | user-facing |
| Q3 | `game_shares` for an unknown game raises `LookupError` | functional |
| Q4 | `standings(season, week)` returns one entry per member with a row that week: `member`, `points` (that week), `total` (the member's points in weeks up to and including it, that season only), `rank` (stored, or null). Order: total high to low, then rank low to high, then name A to Z. No rows gives an empty list | user-facing |
| H1 | Hand check: the owner's two real files import with no refusal; stored rows equal an independent count of the files (rows, picks per team per game, points per member-week); straight-winner scoring from real results equals the weekly file for every member-week; recorded in section 5 with made-up labels in place of names | user-facing |

Operational layer note: N1, N2, N7 and N8 are what an operator sees when an import goes wrong. A run-log row per import belongs to the upload route (wave 5) and is carried.

First failing tests: `backend/tests/test_group.py` (red at `ModuleNotFoundError: No module named 'nflpi.group'`, the intended reason: the seam does not exist yet). Log `red-pytest.log`.

## 3. IMPLEMENTATION
(filled as the work lands)

## 4. CLEANUP
(pending)

## 5. VERIFICATION
(pending)

## 6. LANDING
(pending: the lane does not push; the integrator lands)
