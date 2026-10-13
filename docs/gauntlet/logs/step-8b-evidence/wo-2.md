CODEX WORK ORDER 2 (step 8b, lane starb): one review fix and a scope-locked cleanup

GOAL:
In backend/nflpi/analytics/star_backtest.py only: fix one edge case a new test pins, and make three small
simplifications. All 11 tests in backend/tests/test_star_backtest.py must pass; no other behaviour changes.

BASELINE:
Worktree /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-starb, branch lane/starb.
`tests/test_star_backtest.py`: 1 failed, 10 passed (the failure is the fix below). `tests/test_model.py`: 34 passed.

ALLOWED SCOPE:
- backend/nflpi/analytics/star_backtest.py (the only file you may edit)
Do NOT edit any test, doc, or other module.

CHANGES:
1. FIX (league_stars): a season gets a star list only when it has at least one row with season_type == "REG".
   Today `stars = {row["season"]: {} for row in stats}` gives a season with playoff rows only an EMPTY list, which
   star_out_features then reads as "nobody is out" (0) instead of unknown (NaN). A season with regular-season rows
   but no player above 0 still gets a key with an empty dict.
2. CLEANUP (_counts): iterate the ids in sorted order (`for pid in sorted(ids)`) so the weighted float sum is the
   same on every run (set order changes with string hashing).
3. CLEANUP (star_out_features): replace the index loop `for i in (0, 1)` on the reserve counts with a zip over the
   first two values of each tuple, the same shape as the report line above it (home minus away).
4. CLEANUP (star_preds): `frame.assign(**{name: inputs[name] for name in inputs.columns})` -> `frame.assign(**inputs)`.
Nothing else: no renames, no new helper, no new constant, no reformatting of untouched lines.

FAILING EVIDENCE:
tests/test_star_backtest.py::test_unknown_stays_missing_and_a_known_empty_report_is_zero
  assert 2021 not in sb.league_stars(post_only)

PROOF (must pass; never run pytest without that DATABASE_URL: the default points at a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_codex uv run pytest -q tests/test_star_backtest.py tests/test_model.py
cd backend && uvx ruff check nflpi tests
(If uv cannot write its cache, set UV_CACHE_DIR to a temp folder.) Do not run the full test suite.

CONSTRAINTS:
- smallest correct diff; behaviour-preserving apart from change 1; ruff line length 120
- do not mutate inputs; no new dependency; no print; do not change or weaken any test
- do not commit, never push, never deploy

RETURN:
- the diff summary, the pytest summary line, the ruff line, any blocker
