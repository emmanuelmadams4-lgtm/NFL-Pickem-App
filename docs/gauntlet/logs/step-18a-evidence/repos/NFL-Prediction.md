# Reader report: NFL-Prediction

Read-only inspection by a subagent on 2026-10-13 (nothing in the repository was run, imported or installed). The coordinator checked the commit and the license against the clone; other claims are the reader's, cited to files in that clone.

1. **COMMIT:** `62e4b3fbbaceda3d50eb1abc6fc23f9b655164b3 2023-01-11T09:29:10-08:00`

2. **FILES** (tracked, bytes):
- `.gitignore` 3
- `Data/nfl_games.csv` 3,651,628
- `Data/nfl_teams.csv` 2,525
- `Data/spreadspoke_scores.csv` 1,384,996
- `Machine_Learning_Final_Project.pdf` 216,132 (not read; UNVERIFIED)
- `NFL Analysis.ipynb` 251,335
- `README.md` 1,274

3. **LICENSE:** no license file. README and notebook contain no license statement.

4. **VERIFIED CAPABILITIES**
- Predicts whether the home team wins: `NFL Analysis.ipynb` markdown cell (Table of Contents, ~L7-9).
- Models: DecisionTree, LogisticRegression, XGBoost (`xgb.XGBClassifier`, ~L619-620), RandomForest (~L642-644), tuned with hyperopt (~L704). Final model is `LogisticRegression(C=0.1)` (~L1037).
- Ensemble: yes. `VotingClassifier(voting='soft')` over XGB, LR, RF (~L1038).
- Calibration: yes. `CalibratedClassifierCV(vote, method='isotonic', cv=3)` (~L1033, ~L1040), then `predict_proba` (~L1050). No Brier, log-loss or reliability metric found.
- Features: pre-game Elo probabilities (`pred_home_win`, `pred_homeQB_win`), Elo and QB values, weather, playoff/neutral flags, `over_line`, plus QB differentials (~L179-198, ~L381-396).
- Data: fivethirtyeight NFL Elo games and a Kaggle betting/scores file (~L61-63, ~L84-95).
- Split: the final model trains on seasons <2019 and tests on 2019 (~L187-188), which is chronological. The early split at ~L274 is `shuffle=True`, random.

5. **LEAKAGE OR METHOD RISKS**
- `over_line` is derived from final scores, `(score_home + score_away) > over_under_line` (~L124-126), yet it is a model input: RFE selects it (~L381) and it is in `selected_cols` (~L690-693).
- The random shuffled split (~L274) covers all seasons, including 2019. RFE is fit on it (~L389-390), so the 2019 test rows influence feature selection.
- Model comparison uses random repeated CV over all seasons (~L297, ~L424ff). It is not walk-forward.
- The betting thresholds 0.60/0.40 are fixed in code (~L1062-1063) and evaluated on one season only (~198 bets).
- Weather NaNs are filled with the mean of the full column before splitting (~L168-172).
- `qb1_relative` is built from `qb1_game_value` (~L174). Whether that value is post-game cannot be confirmed from the repo: UNVERIFIED.
- Inconsistent training start: 1990 (~L61), 1980 (~L681), and seasons 1966-1979 removed (~L156-157).
- `StandardScaler` is imported (~L49) but never used.

6. **DEPENDENCIES:** pandas, numpy, matplotlib, scikit-learn (model_selection, linear_model, preprocessing, feature_selection, discriminant_analysis, pipeline, tree, ensemble, calibration), xgboost, hyperopt, warnings. No requirements file. Only `.gitignore` is present besides data and notebook.

7. **NOT FOUND:** calibration is present; ensembling is present. No stacking, no averaging ensemble, no log-loss or Brier evaluation.

8. **STATED RESULTS (author's claims, not verified):**
- README abstract: "placed 207 bets out of the possible 251 games and won 170 of those bets. This resulted in a win percentage of 82.13%." These figures do not appear in the notebook.
- Notebook output (~L1075-1077): "Model Win Percentage: 0.8182", "Total Number of Bets Won: 162", "Total Number of Bets Made: 198" (251 possible games).
- Given the leakage above, the 2019 result is not evidence of a usable edge.
