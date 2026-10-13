CODEX WORK ORDER 2 (step 14, lane model)

GOAL:
Make the three new tests at the bottom of backend/tests/test_model.py pass (`test_team_game_epa_...`,
`test_epa_diff_...`, `test_epa_candidate_...`) and extend the evidence script to the EPA candidate.

BASELINE:
Branch lane/model, commit a4ebda6. tests/test_model.py fails at import:
`ImportError: cannot import name 'epa_diff' from 'nflpi.predictions.features'`. Before these tests: 15 passed.

ALLOWED SCOPE (edit only these):
- backend/nflpi/predictions/features.py
- backend/nflpi/analytics/backtest.py
- docs/gauntlet/logs/step-14-evidence/candidates.py
Do NOT edit backend/tests/test_model.py or any other file. If a test looks wrong, stop and say so in RETURN.

REQUIREMENT (frozen; names and signatures are fixed):

features.py
- `team_game_epa(rows: list[dict]) -> pd.DataFrame` with columns exactly `["game_id", "team", "net_epa"]`, rows in
  input order. `rows` are raw nflverse `stats_team_week` CSV rows (string values) with keys `game_id`, `team`,
  `passing_epa`, `rushing_epa`, `attempts`, `sacks_suffered`, `carries`. A team's EPA per play in a game is
  (passing_epa + rushing_epa) / (attempts + sacks_suffered + carries). Its `net_epa` is its own value minus its
  opponent's value in the same game. A side is unusable when any of the five values is `""` or `"NA"`, or its
  plays are 0. Keep a game only when it has exactly two usable sides; otherwise leave out both rows.
  Never fill a missing value.
- `epa_diff(df: pd.DataFrame, epa: pd.DataFrame, half_life: float) -> pd.Series`, indexed like `df`. `df` is in
  kickoff order (as `games_frame` returns) with `game_id`, `home_team`, `away_team`. `epa` is `team_game_epa`'s
  output. Walk the rows in order. Before each game a team's rating is the weighted mean of its `net_epa` in the
  games above that row only: the most recent rated game weighs 1, the one before `0.5 ** (1 / half_life)`, and so
  on (keep a running weighted sum and weight sum per team; multiply both by `0.5 ** (1 / half_life)` before adding a
  game). The value for the row is home rating minus away rating, and NaN when either team has no rated game yet.
  A game with no `epa` rows changes no rating. Ratings carry across seasons. Do not mutate `df` or `epa`.
- `BASE_FEATURES` and `BLEND_FEATURES` stay exactly as they are. `add_features` is not changed.

backtest.py
- Add `EPA_HALF_LIVES = (4, 8, 16)`.
- `candidate_preds(df, seasons, window=10, epa=None)`: when `epa` is None, behave exactly as now (no EPA columns).
  When given, add a feature column `epa_diff_<h>` for each half-life to every Elo frame (compute each once from
  `df`, not once per Elo setting; copy the frames, do not mutate the caller's `df`), and for each test season add a
  probability column `p_epa_<h>`: fit `LogitModel.fit(train.dropna(subset=["market_logit"]), [*BLEND_FEATURES,
  f"epa_diff_{h}"])` on the same training rows `predict_season` uses (prior `window` seasons only, finished games;
  never the test season), predict the test rows, and where the result is NaN (feature missing) use that row's
  `p_blend`.
- `predict_season`, `inseason_blend`, `evaluate` and `run_backtest` keep their behavior and output.

candidates.py
- Also download `stats_team/stats_team_week_<season>.csv` for seasons 2002 to 2025 with `nflverse.fetch_csv`
  (a failure must raise), build `epa = team_game_epa(all rows)`, pass it to `candidate_preds`, and add
  `"epa_rating": [f"p_epa_{h}" for h in EPA_HALF_LIVES]` to the `evaluate` call after `inseason_refit`.
- Add to the printed JSON: `"epa_games": number of distinct game_id values in epa`. Update the module docstring.
  Still no file writes and no arguments.

FAILING EVIDENCE / PROOF (must pass; never run pytest without this DATABASE_URL: the default is a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15442/nflpi_codex uv run pytest -q tests/test_model.py
cd backend && uvx ruff check nflpi tests ../docs/gauntlet/logs/step-14-evidence/candidates.py
Do not run the full suite and do not run candidates.py (the coordinator runs both).

CONSTRAINTS:
- Smallest correct diff. No new dependency. Plain functions: no class, registry, config or plug-in layer.
- Match the surrounding code: typed signatures, one-line docstrings, ruff line length 120.
- No print or logging in the two modules. Do not import from `nflpi.ingestion` inside `nflpi/predictions` or
  `nflpi/analytics`.

DO NOT:
- edit tests, jobs.py, engine.py, the API, or anything outside ALLOWED SCOPE
- commit, push, or touch any container or port other than the test database URL above

RETURN:
- changed files
- a short summary
- the two proof command results
- any blocker
