CODEX WORK ORDER 1 (step 9, lane scores)

GOAL:
Create two new pure Python modules so that `backend/tests/test_scores.py` passes.

BASELINE:
Worktree: this directory (branch lane/scores). The test file and the spec are committed. Do not create another worktree.

ALLOWED SCOPE (create these two files, touch nothing else):
- backend/nflpi/predictions/scores.py
- backend/nflpi/analytics/score_backtest.py

READ FIRST (read-only, do not edit):
- backend/tests/test_scores.py            the bar: every expected number is explained in its comments
- docs/gauntlet/logs/step-9.md section 2  the frozen criteria S1 to S15
- backend/nflpi/predictions/features.py   `add_features`, `qb_changes` (the pattern for `scoring_form`)
- backend/nflpi/predictions/model.py      `LogitModel` (the dataclass pattern for `ScoreModel`)
- backend/nflpi/analytics/backtest.py     `predict_season`, `run_backtest` (the walk-forward pattern)
- backend/nflpi/analytics/metrics.py      `bootstrap_ci` (use it; do not write another bootstrap)

REQUIREMENT:

scores.py
- `FORM_GAMES = 16`
- `STATS_FEATURES = ["elo_diff", "home_field", "home_qb_change", "away_qb_change", "home_pf", "home_pa", "away_pf", "away_pa"]`
- `BLEND_FEATURES = ["implied_home", "implied_away", *STATS_FEATURES]`
- `implied_score(spread_line, total_line) -> tuple[float, float] | None`: (home, away) = ((total + spread) / 2, (total - spread) / 2). None when either is None, NaN or infinite, when total <= 0, or when abs(spread) > total.
- `entry(points: float) -> int`: round half up (floor(points + 0.5)), never below 0.
- `tiebreak_score(spread_line, total_line) -> dict | None`: `{"home": int, "away": int, "method": "line_implied"}` from the two functions above; None when implied_score is None.
- `scoring_form(df, games: int = FORM_GAMES) -> dict[str, list[float]]`: keys home_pf, home_pa, away_pf, away_pa, one value per row of `df` (rows are already in kickoff order). A value is the mean of that team's points scored (pf) or allowed (pa) in its last `games` earlier rows that have status "final" and both scores present; NaN when it has none. A row's own result is added only after its values are taken.
- `add_score_features(df, elo: EloParams) -> pd.DataFrame`: `features.add_features(df, elo)` plus the four form columns and `implied_home` / `implied_away` (NaN where implied_score is None). `df` carries `spread_line` and `total_line` columns.
- `ScoreModel` dataclass with fields `features, home_coef, home_intercept, away_coef, away_intercept` (plain floats and lists):
  - `fit(cls, df, features)`: ordinary least squares with an intercept (use `np.linalg.lstsq`, it must cope with a constant column), one fit for `home_score` and one for `away_score`, on rows with status "final" and no missing value in the features or either score. Raise `ValueError` whose message contains the word "rows" when there are fewer usable rows than `len(features) + 1`.
  - `predict(self, x) -> tuple[np.ndarray, np.ndarray]`: (home, away) raw decimals; NaN for a row with a missing feature.

score_backtest.py
- `METHODS = ["implied", "stats", "blend"]`, a `LABELS` dict with a plain-language label per method (say that the line is the closing line).
- `is_tiebreak_slot(weekday: str, kickoff_utc: datetime) -> bool`: True for weekday "Monday"; True for "Sunday" when the kickoff converted to America/New_York has hour >= 19; else False. Returns a real bool.
- `predict_season(frame, season, window) -> pd.DataFrame`: `frame` is the output of `add_score_features`. Train rows: seasons `season - window` to `season - 1`. Call `ScoreModel.fit(train, STATS_FEATURES)` and `ScoreModel.fit(train, BLEND_FEATURES)` exactly once each, passing only train-season rows. Test rows: this season, game_type "REG", status "final", both scores present. Return a copy of the test rows with float columns `pred_<method>_home` and `pred_<method>_away` for each method, each value an `entry` (whole number) or NaN when that method has no prediction for the row (missing line for `implied` and `blend`, missing feature for a model).
- `summary(preds) -> dict`: `preds` has `home_score`, `away_score` and the six `pred_*` columns, no NaN in them. Returns
  `{"games": n, "methods": [{"method", "label", "team_mae", "total_mae"} in METHODS order], "comparisons": [{"candidate", "team_mae_gain", "team_ci": [lo, hi], "total_mae_gain", "total_ci": [lo, hi], "wins"} for "stats" then "blend"]}`.
  Per game: team error = (|pred_home - home| + |pred_away - away|) / 2; total error = |(pred_home + pred_away) - (home + away)|. Gain = mean of the per-game (implied error - candidate error). Each interval is `bootstrap_ci` of those per-game differences (numpy float array). `wins` = team_ci low > 0 and total_mae_gain >= 0 (a real bool). With zero games every number is None, both intervals are `[None, None]` and `wins` is False.
- `pick_winner(comparisons) -> str | None`: the candidate with `wins` true and the largest `team_mae_gain`; None when nobody wins.
- `run_score_backtest(df, seasons, window=10) -> dict`: `add_score_features(df, EloParams())` (default Elo, no tuning), `predict_season` for each season, keep only rows where all six `pred_*` values are present, then
  `{"seasons": [int], "games": n, "methods": ..., "comparisons": ..., "by_season": [{"season", "n", "implied": {"team_mae", "total_mae"}, "stats": {...}, "blend": {...}}], "tiebreak_slots": summary of the rows where is_tiebreak_slot(weekday, kickoff_utc), "ships": pick_winner(comparisons of all games)}`.
  Only plain Python ints, floats, strings, bools, lists, dicts and None in the result (it must survive `json.dumps` and compare equal after `json.loads`).

FAILING EVIDENCE:
`ImportError: cannot import name 'score_backtest' from 'nflpi.analytics'` when collecting backend/tests/test_scores.py.

PROOF (run from backend/; the test database is already running on this machine):
DATABASE_URL=postgresql+psycopg://nflpi:test@127.0.0.1:15446/nflpi_wo uv run pytest -q tests/test_scores.py
uvx ruff check nflpi tests
NEVER run pytest without that DATABASE_URL. Run only this one test file, never the whole suite.

CONSTRAINTS:
- smallest correct diff; small typed functions; match the style of the files listed above (ruff, line length 120)
- no new dependency; numpy and pandas only; no scikit-learn in these modules
- no file, network, database or environment access in either module: the strings "sqlalchemy", "httpx", "requests", "urllib", "open(", "os.environ", "subprocess", "socket" must not appear anywhere in them, comments and docstrings included
- do not mutate the caller's DataFrame; return new objects
- no speculative abstractions, no extra public functions, no config, no CLI, no print
- each module starts with a short docstring saying what it is and that the line is the closing line (a benchmark with a timing advantage)
- do not edit the test file or any other file; do not commit; never push

TASK:
Make the failing evidence pass.

RETURN:
- changed files
- concise implementation summary
- proof command result
- blocker if one remains
