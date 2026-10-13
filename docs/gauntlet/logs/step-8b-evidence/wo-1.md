CODEX WORK ORDER 1 (step 8b, lane starb): the star-out bench module

GOAL:
Create ONE new module, backend/nflpi/analytics/star_backtest.py, so that all 11 tests in
backend/tests/test_star_backtest.py pass. Nothing else changes.

BASELINE:
Worktree /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-starb, branch lane/starb.
`tests/test_star_backtest.py` fails at import (the module does not exist). `tests/test_model.py`: 34 passed.

ALLOWED SCOPE:
- create backend/nflpi/analytics/star_backtest.py (the only file you may write)
Do NOT edit any existing file: no test, no doc, not backtest.py, features.py, model.py, metrics.py, stars.py,
engine.py, jobs.py, nflverse.py, api/, apps/, packages/. Do NOT import nflpi.analytics.stars.

READ FIRST:
- backend/tests/test_star_backtest.py (the contract; every assertion matters)
- docs/gauntlet/logs/step-8b.md section 2, clauses L1 to L3, F1 to F8, P1 to P5 (the frozen rules, in words)
- backend/nflpi/analytics/backtest.py: split_preds is the pattern for star_preds; reuse its private helpers
  `_elo_frames`, `_train_rows`, `_predict_or_blend`, `_market_games` and `predict_season` by importing them
- backend/nflpi/ingestion/nflverse.py: STAR_STATS (the 17 stat names on every stats row)

REQUIREMENT (three public functions and six constants):

Constants:
  STAR_LIMITS = {"qb": 32, "off": 64, "def": 64}
  REPORT_OUT = frozenset({"out", "doubtful"})
  ROSTER_OUT = frozenset({"RES", "PUP", "SUS"})
  ROSTER_FIRST_SEASON = 2016
  MIN_FIT_SEASONS = 3
  STAR_VARIANTS = {name: [extra input columns]} exactly as the test spells it, in that order
  Name the point values of the two scores as module constants too (no magic numbers).
  The tests monkeypatch STAR_LIMITS and ROSTER_FIRST_SEASON: read them from the module at call time, never as a
  default argument.

1. league_stars(stats: list[dict]) -> dict[int, dict[str, tuple[str, float]]]
   season -> player_id -> (group, weight). Clauses L1, L2, L3. Rows are plain dicts with keys season, week,
   season_type, player_id, position and the 17 STAR_STATS numbers. Only rows with season_type == "REG" count.
   Per season, sum each player's numbers. Group: "qb" when his row with the highest week has position "QB"
   (score = attempts); otherwise offence score and defence score by the formulas of clause L2, side = the higher
   one, offence on a tie. A quarterback is never on the offence or defence list. Stars per group: score > 0, sorted
   by score high to low then player_id low to high, first STAR_LIMITS[group]. weight = score / mean score of that
   group's stars in that season. A season with rows always has a key (its dict may be empty).

2. star_out_features(df, stats, reports, roster=None) -> pd.DataFrame
   One row per row of df, same index. Columns, in this order: star_out_diff, star_out_w_diff, qb_out_diff, and
   only when roster is not None: star_res_diff, star_res_w_diff. All floats, NaN = unknown. Clauses F1 to F8.
   It may read ONLY these df columns: season, week, kickoff_utc, home_team, away_team.
   - Stars for a game of season S: league_stars(stats)[S - 1] only. No list for S - 1 (key absent): all NaN.
   - reports rows: season, week, team, player_id, status (str or None), modified (aware datetime or None).
     A club's players out for a game = report rows with the same season, week and team, status lower-cased in
     REPORT_OUT, and (modified is None or modified < the game's kickoff_utc). Each player once.
   - Each value is home minus away. star_out_diff = count of non-quarterback stars out; star_out_w_diff = sum of
     their weights; qb_out_diff = count of quarterback stars out.
   - A (season, week) with no report row at all (any team, any status): NaN in every column. Otherwise a club
     with nothing out counts 0.
   - roster rows: season, week, team, player_id, status. Reserve set for a club and game = the report set above
     plus roster rows of the same season, week and team with status in ROSTER_OUT (None or any other status is
     ignored). star_res_diff / star_res_w_diff = count / weight sum of NON-quarterback stars in that union.
     NaN when the report columns are NaN, when season < ROSTER_FIRST_SEASON, or when that (season, week) has no
     roster row at all.
   Index the report and roster rows once (dicts keyed by (season, week, team)); do not rescan the lists per game.

3. star_preds(df, seasons, inputs, window=10) -> pd.DataFrame
   Clauses P1 to P5. `inputs` is a DataFrame with df's index holding the five input columns. Same shape as
   split_preds: attach the input columns to every Elo frame with assign, then per season call predict_season,
   take the training rows from _train_rows and drop rows without market_logit. For each (name, extra) in
   STAR_VARIANTS: rows = training rows with every `extra` column present; if rows["season"].nunique() <
   MIN_FIT_SEASONS, test[name] = test["p_blend"]; else fit LogitModel on rows with [*BLEND_FEATURES, *extra] and
   set test[name] = _predict_or_blend(model, test). Return _market_games(by_season).

FAILING EVIDENCE:
ImportError: cannot import name 'star_backtest' from 'nflpi.analytics'

PROOF (must pass; never run pytest without that DATABASE_URL: the default points at a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_codex uv run pytest -q tests/test_star_backtest.py tests/test_model.py
cd backend && uvx ruff check nflpi tests
(If uv cannot write its cache, set UV_CACHE_DIR to a temp folder.) Do not run the full test suite.

CONSTRAINTS:
- smallest correct diff: one module, plain functions, type hints on every signature, a one-line docstring on each
  public function, ruff line length 120, functions under 50 lines, no nesting deeper than 4
- no new dependency, no class, no config, no caching layer, no logging, no print
- do not mutate the inputs (df, the row dicts, the inputs frame)
- no network, no file access: the module only transforms what it is given
- do not change or weaken any test; if a test looks wrong, stop and say so in the RETURN
- do not commit, never push, never deploy

TASK:
Make the failing evidence pass with the smallest correct diff.

RETURN:
- changed files
- concise implementation summary
- proof command result (the pytest summary line and the ruff line)
- blocker, if any
