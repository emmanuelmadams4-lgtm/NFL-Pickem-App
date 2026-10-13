# Reader report: nfl-4th-down-ml-model

Read-only inspection by a subagent on 2026-10-13 (nothing in the repository was run, imported or installed). The coordinator checked the commit and the license against the clone; other claims are the reader's, cited to files in that clone.

**Verdict:** The repo is a 2022 college course project. It classifies the historical 4th-down play type (punt / field goal / go-for-it) from in-game state. It does not model optimal decisions, and it has nothing pregame or team-level. Nothing was run.

**1. COMMIT:** `51dd37d0b23c6db4625cc652f1990400cff96328`, committed 2022-04-24T11:09:51-04:00.

**2. FILES** (tracked, 23 files):
- `data/2003.csv` to `data/2021.csv`: 19 play-by-play CSVs, 2.5 MB to 7.7 MB each, about 130 MB total. No pickled or serialized model files.
- `data_processing_and_ml_models.ipynb`: 8,694,009 bytes.
- `data_scraping.ipynb`: 16,797 bytes.
- `README.md`: 2,689 bytes. `LICENSE`: 1,069 bytes.

**3. LICENSE:** `LICENSE`, MIT. First line: "MIT License", copyright 2022 Connor Cozad.

**4. VERIFIED CAPABILITIES:**
- **Predicted target:** the play type actually called (Field Goal / Punt / Go For It), inferred from the play description text. `data_processing_and_ml_models.ipynb` cell 21. The model is not win-probability-optimal. The README's "chooses the best play" (`README.md:15`) is a mislabel.
- **Training filter:** only successful 4th-down plays are kept (cells 19, 23, 26). Punts are always "successful" (cell 23).
- **Model and library:** seven sklearn/xgboost classifiers compared (cells 67–86, 91). Final model is `xgb.XGBClassifier` with `n_estimators=30, max_depth=6, colsample_bytree=0.8, subsample=0.7, learning_rate=0.3` (cell 120).
- **Features:** all in-game state (cells 29–41, 61): Postseason, possession team is home, possession team score difference, both scores, minutes to end of game, yards to first down, yards to end zone. No team identity, no pregame data.
- **Data source and seasons:** ESPN play-by-play scraped by BeautifulSoup (`data_scraping.ipynb` cells 6–14), seasons 2003–2021 (`README.md:9`, files in `data/`).
- **Split:** random 60/20/20 train/validation/test via `np.split(plays.sample(frac=1), …)` (cell 59). Not time-ordered, so later seasons leak into training.
- **Stated accuracy:** recorded outputs show validation accuracy of 0.867 for the tuned XGBoost (cell 93 shows 0.867 for XGBoost, the 87% figure); test accuracy is 0.867 with per-class F1 of 0.770 (field goal), 0.637 (go for it), 0.933 (punt) (cells 121, 126). Hyperparameters were tuned on the validation set (cells 101–117), so the validation number is optimistic.

**5. PREGAME USE:** No. The model classifies a single in-game play from state variables. Nothing produces a team-level or pregame aggressiveness rate. Team identity is never a feature, and "Possession Team is Home" is the only team-related feature (cell 29).

**6. DEPENDENCIES:** No requirements file, lockfile or environment file. The README (line 24) lists pandas, numpy, seaborn, matplotlib, sklearn, xgboost and jupyter, unpinned. Imports in the notebooks: bs4, requests, pandas, numpy, seaborn, matplotlib, xgboost, sklearn. Versions: UNVERIFIED.

**7. RISKS:**
- Label is play-called, not decision quality. A high accuracy means agreement with historical coaching choices, which is not a fourth-down decision recommendation.
- Data path mismatch: the notebook reads `Play by Play CSVs/{year}.csv` (cell 7), but the files live in `data/`. Running as written fails unless the path is changed. The scraper writes to `Final Project/Play by Play CSVs/` (cell 18).
- Random split leaks future seasons into training; no walk-forward validation.
- The scraper targets ESPN pages from 2022 and is likely broken now (UNVERIFIED: not tested).
- No pickled models bundled, so no unsafe-load risk. Not run; nothing executed.
