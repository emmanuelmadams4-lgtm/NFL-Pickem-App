CODEX WORK ORDER 3 (step 14b, lane modelb): review fixes and cleanup, behaviour unchanged

GOAL:
A scope-locked refactor of the code added in this step. No behaviour change: every number the bench produces must stay
the same, and all 34 tests in backend/tests/test_model.py must still pass.

BASELINE:
Worktree /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-modelb, branch lane/modelb, HEAD c0cbc4e.
`tests/test_model.py`: 34 passed.

ALLOWED SCOPE (edit only these two files, and only the functions named below):
- backend/nflpi/analytics/backtest.py: idea_preds, split_preds, candidate_preds, calibrated, plus small private helpers
- backend/nflpi/predictions/features.py: offence_defence only
Do NOT edit tests, docs, add_features, metrics.py, market.py, model.py, engine.py, jobs.py, api/, apps/, packages/.

CHANGES (each one small):
1. backtest.py: the expression `pd.Series(model.predict(test), index=test.index).fillna(test["p_blend"])` appears in
   candidate_preds, idea_preds and split_preds. Extract ONE private helper (for example
   `_predict_or_blend(model, test) -> pd.Series`, docstring: a game missing an input keeps the blend's number) and use
   it in all three. The tail `preds = pd.concat(by_season, ignore_index=True); return preds[preds["p_market"].notna()]`
   appears three times: extract ONE private helper (for example `_market_games(by_season)`) and use it in all three.
2. idea_preds: stop mutating the Elo frames in place and stop recomputing `market_logit` once per Elo frame. Build the
   new columns ONCE from `df` (the four `market_logit_<method>` series, `spread_pts`, `total_pts`, `spread_per_total`)
   and attach them with `frame.assign(**columns)` the way split_preds does. Use `DEVIG_METHODS[1:]` (import
   DEVIG_METHODS from nflpi.predictions.market) instead of the two hard-coded method tuples.
   `spread_per_total` must be missing (NaN) where `total_line` is not above 0: use `.where(df["total_line"] > 0)`.
3. calibrated: clip `p_blend` to [0.01, 0.99] before taking log-odds for the platt method (so a 0 or 1 can never give
   an infinite input), using two named module constants for 0.01 and 0.99 that the final clip also uses. Say in the
   docstring that values are clipped to 1% to 99%.
4. features.py offence_defence: simplify. Remove the `try/except` (bad input should raise, not be skipped) and the
   hand-unpacked `first_*` / `second_*` names. Keep the behaviour the tests pin: output columns and order, rows in
   input order, a game left out unless it has exactly two rows, two different teams, and finite numbers with
   plays > 0 on both sides.

PROOF (must pass; never run pytest without that DATABASE_URL: the default points at a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_codex uv run pytest -q tests/test_model.py
cd backend && uvx ruff check nflpi tests
(If uv cannot write its cache, set UV_CACHE_DIR to a temp folder.) Do not run the full test suite.

CONSTRAINTS:
- Behaviour-preserving. Smallest diff that does the four changes. No new dependency, no new public name, no new file.
- Match the surrounding code: type hints, one-line docstrings, lines up to 120 characters.
- No print or debug statements. Do not commit. Never push.

RETURN:
- changed files, what was simplified, the two proof results, any blocker
