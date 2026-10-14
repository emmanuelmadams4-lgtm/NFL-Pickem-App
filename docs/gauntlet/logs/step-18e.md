# Step 18e: point-in-time data layer (lane data)

Base main `4cd599b`, branch `lane/data`. ONE_SHOT. Builder: Claude Sonnet subagent (Codex out of credits). Test database: container `nflpi-lane-model-db`, database `nflpi_data`.

| # | Checkpoint | Result |
|---|---|---|
| C1 | Spec and tests written | Spec in the builder brief (as-of rule `observed_at <= cutoff`; result known at kickoff + 4 h; spread sign in one place). Tests file created with the package |
| C2 | As-of frame builder | `asof.py`: games, lines, quarterbacks, injuries, weather, `build_asof_frame`, DB loader. Red (import error, 6 failures) then green |
| C3 | Input checks | `checks.py`: columns, team codes, duplicate games, seasons, missing counts, snapshots. Tests written after the code (not seen red first) |
| C4 | Coverage report | `coverage.py` run on the public 2026 files: 272 games, 79 finished, 107 with a line, 93 with both quarterbacks, matches PLAN section 4. `docs/model/DATA_COVERAGE.md` |
| C5 | Docs and matchup score | `docs/model/FEATURES.md`; `matchup.py` (bench candidate only, imported by nothing in predictions, api, analytics or jobs; a test greps for that) |
| C6 | Critic, lane-guard | see end of file |

Own tests: `tests/test_data_layer.py` 70 passed. ruff clean. No existing file edited, no migration, no route, no dependency. App code does no file write; network only through the existing `fetch_csv` (public nflverse files), only inside the coverage module.

Note: TDD order deviated for C3 to C5 (tests written with or after code); the tests passed first run, so they were not shown to fail for the intended reason.

## C6: critic round 1 (head 04d1efc): FAIL
2 HIGH (asof_games kept the after-the-fact quarterback names; FEATURES.md said the code was not built), 5 MEDIUM (naive timestamps read as UTC, missing observed_at silently empty, duplicate game ids, injury key collapse and case, tie order), LOW check gaps. All fixed in the next commit with 12 new tests (68 total).

## C6: critic round 2 (head 526f037, fresh critic): PASS with warnings
No leak found. Two MEDIUM fixed in the final commit: `kind` dropped from the as-of lines (ingestion flips latest to closing after the game), and a -110/-110 pick'em pair now allowed by the moneyline sign check. LOW left as is: `check_snapshots` runs on the whole table before the cutoff filter; `check_games` is not called by the as-of builder (callers run it); duplicate key differs from the DB constraint (no `source` column in the check). Final: 70 passed, ruff clean.
