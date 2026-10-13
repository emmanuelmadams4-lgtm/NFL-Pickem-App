CODEX WORK ORDER 1 (step 14b, lane modelb)

GOAL:
Make the twelve failing tests at the end of backend/tests/test_model.py pass (everything after the comment line
"# ---- Step 14b: five ideas from the repo review"). They add: a cluster bootstrap, four more ways to remove the
bookmaker margin, row weights for the logistic fit, a function that scores eleven model variants walk-forward,
and a walk-forward calibration function.

BASELINE:
Worktree /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-modelb, branch lane/modelb.
`tests/test_model.py`: 12 failed, 19 passed. The 19 must stay green.

ALLOWED SCOPE (edit only these five files):
- backend/nflpi/analytics/metrics.py
- backend/nflpi/analytics/backtest.py
- backend/nflpi/predictions/market.py
- backend/nflpi/predictions/features.py
- backend/nflpi/predictions/model.py
Do NOT edit tests/test_model.py, anything under docs/, engine.py, jobs.py, api/, apps/, packages/.

REQUIREMENT (the tests are the contract; read them first):

metrics.py
1. `bootstrap_ci(values, reps=2000, seed=7, clusters=None)`. With `clusters=None`: exactly today's code and numbers.
   With `clusters` (one label per value): raise ValueError if its length differs from `values`. Else
   `_, inverse = np.unique(clusters, return_inverse=True)`; per-cluster sums (`np.bincount(inverse, weights=values)`)
   and counts; draw `idx = rng.integers(0, n_clusters, size=(reps, n_clusters))` from `np.random.default_rng(seed)`;
   each replicate mean = `sums[idx].sum(axis=1) / counts[idx].sum(axis=1)`; return the 2.5 and 97.5 percentiles.
2. `paired_gain(p_new, p_old, y, clusters=None)`. Without `clusters` the returned dict is exactly today's (same six
   keys, same values). With `clusters`: ValueError if its length differs; add three keys:
   `log_loss_gain_ci_cluster` and `accuracy_diff_ci_cluster` (lists, from `bootstrap_ci(..., clusters=clusters)` of the
   same per-game differences) and `ships_cluster` (plain bool: cluster low end > 0 and accuracy_diff >= 0).
   `ships` never changes.

backtest.py
3. `evaluate(preds, candidates, tune, confirm, cluster=None)`. Raise ValueError when `tune` and `confirm` share a
   season. When `cluster` is a list of column names, pass `clusters=rows.groupby(cluster, sort=True).ngroup().to_numpy()`
   to every `paired_gain` call (tune rows and confirm rows each grouped on their own rows). `cluster=None`: today's output.
4. `RECENCY_HALF_LIVES = (2, 4, 8)` (seasons).
5. `idea_preds(df, seasons, window=10) -> pd.DataFrame`. `df` is the schedule frame the bench already takes, plus
   columns `spread_line` and `total_line` (may be NaN). For each season: start from `predict_season(frames, season, window)`
   and `_train_rows(frames, season, window)` (training rows = the `window` seasons before the test season, nothing else).
   Add to the frames (once, before the season loop) the feature columns:
   `market_logit_<m>` for m in ("additive", "shin", "power", "odds_ratio") via `features.market_logit(df, m)`;
   `spread_pts` = spread_line / 7; `total_pts` = (total_line - 45) / 10; `spread_per_total` = 10 * spread_line / total_line.
   Use named constants for 7, 45 and 10. Then add prediction columns, each from ONE `LogitModel.fit` per test season on
   `train.dropna(subset=["market_logit"])`:
   - `p_devig_<m>`: features `[f"market_logit_{m}", *BASE_FEATURES]`.
   - `p_in_spread`, `p_in_total`, `p_in_both`, `p_in_ratio`: features `[*BLEND_FEATURES, *extra]` with extra =
     ["spread_pts"], ["total_pts"], ["spread_pts", "total_pts"], ["spread_per_total"].
   - `p_recency_<h>` for h in RECENCY_HALF_LIVES: features BLEND_FEATURES (the same list), with
     `weights = 0.5 ** ((season - 1 - train["season"]) / h)` passed as a pandas Series on the training rows' index.
   Where a variant's prediction is NaN for a test row (a needed input is missing) the value is that row's `p_blend`
   (`.fillna(test["p_blend"])`, as `candidate_preds` does for EPA). Return the seasons concatenated with
   `ignore_index=True`, keeping only rows where `p_market` is not NaN (same as `candidate_preds`). The returned frame
   must carry `spread_pts`, `total_pts`, `spread_per_total`. Do not compute `p_inseason` or EPA columns here.
