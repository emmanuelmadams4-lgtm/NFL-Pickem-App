CODEX WORK ORDER 3 (step 14, lane model): review fixes and cleanup

GOAL:
Make the three failing tests in backend/tests/test_model.py pass, and remove one piece of duplication. No other
behavior change.

BASELINE:
Branch lane/model, working tree on top of 2c4ece6. `tests/test_model.py`: 3 failed, 16 passed
(test_paired_gain_refuses_missing_or_empty_input, test_team_game_epa_is_net_epa_per_play_and_leaves_out_incomplete_games,
test_epa_diff_is_a_pregame_weighted_mean_of_earlier_games).

ALLOWED SCOPE (edit only these):
- backend/nflpi/analytics/metrics.py
- backend/nflpi/analytics/backtest.py
- backend/nflpi/predictions/features.py
- docs/gauntlet/logs/step-14-evidence/candidates.py
Do NOT edit backend/tests/test_model.py or any other file. If a test looks wrong, stop and say so in RETURN.

REQUIREMENT:
1. metrics.paired_gain: first thing, raise `ValueError` with a short clear message when the three arrays do not have
   the same length, when they are empty, or when any value in `p_new`, `p_old` or `y` is not finite
   (`np.isfinite`). A missing prediction must never be scored as a wrong pick.
2. features.team_game_epa: a side is also unusable when any of its five parsed values is not finite
   (`math.isfinite`), for example the strings "nan" or "inf". Everything else stays as it is.
3. features.epa_diff: raise `ValueError` when `df["kickoff_utc"]` is not in non-decreasing order
   (`is_monotonic_increasing`), because rows out of order would leak later games into earlier ratings. Say so in the
   docstring in a few words.
4. backtest.py cleanup, no behavior change: the same four lines (train seasons, `tune_elo`, pick the frame, select
   finished rows of the train seasons) now appear in `predict_season`, `inseason_blend` and the EPA branch of
   `candidate_preds`. Extract ONE private helper, e.g.
   `_train_rows(frames, season, window) -> tuple[EloParams, pd.DataFrame]` (the tuned Elo settings and the training
   rows), and use it in all three places. `predict_season` must return exactly what it returns now.
   Fix the `candidate_preds` docstring so it names both candidates.
5. candidates.py: print with `json.dumps(..., indent=1, allow_nan=False)` so a NaN verdict fails loudly, and add two
   keys beside `epa_games`: `"epa_rows": len(epa_rows)` and `"epa_missing_scored_games"`: the number of rows in
   `preds` whose `epa_diff_4` is NaN (rows that fell back to the blend).

PROOF (must pass; never run pytest without this DATABASE_URL: the default is a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15442/nflpi_codex uv run pytest -q tests/test_model.py
cd backend && uvx ruff check nflpi tests ../docs/gauntlet/logs/step-14-evidence/candidates.py
Run only that one test file, once at a time. Do not run the full suite, candidates.py, or any other test process
(machine rule tonight: the host is overloaded).

CONSTRAINTS:
- Smallest correct diff. No new dependency (`math` is stdlib). Plain functions.
- Match the surrounding code: typed signatures, one-line docstrings, ruff line length 120.
- No print or logging in the modules.

DO NOT:
- edit tests, jobs.py, engine.py, the API, or anything outside ALLOWED SCOPE
- commit, push, or touch any container or port other than the test database URL above

RETURN:
- changed files, a short summary, the two proof results, any blocker
