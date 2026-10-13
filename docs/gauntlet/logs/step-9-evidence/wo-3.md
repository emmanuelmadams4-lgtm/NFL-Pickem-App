CODEX WORK ORDER 3 (step 9, lane scores): cleanup only, no behaviour change

GOAL:
Three behaviour-preserving refactorings in the two score modules. Every test must stay green with no test edit.

BASELINE:
Worktree: this directory (branch lane/scores), HEAD 1c5e104 or later. `tests/test_scores.py`: 50 passed.

ALLOWED SCOPE (edit only these two files):
- backend/nflpi/predictions/scores.py
- backend/nflpi/analytics/score_backtest.py

REQUIREMENT (one transformation each, nothing else):
1. Extract constant (score_backtest.py): the list of the six `pred_<method>_<side>` column names is built twice (`required` in `summary`, `prediction_cols` in `run_score_backtest`). Build it once as a module constant `PRED_COLS` next to `METHODS` and use it in both places.
2. Extract function (score_backtest.py): `predict_season` turns a (home, away) pair of number sequences into two float columns of entries twice (once for the line, once per model). Extract one private helper `_entry_columns(home, away) -> tuple[np.ndarray, np.ndarray]` (entry_pair per row; NaN for both when either number is missing) and call it for all three methods.
3. Remove dead code (scores.py): the `.copy()` after `add_features(df, elo)` in `add_score_features` is redundant because `add_features` already returns a new frame (`run_elo` copies). Remove it only if the test that checks the caller's frame is unchanged still passes; otherwise leave it and say so.

PROOF (run from backend/):
DATABASE_URL=postgresql+psycopg://nflpi:test@127.0.0.1:15446/nflpi_wo uv run pytest -q tests/test_scores.py     (50 passed)
uvx ruff check nflpi tests
NEVER run pytest without that DATABASE_URL. Run only this one test file.

CONSTRAINTS:
- no behaviour change, no new public name except `PRED_COLS`, no renames of existing public names
- no other "improvements"; smallest diff; ruff line length 120
- the strings "sqlalchemy", "httpx", "requests", "urllib", "open(", "os.environ", "subprocess", "socket" must not appear in either module
- do not edit the test file or any other file; do not commit; never push

RETURN:
- changed files, what each transformation did, proof result, blocker if any
