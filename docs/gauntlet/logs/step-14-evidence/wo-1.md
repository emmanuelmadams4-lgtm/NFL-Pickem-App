CODEX WORK ORDER 1 (step 14, lane model)

GOAL:
Make the nine new tests at the bottom of backend/tests/test_model.py pass (everything under the comment
"# --- Step 14: candidates are judged against the current blend"). Add one small evidence script.

BASELINE:
Branch lane/model, commit a27cfd0. Before this commit the suite was 172 passed. Right now tests/test_model.py
fails at import: `ImportError: cannot import name 'candidate_preds' from 'nflpi.analytics.backtest'`.

ALLOWED SCOPE (edit only these):
- backend/nflpi/analytics/metrics.py
- backend/nflpi/analytics/backtest.py
- docs/gauntlet/logs/step-14-evidence/candidates.py   (new)
Do NOT edit backend/tests/test_model.py or any other file. If a test looks wrong, stop and say so in RETURN.

REQUIREMENT (frozen; signatures are fixed):

metrics.py
- `game_log_loss(p, y) -> np.ndarray`: one log loss per game, same clipping as `log_loss`. Make `log_loss` its mean.
- `paired_gain(p_new, p_old, y) -> dict` with exactly these keys:
  `n` (int), `log_loss_gain` (float: mean of old loss minus new loss per game), `log_loss_gain_ci` ([lo, hi] from
  `bootstrap_ci` of those per-game differences), `accuracy_diff` (float: mean of new-correct minus old-correct per game,
  "correct" as in `summarize`), `accuracy_diff_ci` ([lo, hi] from `bootstrap_ci` of those per-game differences),
  `ships` (a plain Python bool: True only when `log_loss_gain_ci[0] > 0` and `accuracy_diff >= 0`).

backtest.py
- `inseason_blend(frames, season, window) -> pd.Series`: home-win probability for the same test rows, in the same
  order and with the same index, as `predict_season(frames, season, window)` returns. Elo settings are chosen exactly
  as `predict_season` does (prior seasons only). For each `week` of the test rows, fit
  `LogitModel.fit(train.dropna(subset=["market_logit"]), BLEND_FEATURES)` where `train` = the rows `predict_season`
  trains on (prior `window` seasons, finished) plus rows of the test season that are finished (`home_win` not null)
  and whose `kickoff_utc` is before the earliest `kickoff_utc` of that week's test rows. Use time, not the week
  number: a postponed game that had not kicked off yet must not be in the training rows. Test rows without a market
  line get NaN.
- `candidate_preds(df, seasons, window=10, epa=None) -> pd.DataFrame`: like the first three lines of `run_backtest`
  (build the Elo frames once, `predict_season` per season, concat with `ignore_index=True`, keep rows with a market
  line) plus a column `p_inseason` from `inseason_blend`. Accept `epa` and ignore it for now (work order 2 uses it).
- `evaluate(preds, candidates, tune, confirm) -> list[dict]`: `candidates` maps a candidate name to a list of
  probability column names (its variants). For each candidate, in dict order, return
  `{"candidate": name, "variants": [{"variant": col, "tune": paired_gain(col vs "p_blend" on rows whose season is in
  tune)}, ...], "chosen": the variant with the largest tune `log_loss_gain` (first one on a tie),
  "confirm": paired_gain(chosen vs "p_blend" on rows whose season is in confirm), "ships": confirm["ships"]}`.
  Only the chosen variant is scored on the confirm seasons.
- `run_backtest` and `predict_season` keep their behavior and output. `engine.train` calls `run_backtest`: do not
  make it slower or change what it returns.

candidates.py (evidence script, run as `cd backend && uv run python ../docs/gauntlet/logs/step-14-evidence/candidates.py`)
- Build the games frame exactly as `backtest()` in backend/nflpi/jobs.py does (read it; do not edit it): 
  `nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)`, rename, drop, sort.
- `preds = candidate_preds(frame, list(range(2012, 2026)))`, then
  `evaluate(preds, {"inseason_refit": ["p_inseason"]}, tune=list(range(2012, 2022)), confirm=list(range(2022, 2026)))`.
- Print one JSON document (indent 1) to stdout: `{"games": len(preds), "baseline": {"market": summarize(...), "blend":
  summarize(...)} for all seasons, "baseline_confirm": the same two on the confirm seasons, "candidates": the evaluate
  result}`. No file writes, no arguments, no new network code: only `nflverse.fetch_csv`. A download failure must
  raise (do not catch it).

FAILING EVIDENCE:
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15442/nflpi_codex uv run pytest -q tests/test_model.py

PROOF (must pass; never run pytest without that DATABASE_URL: the default points at a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15442/nflpi_codex uv run pytest -q tests/test_model.py
cd backend && uvx ruff check nflpi tests ../docs/gauntlet/logs/step-14-evidence/candidates.py
Do not run the full suite (it takes 25 minutes tonight); the coordinator runs it.

CONSTRAINTS:
- Smallest correct diff. No new dependency. No class, registry, config or plug-in layer: plain functions.
- Match the surrounding code: typed signatures, one-line docstrings where the file has them, ruff line length 120.
- Do not mutate a caller's DataFrame (copy before assigning columns, as `predict_season` does).
- No print or logging in the two modules.

DO NOT:
- edit tests, jobs.py, engine.py, features.py, the API, or anything outside ALLOWED SCOPE
- commit, push, or touch any container or port other than the test database URL above
- change BASE_FEATURES, BLEND_FEATURES or the output of run_backtest

RETURN:
- changed files
- a short summary
- the two proof command results (the pytest summary line and the ruff line)
- any blocker
