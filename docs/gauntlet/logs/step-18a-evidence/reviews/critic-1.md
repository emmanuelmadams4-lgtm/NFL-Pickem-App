# Critic 1: ecc:mle-reviewer, no build transcript, on d2a6f7b (the commit before the branch was moved onto main 589aa3b; same content as 8e8670e)

**Verdict: FAIL.** One rule is broken: two HYPOTHESIS claims are restated as fact elsewhere in `AUDIT.md`. Everything else I checked passes.

**1. Six VERIFIED findings re-derived**
- **A9 CONFIRMED.** In `audit-numbers.json`, market is 0.6657 and 0.6094, and blend is 0.6646 and 0.6107. Blend over market is -0.0013 with interval [-0.0030, +0.0003]. The clustered interval is [-0.0029, +0.0004].
- **A10 CONFIRMED.** `blend-vs-market.txt` shows 72 of 3,649 picks differ (1.97%). The blend was right in 34 of them. The correlation is 0.993. The weights are 1.0316 on the line and 0.0161 on Elo.
- **A4 CONFIRMED.** I checked all ten deciles: the stated chance sits inside the observed 95% interval in every one. The gaps match the table. Slope is 1.0176 and intercept 0.008.
- **A6 gap CONFIRMED.**
  - `backtest.py:5-6` says the market line is the closing line.
  - `engine.py:53-57` takes the newest snapshot id per game with no time filter.
  - `service.py:88-102` sets `kind = "closing"` from game status, not from the clock.
  - `feeds-extra.txt` shows lines for weeks 6 and 7 only (14 + 14).
- **A8 CONFIRMED.** `share_with_both_qbs` is 1.0. For 2026, 79 of 79 finished games carry a name, and 14 of 193 unplayed games do (week 6 only).
- **A2 and A3 line citations CONFIRMED.** `features.py:11-13`, `:115`, `:118`, `backtest.py:58`, `engine.py:103-109`, and `jobs.py:56` all say what the findings claim. The A2 test passes (item 4).
- **A13 and A14 arithmetic CONFIRMED.** 3,663 - 13 - 1 = 3,649. Home spread above zero: 2,284 games, and the home moneyline is negative in 2,283.

**2. HYPOTHESIS entries: two are restated as fact (FAIL)**
- Each HYPOTHESIS (A6 twice, A8 once) names a settling test.
- A6 says "HYPOTHESIS: live accuracy is below the bench's 66.5% because of this."
- A8 says "HYPOTHESIS: ... flatters the bench."
- Yet the AUDIT.md summary, point 4, says "Two things make the bench kinder than real life". That is the same claim, stated as fact.
- The A5 "Realistic cutoffs" paragraph says "The bench's 66.5% is therefore an upper estimate of what a mid-week pick earns". It is also stated as fact.
- The A8 line "How much it could matter: little" is an inference, not a measurement.
- Fix: reword both places to "may be kinder", or relabel them as HYPOTHESIS and cite the settling test.

**3. REPOS.md against the clones: all six rows correct**

| Repository | SHA and date | License | Capability spot-check |
|---|---|---|---|
| nflreadpy | match (2026-09-09) | MIT (`LICENSE.md`, `pyproject.toml`) | Six dependencies and Python >=3.10 match. `load_schedules`, `load_pbp`, and `load_depth_charts` exist, and the code imports polars. |
| nfl-analytics | match | no license file, no license field in `pyproject.toml` or `README.md` | `benchmark.json` is present. Four workflows are present. `LinearRegression` appears only in `tests/test_runs.py` in the lines I printed, so the "scikit-learn LinearRegression" model claim is not fully confirmed. |
| nfl-predictions | match | no license file; README says "educational and research purposes" | `rest_days = 7` is at `feature_engineer.py:337`. The whole-season win rate for `home_team_strength` is at `:296-307`. `log_loss` is at `model_trainer.py:223`. |
| NFL-Prediction | match | no license file or README text | `CalibratedClassifierCV` and `VotingClassifier` are in the notebook, and so is `over_line`. |
| nfl-modeling | match | `LICENSE` is CC BY-NC-ND 4.0 | Exponent 2.77 is at `pythag_exp.py:75`. `CalibratedClassifierCV(cv=3)` is at `estimators.py:31`. |
| nfl-4th-down | match | MIT, Connor Cozad 2022 | XGBoost is present in the notebook. |

**4. Test run.** The command printed `6 passed in 20.84s`.

**5. R4 clauses**
- **S1.**
  - Bench test: killed M7. Live test: killed M1.
  - The live test includes a control that an earlier result does change the prediction.
  - Blind spot, advisory: both tests swap home and away scores, so the sum of the two scores never changes. A leak through total points would pass. Both planted defects (M1, M7) use `home_score` alone.
- **S2.** The parity test killed M2 and M6. M1, M7, M3, and M9 also trip it.
- **S3.** The bench test killed M3 and M4. The live test killed M5 and M9.
- **S4.** The line-timing test killed M8 and M9. No planted defect targets "live uses a line stored before kickoff". That assertion reads from `load_frame`, which has no as-of filter (the audit says so in A7). It only fails if the fixture contains a late line. The fixture contents were not checked. This is advisory, not a missing test, because M8 does kill the clause as a whole.
- The log has all nine planted defects KILLED, with `ok: true` and `files_left_changed: false`.

**6. PLAN.md**
- **Citations.** `engine.py:243` is the pick. `elo.py:17` is `revert = 1/3`. `metrics.py:8` is `EARLY_WEEK_END = 4`. `backtest.py:325-326` is the same-games filter. `weather.py:15` is `STADIUMS`. All five check out.
- **Section 3.** Section 3 says it was written before the cover and totals models were scored. It is a proposal for cover and totals, but D18 is unchanged and the step 9 rule is kept. This is acceptable.
- **Section 4.** Every 2026 number matches `audit-numbers.json` or `feeds-extra.txt`: 272 games, 79 finished, 193 unplayed, 28 with lines, 14 with a quarterback name, 158 team rows, 1,413 injury rows, and the file update times. I did not check the 1,413 injury-row count or the "weeks 1 to 5" claims against a raw file. They come from `feeds-extra.txt`.

**7. Step log**
- The five commits in `11cc401..d2a6f7b` exist.
- The evidence files exist: `reviews`, `repos`, `wo-1.md`, `wo-1b.md`, `gate.sh`.
- The T1 assumptions table is present, with validated, assumed, and unknown entries.

**Advisories**
- SPECIFICATION says "eight planted defects", but nine exist after M9.
- The S1 sum-of-scores blind spot (item 5).
- The S4 "before kickoff" assertion rests on fixture data (item 5).
- The nfl-analytics "LinearRegression" model claim lacks a ✔. I did not see it in `src`.

Key files: `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-audit/docs/model/AUDIT.md` (summary point 4, and the A5 "Realistic cutoffs" paragraph).
