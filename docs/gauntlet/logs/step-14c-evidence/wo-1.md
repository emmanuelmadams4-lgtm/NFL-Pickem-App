CODEX WORK ORDER 1 (step 14c)

GOAL: create backend/nflpi/analytics/model_c.py with the tree, stack and report pieces so the named tests pass.

BASELINE: branch lane/modelc, commit 476a40a. tests/test_model.py: 34 passed.

ALLOWED SCOPE: only the new file backend/nflpi/analytics/model_c.py. Do not edit any test, any other file.

REQUIREMENT (clauses are in docs/gauntlet/logs/step-14c.md section 2: T1-T4, S1-S2, C1; read them and backend/tests/test_model_c.py):
- Constants: TREE_SETS (core = BLEND_FEATURES; wide = BLEND_FEATURES + spread_line,total_line,rest_diff,roof_indoor,temp_f,wind_mph,div_flag), TREE_GRID=((2,30),(2,80),(3,30),(3,80)), TREE_LEARNING_RATE=0.05, TREE_MAX_ITER=300, STACK_GRID = 21 weights 0.0..1.0 step 0.05 (last must equal exactly 1.0).
- tree_column(set_name, depth, leaf) -> "p_tree_<set>_d<depth>_l<leaf>".
- tree_inputs(frame) -> copy with roof_indoor (dome/closed 1.0, outdoors/open 0.0, missing NaN) and div_flag (div_game True->1.0 else 0.0).
- class TreeModel (dataclass: features, n_iter, model) with classmethod fit_early(train, features, depth, leaf) and predict(x)->np.ndarray. Use sklearn HistGradientBoostingClassifier(max_depth=depth, min_samples_leaf=leaf, learning_rate=TREE_LEARNING_RATE, max_iter=..., l2_regularization=1.0, early_stopping=False, random_state=0). First fit: all training seasons except max season, max_iter=TREE_MAX_ITER; pick n_iter = argmin over staged_predict_proba of log loss on the max season (use nflpi.analytics.metrics.game_log_loss/log_loss; at least 1); refit on all training rows with max_iter=n_iter. Drop only rows missing home_win (NaN in features allowed).
- tree_preds(df, seasons, window=10, grid=TREE_GRID): follow backtest.idea_preds: frames = backtest._elo_frames(df) with tree_inputs and the spread/total columns present (spread_line, total_line come from df), test = backtest.predict_season(frames, season, window), train = backtest._train_rows(...) then keep rows with market_logit not null. For each set and (depth,leaf) in grid add column tree_column(...) = backtest._predict_or_blend(model, test). Return backtest._market_games(by_season). The eight columns for the default grid.
- stack_weight(p_blend, p_tree, y): grid weight with lowest log loss; ties -> smaller weight.
- stacked(preds, tree_col): pd.Series on preds.index; season S uses weight fitted on rows of seasons < S in preds; first season NaN.
- evaluate_c(preds, candidates, tune, confirm, cluster=None): call backtest.evaluate and for each candidate dict add "all_variants": list of {variant, tune_gain, confirm_gain, gap}; confirm_gain = paired_gain(...)["log_loss_gain"] on confirm rows; gap = tune_gain - confirm_gain. Keep all keys evaluate returns.
Leave the margin, explosive and points functions for work order 2 (do not write them).

PROOF: cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15448/nflpi_test uv run pytest -q tests/test_model_c.py -k "tree or stack or evaluate_c" ; uvx ruff check nflpi tests

CONSTRAINTS: smallest correct diff (ponytail), no new dependency, no speculative abstraction, ruff line length 120, type hints, docstring one line per public function, do not mutate input frames, do not commit, never push.
RETURN: changed files, summary, proof result, blocker.
