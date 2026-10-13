# Critic 2: a new ecc:mle-reviewer, no build transcript, delta brief, on 639f430

**Verdict: PASS**

**1. R1 in AUDIT.md, PLAN.md and the step log top.**
- (a) is fixed. Summary point 4 now reads "that may make the bench kinder; whether it does, and by how much, is not shown and cannot be sized from history". It splits "Shown" from "Not shown (two hypotheses…)".
- (b) is fixed. The Question 5 paragraph now says "is the HYPOTHESIS of A6 and A8, not a measured fact".
- (c) is fixed. A8's "little" is gone. The replacement, "A bound on the size, not a measurement of it", ends with "How much of the 0.0028 would survive… is the HYPOTHESIS above."
- Summary line 1 and the "measured reason" paragraph rest only on A9 and A10. I checked the numbers against `audit-numbers.json`:
  - `baselines.all` has market 0.66566 and 0.60943, and blend 0.66457 and 0.61070.
  - `paired.all.blend_vs_market` has a log-loss gain of -0.00127 with 95% interval [-0.00304, +0.00033], and a week-clustered interval of [-0.00288, +0.00038]. Both intervals include zero.
  - `blend-vs-market.txt` shows 72 differing picks (1.97%), the blend right in 34 of them, and a correlation of 0.993.
  - The "stats inputs add nothing measurable to the line" wording matches those numbers.
- The grep of PLAN.md and the step-log top found no hypothesis stated as fact. PLAN line 169 says "cannot be measured from history", and the step log's QB assumption says "unknown… HYPOTHESIS".
- I found no sentence that explains weak performance without evidence.

**2. Test change.** The diff touches only `SHIFT = 3`, `_flip_scores` and `_swap`. Each now swaps the two scores and adds 3 to each, so the winner, margin and total all change. Both S1 tests are unchanged in the diff, so they still assert that the game's own features and probability are unchanged. Nothing else was weakened.

**3. Mutation log.**
- All ten (M1 to M10) are KILLED, with `"ok": true` and `"files_left_changed": false`.
- M10 is killed by both `test_bench_features_and_probability_ignore_the_games_own_and_later_scores` and `test_live_features_and_probability_ignore_the_games_own_and_later_scores`.
- M10 exercises clause S1, on the bench and live paths.
- M9 (live fit window reaches into the predicted season) exercises S3 on the live path, through `test_live_model_is_fitted_only_on_seasons_before_the_one_it_predicts`. It is also caught by the S2 parity test and the S4 live-pick test, because the live weights change.

**4. Test run.** The exact command printed `6 passed in 5.72s`.

**5. Citations.**
- `jobs.py:56` is `engine.train(session, through_season=season - 1)`.
- `jobs.py:67-75` reads `schedules/games.csv`.
- `models.py:380` is `class QbObservation`.
- `config.py:21` is `nflverse_base`.
- `git diff --stat c55827f 589aa3b -- backend/nflpi/predictions backend/nflpi/analytics backend/nflpi/ingestion` printed nothing.

**6. BlairCurrey claim.** Confirmed. `model.py` imports `LinearRegression` and `StandardScaler`, calls `scaler.fit_transform(df_train[FEATURES])` at line 45 and builds `LinearRegression()` at line 47.

**7. Step log.**
- "Eight planted defects" is gone. The log says "ten by the end: M1 to M10".
- Every commit hash the log names (`589aa3b`, `5b796ae`, `76b9c4d`, `b0fdc07`, `bb3c5d6`, `c55827f`) exists in the repo.
- `git log` shows five commits on top of the base. I did not check which commit each section names, only that the hashes exist.

**Advisories (none affect the verdict):**
- The A4 claim "pulls it toward zero by well under 0.01" (line 95) is not backed by a cited command.
- The A4 claim "The larger gap is what groups of 108 games give by chance; it is not evidence of drift" (line 96) is stated as fact. It is also unmeasured, though it does not explain model performance.
- The A10 inference "an added input changes a pick only where it disagrees with the closing line strongly enough to cross 50%" is labelled as a reading rather than a measurement. That is acceptable, but it could say "should".
- The mutation log's M6 line is printed last in the summary. That is only an ordering quirk.