6. `calibrated(preds, method) -> pd.Series` (index = preds.index, float). `method` is "platt" or "isotonic", anything
   else raises ValueError. For each season S in `preds["season"]`: fit on the rows with season < S (inputs `p_blend`,
   target `home_win`), predict the rows of S. The earliest season stays NaN. Clip every value to [0.01, 0.99].
   platt: a logistic regression of home_win on the log-odds of p_blend (reuse `LogitModel` on one temporary column).
   isotonic: `sklearn.isotonic.IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")` (scikit-learn is
   already a dependency).

market.py
7. `DEVIG_METHODS = ("multiplicative", "additive", "shin", "power", "odds_ratio")` and
   `devig_home_prob(home_ml, away_ml, method="multiplicative") -> float | None`. Unknown method: ValueError (check this
   first). Either price None: return None. With h, a = implied_prob of each side:
   - multiplicative: exactly `novig_home_prob(home_ml, away_ml)` (leave that function as it is).
   - additive: h - (h + a - 1) / 2.
   - power: p = h ** k with k > 0 solving h ** k + a ** k = 1 (solve with plain bisection, to about 1e-12; no SciPy import).
   - odds_ratio: p = h / (c + h - c * h) with c > 0 such that the home and away values sum to 1
     (closed form: c = sqrt(odds(h) * odds(a)), odds(q) = q / (1 - q)).
   - shin: z = ((B - 1) * (D * D - B)) / (B * (D * D - 1)) with B = h + a and D = h - a;
     p = (sqrt(z * z + 4 * (1 - z) * h * h / B) - z) / (2 * (1 - z)). When B == 1 return h.
   If the two prices carry no margin (h + a == 1) every method returns h.

features.py
8. `market_logit(df, method) -> pd.Series` (index = df.index, float): for each row, NaN when `home_ml` or `away_ml`
   is NaN, else the log-odds of `devig_home_prob(home_ml, away_ml, method)` after clipping the probability to
   [0.01, 0.99]. Do not change `add_features` or its output.

model.py
9. `LogitModel.fit(df, features, weights=None)`. `weights` is a pandas Series indexed like `df`. Raise ValueError if
   any weight is negative or not finite. After the existing `dropna`, pass `weights.loc[train.index]` as
   `sample_weight`. `weights=None`: today's behaviour exactly.

FAILING EVIDENCE:
docs/gauntlet/logs/step-14b-evidence/red-1.log (TypeError / AttributeError: the seam does not exist yet).

PROOF (must pass; never run pytest without that DATABASE_URL: the default points at a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_codex uv run pytest -q tests/test_model.py
cd backend && uvx ruff check nflpi tests
Do not run the full test suite; the coordinator runs it.

CONSTRAINTS:
- Smallest correct diff. No new dependency. Plain functions and module constants: no class, registry, config or plug-in layer.
- Match the surrounding code: type hints on every function, one-line docstrings, lines up to 120 characters (ruff),
  compact style like `candidate_preds` in backtest.py.
- Existing behaviour must not change: BASE_FEATURES, BLEND_FEATURES, add_features, run_backtest, candidate_preds,
  predict_season, inseason_blend, novig_home_prob, and the output of bootstrap_ci / paired_gain / evaluate /
  LogitModel.fit when the new argument is left out.
- No value known only after kickoff may enter a feature or a fit. Missing stays missing (NaN or None), never a guess.
- No print or debug statements. Do not commit. Never push. Do not touch files outside the allowed scope.
- If a test looks wrong, stop and say which one and why. Do not edit or weaken it.

TASK:
Make the failing evidence pass with the smallest correct diff.

RETURN:
- changed files
- concise implementation summary
- the two proof command results (the pytest summary line and the ruff line)
- any blocker
