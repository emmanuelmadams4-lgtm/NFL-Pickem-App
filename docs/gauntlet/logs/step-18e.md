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

Own tests: `tests/test_data_layer.py` 56 passed. ruff clean. No existing file edited, no migration, no route, no dependency. App code does no file write; network only through the existing `fetch_csv` (public nflverse files), only inside the coverage module.

Note: TDD order deviated for C3 to C5 (tests written with or after code); the tests passed first run, so they were not shown to fail for the intended reason.
