# Reader report: nfl-modeling

Read-only inspection by a subagent on 2026-10-13 (nothing in the repository was run, imported or installed). The coordinator checked the commit and the license against the clone; other claims are the reader's, cited to files in that clone.

1. COMMIT: `79596b14f8138e83ad948a98191f02cf8c8d007c`, 2025-09-01T11:16:33-05:00.

2. LICENSE: `LICENSE` states "nfl-modeling is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License" (LICENSE:3-4). `pyproject.toml` has no license field. CC BY-NC-ND forbids derivatives, so you can't copy or adapt the code. Use it only as a source of ideas.

3. VERIFIED CAPABILITIES
- **Target:** binary win/loss only. `result > 0` becomes `target` (`src/data/build.py:239`). It makes no spread, total, or score-distribution output, and no simulation. README.md:5 calls it "well-calibrated probabilities".
- **Games kept:** regular-season games from week 5 onward (`build.py:30-46`). It reads them from the nflverse `games.csv` (`src/config/config.py:34`).
- **Data source:** nflverse games.csv, plus a local SQLite file of Pro-Football-Reference boxscores built by a scraper (`src/data/pfr/tables.py`, `data/boxscore-stats.db`). I found no `nfl_data_py` or `nflreadpy` use in `src`, `requirements.txt` or `pyproject.toml`.
- **Models** (`src/model/estimators.py`): logistic regression baseline with elastic net (`spaces.py:17-21`), LightGBM and NuSVC. All three are wrapped in `CalibratedClassifierCV(cv=3)` (estimators.py:34, 48, 64).
- **Baseline features** (estimators.py:25-27): `log5_pyexp`, `rest_net` and `obj_team_is_home`.
- **Feature engineering in the build** (`build.py:218-231`):
  - `rest_net` (home minus away rest).
  - Opponent-adjusted yards per play (`play_stats.py:17-34`).
  - Pythagorean expectation with exponent 2.77, converted to log5 (`pythag_exp.py:75, 80-110`).
  - QB passer rating from the starter's last 50 games (`qb_stats.py:14-17, 66-79`). The starter comes from the PFR starters table. The feature is starter rating minus opponent starter rating.
- **Opponent adjustment** (`src/data/features/scaler.py:160-210`): the team's raw stat minus the average that opponents posted against their other opponents. Rolling window is 20 games, grouped by team and season (scaler.py:98, 107-117).
- **Evaluation split:** `mlxtend` `GroupTimeSeriesSplit` over seasons, with train 10, test 3 and shift 2 (`config.py:48-50`, `evaluate.py:75-88`). The final holdout is seasons 2022 and later (`config.py:42`, `build.py:244-245`).
- **Calibration:** sigmoid calibration, either the `CalibratedClassifierCV` default or an unverified setting. Calibration plots are produced (`train.py:95`).
- **Tuning:** hyperopt TPE, minimizing negative Brier score (`hyperoptimize.py:95-101`, `config.py:47`). The search runs `MAX_EVALS = 15` evaluations (`config.py:51`).
- **Not found, so not claimed:** EPA, Elo, SRS, Massey or Bradley-Terry ratings, weather, market lines, QB-change flags, and a travel feature. `config.py:56` has only a stale travel precision entry. The README says EPA is avoided on purpose to prevent "data leakage" (README.md:40-42), which is a questionable claim.

4. LEAKAGE OR METHOD RISKS
- **Current-game exclusion** works by shifting each team's features one row back within the season (`src/utils.py:73-91`, with `.shift(1).over(["team","season"])`). The join is then on the next row, not the same week (`utils.py:123-142`).
- **Season boundary:** the shift is per season, so week 1 has a null shift. Weeks 1-4 are dropped (`build.py:41`), so every season starts with at most about 4 games of history.
- **Bye weeks are not handled in the shift.** The shift is by row, not by week number. The docstring says it is "consistent with the bye weeks" (utils.py:76-78), but that is not what the shift does. The window is also row-based, which carries the same bye-week issue.
- **Opponent average includes the same-season future (`scaler.py:126-136`).** The opponent aggregate is computed over the opponent's window ending at the current index, and the current game is only subtracted out as a residual (`scaler.py:194-195`). This is hard to audit, and I did not trace it fully. I would call it UNVERIFIED rather than a confirmed leak.
- **Missing QB data is filled with the mean.** `fill_null(strategy='mean')` fills the null with the mean of the whole column (`qb_stats.py:99, 119`), which uses future data. `qb_rating_net` also fills nulls with 0 (`qb_stats.py:141`).
- **Scrambled row order for the final fit:** `train.py` rejoins train and test (`train.py:97-99`), which is fine. But `season` is in the frame and `GroupTimeSeriesSplit` relies on it as the group.
- **Calibration inside CV:** `CalibratedClassifierCV(cv=3)` uses unshuffled stratified folds, not time-ordered ones (estimators.py:34 and similar).
- **Tuning on the same CV used to report scores:** hyperopt runs on the training CV (`train.py:78-85`), and the same CV's scores are then reported, which is optimistic.
- **Small tuning budget:** 15 evaluations over a 15-dimensional LightGBM space is thin (`config.py:51`, `spaces.py:22-38`).
- **Bug:** `train.py:96` uses the global `name`, not `model_name`.
- **Object/adversary swap:** `transform_home_away` uses `gather_every(2)` on a sorted frame (`build.py:57-74`), which assumes game ids pair up cleanly. I did not verify this.

5. DEPENDENCIES
- Python >=3.13 (`pyproject.toml`), with 3.13 in `.python-version`.
- `requirements.txt` pins: lightgbm 4.6.0, mlxtend 0.23.4, numpy 2.3.2, pandas 2.3.2, polars 1.32.3, scikit-learn 1.7.1, hyperopt 0.2.7.
- `pyproject.toml` also lists beautifulsoup4, joblib, matplotlib, pyarrow, seaborn, sqlalchemy, sphinx and furo.

6. TECHNIQUES WORTH TESTING
- **Pythagorean expectation with log5** (`pythag_exp.py:75, 80-110`, exponent 2.77). Cheap and independent of EPA. It is untested in your bench as a feature, and it is the author's strongest baseline feature.
- **Opponent-adjusted rolling rate with a league-mean fallback** (`scaler.py:160-210`). It is a method rather than a stat. You could apply it to your own rated stats, with the leakage caveat above.
- **Grouped season time-series CV with multi-season test blocks** (`evaluate.py:75-88`). Your bench already walks forward by season, so this adds little.

7. STATED RESULTS: none. README.md:34-36 reads "Is your model any good? ... Probably not." I did not read the `data/results` files, which are not in the tree.

Verdict on the brief's claim "advanced feature engineering": not supported. The code has four simple features (rest, adjusted yards per play, Pythagorean expectation, QB passer rating) and no ratings, EPA, market or weather inputs. Your bench already covers more.
