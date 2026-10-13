# Reader report: nfl-analytics

Read-only inspection by a subagent on 2026-10-13 (nothing in the repository was run, imported or installed). The coordinator checked the commit and the license against the clone; other claims are the reader's, cited to files in that clone.

1. COMMIT: `9267a968afc7796c0c839c9347bc8ec5da84a15d 2026-09-30T16:23:02-04:00`

2. LICENSE: no license file. No license field in `pyproject.toml` (lines 1-35) and no mention in `README.md`. A grep for "license" in both returned nothing. With no license, the code is all-rights-reserved by default.

3. VERIFIED CAPABILITIES
- **Target:** Home-team point spread, as a regression. It does not predict winner or total. `home_spread` is the home margin (`nfl_analytics/dataframes.py:137-141`; `model.py:32`). `pyproject.toml:4` describes it as "CLI app for predicting NFL spreads". The winner is only implied by the sign.
- **Model:** sklearn `LinearRegression` on `StandardScaler`-scaled features (`model.py:44-48`). One row per game (`drop_duplicates`, `model.py:39`).
- **Features:** 14 columns, home/away running averages of rushing yards, passing yards, sack yards, score differential, points scored, points allowed and mean EPA (`config.py:26-41`).
- **Rolling features:** `grouped[stat].shift()` then cumsum, with the comment "shift so the current game is excluded" (`dataframes.py:146-148`). Early-season averages blend 4 pseudo-games of the prior season's mean (`config.py:5-8`, `dataframes.py:152-159`). The docstring at `dataframes.py:96-100` states the current game is excluded.
- **Split:** Chronological by season. `evaluate.py:46-47` trains on `year < test_since` and tests on `year >= test_since`. The default is 2023 (`evaluate.py:33`), and the committed benchmark tests 2023-2025 (`config.py:15`).
- **Backtest:** Walk-forward by week. It retrains on games from earlier seasons or earlier weeks only (`backtest.py:52-58`), from 2021 (`config.py:23`).
- **Calibration:** Diagnostic only, a slope and intercept of actual on predicted (`evaluate.py:85-88`). No calibrator is applied. It also reports a bootstrap MAE interval (`evaluate.py:92-95`) and a gap-closed measure against Vegas (`evaluate.py:110`).
- **CLI:** Entry point `nfl = nfl_analytics.main:main` (`pyproject.toml:15-16`). `README.md:53-63` lists the commands: update, predict, predict-upcoming, download, train, evaluate, backtest, benchmark, run-pipeline.
- **Data source:** nflverse play-by-play CSVs downloaded over HTTP from `github.com/nflverse/nflverse-data/releases/download/pbp/` (`data.py:58,79`). It uses neither nfl_data_py nor nflreadpy. `START_YEAR` is 1999 (`config.py:3`).
- **Artifacts:** Each run goes to `assets/runs/<run_id>/`. The model is saved as plain JSON parameters, not a pickle (`runs.py:8,18,65`). There is also a manifest holding git SHA, `uv.lock` hash and data SHA-256 hashes (`provenance.py:17-60`, `runs.py:77`), a running-average CSV and `ledger.csv` (`config.py:17-24`).
- **Benchmark snapshot:** `nfl_analytics/benchmark.json` is committed and compared on every run (`README.md:71-78`).
- **Automation:**
  - `.github/workflows/train-spread-predictor.yaml` runs on cron Tuesday and Wednesday 10:00 (lines 14-15). It runs tests, then `nfl run-pipeline` (line 80), then builds release files and attests provenance (line 146). It opens a failure issue on error (line 171).
  - `benchmark.yaml` runs `nfl benchmark`, and `test.yaml` runs pytest.
  - `pages.yaml` is a Pages deploy; I only read its description in the README (`README.md:103`).
  - The README says immutable releases are published weekly and previously published predictions are graded in `ledger.csv` (`README.md:84-95`). The grading behaviour is README only; I did not read `ledger.py`, so UNVERIFIED in code.
- **Tests:** 13 files in `tests/`.

4. LEAKAGE OR METHOD RISKS
- **Mid-season leakage possible:** Rows are sorted by `week` and `year` within team (`dataframes.py:114`), so playoff rounds are treated as ordinary weeks. This is not a leak. I found no filter on regular season versus playoffs, and `model.py:166` notes the Super Bowl has no true home team. This is minor label noise.
- **Final model has no holdout:** The published model trains on all seasons (`model.py:29-31`). Honest numbers come only from `evaluate` and `benchmark`.
- **Prior-weight tuning:** `PRIOR_PSEUDO_GAMES = 4` was "chosen empirically via `nfl evaluate`" (`config.py:5-8`). That evaluate run scores 2023 onward, which is the same window as the benchmark. This is mild test-set tuning.
- **Vegas line as benchmark only:** `spread_line` is not in `FEATURES` (`config.py:26-41`), so there is no market leakage.
- **No random splits found.** The `benchmark.json` ATS figure is below breakeven.
- **Not checked:** The `fillna(0)` in `dataframes.py:149` and `mean_epa` computed from whole-game plays. Both use only prior games because of the shift, so I see no leak.

5. DEPENDENCIES
- Runtime (`pyproject.toml:8-13`): `pandas>=2.2.0`, `scikit-learn>=1.4.0`, `numpy>=1.26.0`, `scipy>=1.12.0`. These are lower bounds, not exact pins. `uv.lock` pins the exact versions; I did not read it.
- Python: `requires-python >=3.12` (line 7), and `.python-version` is `3.12`.
- Dev: `ipykernel>=6.29.0`, `pytest>=8.0.0`.

6. NOT FOUND
- Pipeline organization, CLI workflows, automation and model artifact management are all present.
- Spread modeling is present, but the model is a plain linear regression.
- No winner or moneyline model. No probability output (the calibration check is about margin, not win probability). No injury, weather or QB features.

7. STATED RESULTS (author's claim, not verified)
- `nfl_analytics/benchmark.json:8-12`: MAE naive 11.1556, model 10.2987, Vegas 9.8117, with `gap_closed` 0.6376 and `ats_accuracy` 0.4892. This is for 6400 training and 855 test games, 2023-2025.
- `nfl_analytics/docs/model.md:3`: "mean absolute error ... is about 10.3 ... Vegas closing spread ... 9.8 ... Its against-the-spread pick accuracy is below the ~52.4% betting breakeven, as expected: real signal, no edge."
