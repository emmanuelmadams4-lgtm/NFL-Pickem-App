# Work order 1 (step 18a): two evidence scripts

Builder: Claude Sonnet subagent (Codex refused: "The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account", probe log `~/.claude/plans/nfl-pickem-lanes/logs/step-18a-codex-probe.log`).

GOAL: write exactly two new files, both under `docs/gauntlet/logs/step-18a-evidence/`. Change nothing else.

BASELINE: worktree `.claude/worktrees/lane-audit`, branch `lane/audit`, base `c55827f`. `backend/tests/test_model_audit.py` passes (5 tests).

CONSTRAINTS: smallest correct code; standard library plus what `backend/pyproject.toml` already has (pandas, numpy, httpx); no new dependency; ruff clean at line length 120; no file under `backend/nflpi` or `backend/tests` is left changed; do not commit, push or run a full test suite; never set or print a key; the only network hosts are github.com (nflverse release files, through `nflverse.fetch_csv`) and api.github.com (release asset lists, no token).

## File 1: `audit_numbers.py`
Run as `cd backend && uv run python ../docs/gauntlet/logs/step-18a-evidence/audit_numbers.py > <out.json>`. Prints ONE JSON object (`allow_nan=False`, missing values as null). Model it on `docs/gauntlet/logs/step-14-evidence/candidates.py` for loading.
1. Load `schedules/games.csv` with `nflverse.fetch_csv`, `nflverse.parse_games(rows, 2002)`, build the bench frame exactly as `nflpi.jobs.backtest` does. Keep the raw rows for part 6.
2. `preds` = `predict_season(frames, s, 10)` for seasons 2012 to 2025 from `_elo_frames(frame)`, concatenated; then keep rows with `p_market` not null (the bench's rule).
3. `"baselines"`: for each period (`all` 2012 to 2025, `tune` 2012 to 2021, `confirm` 2022 to 2025) and each model in `home, elo, logistic, market, blend`: `metrics.summarize`. Plus `"paired"` for each period: `metrics.paired_gain(new, old, y)` for the pairs (blend, market), (blend, logistic), (logistic, elo), (elo, home), (market, logistic).
4. `"reliability"`: for each of `blend, logistic, market` and each period: ten equal-count bins of the HOME win probability (`pd.qcut(p, 10, duplicates="drop")`), each bin: `n`, `lo`, `hi`, `predicted` (mean p), `observed` (home win rate), `gap` (observed minus predicted), and a 95% Wilson interval of `observed` (`metrics.wilson_ci`). Also per model and period: `ece` (n-weighted mean of abs gap) and `slope`, `intercept` of a logistic fit of the result on the log-odds of p clipped to 0.01..0.99 (use `LogitModel.fit` on a one-column frame, as `backtest.calibrated` does). A slope below 1 means overconfident.
5. `"sample"`: games in `preds`; regular-season finals 2012 to 2025 in the frame; how many of those are ties (excluded because `home_win` is null); how many have no moneyline (excluded); games per season; share of `preds` rows with `home_qb` and `away_qb` present; rate of `home_qb_change` and `away_qb_change`.
6. `"season_2026"` from the raw games rows with season 2026: games, finals, latest `gameday` among finals, earliest `gameday` among non-finals, counts of non-final games that already carry a moneyline, a spread, a total, a `home_qb_name`; the same counts for finals; weeks covered by finals.
7. `"feeds"`: for each nflverse release tag in `schedules, pbp, stats_team, stats_player, injuries, snap_counts, weekly_rosters, depth_charts, players, nextgen_stats`: GET `https://api.github.com/repos/nflverse/nflverse-data/releases/tags/<tag>` with httpx (timeout 30, header `Accept: application/vnd.github+json`), and report the asset names that contain `2026` (or, for tags without per-season files, the main csv) with each asset's `updated_at` and `size`. On any HTTP error record `{"error": "<status or exception class>"}` for that tag and carry on; never invent a value.
8. `"run"`: UTC time of the run and `git rev-parse HEAD`.

## File 2: `mutate.py`
Run as `cd backend && DATABASE_URL=... uv run python ../docs/gauntlet/logs/step-18a-evidence/mutate.py`. For each mutation below: check the `old` text occurs exactly once in the file (else report `not-applied` and count it as a failure), write the mutated file, run `uv run pytest -q tests/test_model_audit.py -p no:cacheprovider` (subprocess, capture output), record the exit code and the names of the failed tests (lines starting `FAILED`), and ALWAYS restore the original bytes in a `finally`. Run the tests once unmutated first and require exit 0. At the end print one line per mutation (`KILLED` if at least one test failed, `SURVIVED` otherwise, with the failed test names), a JSON summary, verify `git diff --quiet -- nflpi` and exit 1 if any mutation survived, was not applied, or a file is left changed.
Mutations (path relative to `backend/`, `old` -> `new`):
* M1 own score leaks into a feature. `nflpi/predictions/features.py`: `out["elo_diff"] = (out["home_elo"] - out["away_elo"]) / 100` -> `out["elo_diff"] = (out["home_elo"] - out["away_elo"]) / 100 + out["home_score"].fillna(0) / 1000`
* M2 live path ignores the market. `nflpi/predictions/engine.py`: `        prob = model.predict_one(row)` -> `        prob = base_p`
* M3 the fit sees the test season. `nflpi/analytics/backtest.py`: `train_seasons = list(range(season - window, season))` -> `train_seasons = list(range(season - window, season + 1))`
* M4 the home rate is taken from the test games. `nflpi/analytics/backtest.py`: `home_rate = train.loc[train["home_field"] == 1, "home_win"].mean()` -> `home_rate = test.loc[test["home_field"] == 1, "home_win"].mean()`
* M5 the job trains through the current season. `nflpi/jobs.py`: `return engine.train(session, through_season=season - 1)` -> `return engine.train(session, through_season=season)`
* M6 live features differ from the bench. `nflpi/predictions/engine.py`: `    f = add_features(load_frame(session), EloParams(**p["elo"]))` -> `    f = add_features(load_frame(session), EloParams(k=40.0, hfa=0.0))`

PROOF (the coordinator reruns both): `uvx ruff check ../docs/gauntlet/logs/step-18a-evidence/*.py` clean; `mutate.py` exits 0 with six KILLED; `git status --short` shows only the two new files (plus what was already untracked).

RETURN: changed files, a three-line summary, the proof results you actually ran, any blocker.
