# Audit of the current model (owner brief, section 1)

Step 18a, lane `audit`, 2026-10-13. Code audited: main at `589aa3b` (the audit began at `c55827f`; the model, bench and ingestion files are identical in both). No model code was changed. Brief: `docs/model/OWNER_BRIEF_2026-10-13.md` section 1, read under owner decision D68.

## The answer in five lines

1. **The model is, in practice, the betting market's closing number.** Its pick differs from the market favourite in 72 of 3,649 games (2.0%), and it got 34 of those 72 right (A10).
2. **It is not broken.** No result leaks into a feature, the bench and the live path compute the same numbers, and every fit uses earlier seasons only. Ten planted defects were each caught by the new tests (A2, A3, A5, A6).
3. **It is well calibrated** (A4), and it clearly beats "always the home team" and "ratings only". It does **not** beat the market alone: 66.46% against 66.57%, a difference inside the noise (A9).
4. **The bench and real life differ in two inputs, and that may make the bench kinder; whether it does, and by how much, is not shown and cannot be sized from history.** Shown: the bench is scored on the closing line while a live pick is made from an earlier line (A6), and the bench has a quarterback name for every game while a live pick has one for the coming week only (A8). Not shown (two hypotheses, each with the test that would settle it): that either difference costs accuracy.
5. **The 2022 to 2025 check seasons have been scored nine times.** The only untouched games are the 2026 games not yet played (A11).

So the measured reason the model "is not good enough" is not a defect: its stats inputs add nothing measurable to the closing line (A9, A10). Nothing measured so far shows a way past the market; `docs/model/PLAN.md` says what will be tested next and how it will be judged.

## How to read this

* **VERIFIED** = the claim cites the code (file and line) **and** a test or a command with its output. **HYPOTHESIS** = not shown; the entry names the test that would settle it. No reason for weak performance is given without evidence.
* Tests: `backend/tests/test_model_audit.py` (six tests, written for this audit). Planted-defect check: `docs/gauntlet/logs/step-18a-evidence/mutation.log` (script `mutate.py`; M1 to M10 are its defects, ten of ten caught).
* Numbers: `docs/gauntlet/logs/step-18a-evidence/audit-numbers.json`, printed by `audit_numbers.py` on 2026-10-13 from the public nflverse schedule file. Walk-forward, 10-season window, 3,649 regular-season games with a closing line, 2012 to 2025. Its baseline equals the stored step 14 numbers (market log loss 0.6094, blend 0.6107).
* Other lookups: `blend-vs-market.txt` (script `blend_vs_market.py`) and `feeds-extra.txt`, same folder.
* Paths below are under `backend/nflpi/` unless they start with `tests/` or `docs/`.

Words. **Bench:** the walk-forward backtest (`analytics/backtest.py`): each season is predicted by a model fitted on the ten seasons before it. **Live path:** what the running app does (`predictions/engine.py`). **Blend:** the live model, the stats inputs plus the betting line. **Stats model:** the same without the line. **Closing line:** the last betting line before kickoff. **Log loss:** a score for probabilities, lower is better. **Interval:** a 95% paired-bootstrap interval.

---

## Question 1. What does the system predict, and how are picks chosen?

**A1. VERIFIED. One number per game, the chance the home team wins, from a logistic regression on five inputs; the pick is the side at 50% or more.**
* Inputs: the betting line as log-odds, the Elo rating difference, home field, and two "quarterback changed since last game" flags (`predictions/features.py:11-13`). Model: scikit-learn `LogisticRegression(C=1.0)` (`predictions/model.py:22`).
* With no line the stats model answers alone (`predictions/engine.py:240`). Pick: `engine.py:243`. The recommendation for a game is its last prediction row written before kickoff (`predictions/sheet.py:104-110`). Confidence points go out in order of win chance, highest first (`sheet.py:89-101`).
* Weights are fitted once per season on the ten finished seasons before it (`engine.py:103-109`, `jobs.py:56`); Elo keeps moving with results.
* Evidence: `tests/test_model_audit.py::test_bench_and_live_path_agree_on_features_and_probability`, `::test_live_model_is_fitted_only_on_seasons_before_the_one_it_predicts`. The weights a fit on 2016 to 2025 gives (what the 2026 season uses) are printed in `blend-vs-market.txt`: 1.03 on the line, 0.016 on the Elo difference.
* It does not predict a margin, a total, or the chance of covering a spread. A score estimate exists for the two tiebreak games only, read straight off the line (`predictions/scores.py:19-43`).

## Question 2. Do the bench and the live path build features the same way?

**A2. VERIFIED. Yes: same features, same probability, to the four decimals the live path stores.**
* Both call `add_features` (`predictions/features.py:115`; bench through `_elo_frames`, `analytics/backtest.py:51-60`; live at `engine.py:223`) and the same `LogitModel`.
* Test: `::test_bench_and_live_path_agree_on_features_and_probability` rebuilds the current season's finished games on the live path (`backfill_season`) and on the bench (`predict_season`) from the same fixture and compares all five inputs, the stats-only chance, the market chance and the final chance. Planted defects M2 (live ignores the line) and M6 (live uses other Elo settings) each make it fail.
* One weak spot, harmless today: the Elo difference is written in two places, `features.py:118` and `backtest.py:58`. They agree (this test), but a change to one alone would split the paths. Shown by the planted defects: M1 (change the first) breaks only the live path, M7 (change the second) only the bench; the test catches both.
* Two differences that are not errors: the bench scores regular-season games only (`backtest.py:95`), the live path predicts every game; the bench counts a pick as "home" above 50%, the live path at 50% or more.

## Question 3. Does anything use information not known before kickoff?

**A3. VERIFIED. Results do not leak. Changing a game's own final score, and every later score, changes neither its features nor its probability, on either path.**
* Elo records the rating before it applies the result (`predictions/elo.py:43-53`); the quarterback flag compares with the previous game (`features.py:100-112`).
* Tests: `::test_bench_features_and_probability_ignore_the_games_own_and_later_scores` and `::test_live_features_and_probability_ignore_the_games_own_and_later_scores`. The live test also checks the opposite: changing an **earlier** result of one of the two teams does write a new prediction row, so the test is not blind. The rewrite swaps the two scores and adds 3 to each, so the winner, the margin and the total all change. Planted defects M1 and M7 (the game's own score added to a feature) and M10 (the game's total points added to a feature) are caught.

**A6. VERIFIED that the gap exists; HYPOTHESIS how much it costs. The bench uses the closing line; a live pick uses whatever line was last seen before it was made.**
* Bench: "The market line is the closing line" (`backtest.py:5-6`), read from the nflverse schedule file (`jobs.py:67-75`).
* Live: the newest stored line for the game (`engine.py:53-57`), which for an unplayed game is the line in the nflverse file at our last download, stored with our own download time and marked `latest` (`ingestion/service.py:88-102`).
* The live model's own weights are fitted on finished games, so on closing lines (`engine.py:103-109`), then applied to that earlier line.
* Test: `::test_live_pick_uses_the_line_seen_before_kickoff_and_a_rebuilt_pick_the_closing_line` (planted defect M8 is caught).
* What the live path has on 2026-10-13 (`feeds-extra.txt`): the file carries a line for the 28 games of weeks 6 and 7 and for no later week.
* HYPOTHESIS: live accuracy is below the bench's 66.5% for this reason. **Settled by:** at the end of the 2026 season, score the last live row before kickoff against the rebuilt closing-line row (`Prediction.kind` `live` against `backfill`) on the same games; the step 13a report gives each line's age. It cannot be settled from history: no file says what the line was days before a past game.
* HYPOTHESIS: some stored lines marked `closing` were last seen long before kickoff, because the mark follows the game's status, not the clock (`service.py:88-91`). **Settled by:** counting `market_snapshots` rows with `kind = 'closing'` and `observed_at` more than a day before kickoff in the live database, which this lane may not open.
* Not checked: where nflverse takes its line from and at what time.

**A7. VERIFIED. The live loader has no "as of" time: it takes the newest line and the current quarterback name, whenever they were seen.**
* `engine.py:53-57` picks the highest snapshot id per game with no time filter; `games.home_qb` is overwritten on every download (`ingestion/service.py:56-72`).
* This is safe for a pick made now, because only unplayed games are predicted (`engine.py:229-230`) and results cannot leak (A3). The cost is that a past pick cannot be rebuilt as of an earlier moment: a rebuilt row always gets the closing line and is labelled `backfill` (`engine.py:329-347`).
* Tests: the A6 test above (rebuilt rows carry `closing`); `tests/test_model.py::test_backfill_labels_rows_and_needs_an_earlier_model`.

**A8. VERIFIED that history holds one quarterback name per game with no time attached; HYPOTHESIS that this makes the bench look better than a live pick could be.**
* The flags come from nflverse's `home_qb_name` and `away_qb_name` (`ingestion/nflverse.py:167-168`, `features.py:100-112`).
* Command output: in the bench both names are present in 100% of the 3,649 games (`audit-numbers.json`, `sample.share_with_both_qbs` = 1.0). In the 2026 file, names are present for 79 of 79 finished games and for 14 of 193 unplayed games, week 6 only (`feeds-extra.txt`). The file has no column for who was expected before a finished game.
* HYPOTHESIS: for a finished game the name is the man who actually started, so the bench sees late changes that a live pick could not. **Settled by:** the `qb_observations` log (`models.py:380`, collecting since 2026-10-13): for each 2026 game compare the last name seen before kickoff with the name after the game, and count the differences. `docs/gauntlet/PLAN.md` row 13 already names this "hindsight-QB caveat".
* A bound on the size, not a measurement of it: the whole stats model is 0.0028 log loss ahead of Elo alone (A9, VERIFIED), and the flags are only part of that. How much of the 0.0028 would survive with pre-game projections is the HYPOTHESIS above.

**A12. VERIFIED. Injuries, weather, star players and news are not model inputs, so they cannot leak; there is no scaler or imputer to fit.**
* The full input list is `features.py:11-13`. Command: `grep -n "FEATURES = " backend/nflpi/predictions/features.py` prints exactly `BASE_FEATURES` (four names) and `BLEND_FEATURES` (the line plus those four).
* Preprocessing is two fixed steps: the line's probability is clipped to 1% to 99% (`features.py:128`) and rows with a missing input are dropped from a fit (`predictions/model.py:21`). The Elo settings are chosen on the training seasons only (`backtest.py:63-79`), proved by the A5 test.
* Stars-out was tested as an input in step 8b and did not ship (`docs/gauntlet/logs/step-8b.md`).

## Question 4. Are the probabilities calibrated?

**A4. VERIFIED. Yes. Across ten equal groups of games, what happened is within the 95% interval of what the blend said, in every group.**

Blend, 2012 to 2025, 3,649 games, sorted by the home team's stated chance (`audit-numbers.json`, `reliability.all.blend`):

| Tenth | Games | Stated chance (mean) | Home team won | Gap | 95% interval of "won" |
|---|---|---|---|---|---|
| 1 | 365 | 22.2% | 21.1% | -1.1 | 17.2 to 25.6 |
| 2 | 365 | 33.3% | 36.7% | +3.4 | 31.9 to 41.8 |
| 3 | 365 | 40.4% | 38.9% | -1.5 | 34.0 to 44.0 |
| 4 | 365 | 47.2% | 48.5% | +1.3 | 43.4 to 53.6 |
| 5 | 365 | 54.3% | 52.9% | -1.4 | 47.8 to 57.9 |
| 6 | 364 | 59.6% | 59.1% | -0.5 | 53.9 to 64.0 |
| 7 | 365 | 64.4% | 63.6% | -0.8 | 58.5 to 68.3 |
| 8 | 365 | 69.9% | 69.0% | -0.9 | 64.1 to 73.6 |
| 9 | 365 | 75.5% | 76.4% | +0.9 | 71.8 to 80.5 |
| 10 | 365 | 83.9% | 86.8% | +2.9 | 83.0 to 89.9 |

* Average gap, weighted by games: 1.5 points. Calibration slope 1.02, intercept +0.01 (a slope of 1 is perfect; below 1 means overconfident). The slope is fitted with the app's own lightly regularized logistic fit (`predictions/model.py:22`), which shrinks it a little; the unregularized slope was not computed.
* On 2022 to 2025 alone (1,084 games, about 108 per group): slope 1.02, average gap 3.1 points, every group still inside its interval, so this table gives no evidence of drift. With about 108 games a group each interval is up to 9 points wide on either side, so the larger average gap is not a finding by itself.
* For comparison, same games: market slope 1.07 (slightly cautious), stats model 0.97 (slightly overconfident).
* Code: reliability in the app itself is `analytics/metrics.py:67-84` (five buckets by the picked side). Step 14b tested recalibrating the blend (Platt and isotonic); it did not ship, which fits: there is little to correct.

## Question 5. Is the evaluation chronological, with realistic cutoffs?

**A5. VERIFIED. Chronological, yes. The fit for season S uses seasons S-10 to S-1 and nothing later, on the bench and live.**
* Bench: `backtest.py:72-79` (training rows), `:97` (home-win rate from training rows), `:63-69` (Elo settings). Live: `engine.py:103-109`, and the scheduled job asks for the season before the current one (`jobs.py:56`).
* Tests: `::test_walk_forward_fit_for_a_season_uses_no_game_from_that_season_or_later` (records every fit's seasons, and shows that rewriting every result from the test season on changes no fitted weight) and `::test_live_model_is_fitted_only_on_seasons_before_the_one_it_predicts`. Planted defects M3, M4, M5 and M9 are caught.

**Realistic cutoffs: only in part.** Results: yes (A3, VERIFIED). The line: no, the bench has the close (A6, VERIFIED). The quarterback: not known (A8). Whether the bench's 66.5% overstates what a mid-week pick earns is the HYPOTHESIS of A6 and A8, not a measured fact; history cannot settle it, and the 2026 live log can.

**A11. VERIFIED from the step logs. The 2022 to 2025 check seasons have been scored nine times for the win model; they are no longer an untouched period.**

| Step | Looks at 2022 to 2025 | Source |
|---|---|---|
| 14 | 2 (in-season refit, EPA rating) | `docs/gauntlet/logs/step-14.md:153-154` |
| 14b | 5 (margin removal, spread and total inputs, calibration, recency, offence/defence split), plus a re-score of step 14's two under a second interval | `docs/gauntlet/logs/step-14b.md:162-167` |
| 8b | 2 (stars out, with and without reserve lists) | `docs/gauntlet/logs/step-8b.md:159-160` |

* None of the nine passed the ship rule. The logs say so themselves: step 14b counted its five looks (`step-14b.md:112`), step 8b its two (`step-8b.md:119`).
* Also seen, though not as win-model candidates: the blend's and the market's own numbers on those seasons are printed by every run; step 9 scored two score models there; step 4 read the pick labels' hit rates there (`docs/gauntlet/logs/step-4.md:39`). Step 14c is running now and will add more looks; it is not counted here because it has not landed.
* **Still untouched:** the 2026 games not yet played, 193 of 272 as of 2026-10-13 (weeks 6 to 18; `feeds-extra.txt`). For those, a prediction logged live before kickoff (`Prediction.kind = 'live'`) can be told apart from one rebuilt afterwards (`'backfill'`). The 79 games already played in 2026 were not used to choose anything in the step logs read for this audit; whether anyone has looked at them informally is not known.

**A14. VERIFIED. What the bench leaves out:** of 3,663 finished regular-season games in 2012 to 2025, 13 ties (no winner to predict; `features.py:130-136`) and 1 game with no moneyline (`backtest.py:326`) (`audit-numbers.json`, `sample`). No pool tie rule is modelled.

## Question 6. Does the model beat simple baselines on the same games?

**A9. VERIFIED. It beats "always home" and "Elo only" clearly. It does not beat "market only".**

Same 3,649 games (`audit-numbers.json`, `baselines.all`):

| Model | Winners picked | Log loss | Brier |
|---|---|---|---|
| Always the home team | 55.36% | 0.6876 | 0.2472 |
| Elo ratings only | 64.07% | 0.6322 | 0.2209 |
| Stats model (no line) | 64.51% | 0.6293 | 0.2197 |
| Market only (closing line) | 66.57% | 0.6094 | 0.2110 |
| **Blend (the live model)** | **66.46%** | **0.6107** | **0.2115** |

Paired, same games, log-loss gain of the first over the second (positive = first is better; `paired.all`):

| Comparison | Gain | 95% interval | Winners picked, difference |
|---|---|---|---|
| Elo over always-home | +0.0555 | +0.0442 to +0.0662 | +8.71 points |
| Stats model over Elo | +0.0028 | +0.00005 to +0.0057 | +0.44 (interval -0.25 to +1.12) |
| Blend over stats model | +0.0186 | +0.0126 to +0.0247 | +1.95 |
| **Blend over market** | **-0.0013** | **-0.0030 to +0.0003** | **-0.11 (interval -0.55 to +0.36)** |
| Market over stats model | +0.0199 | +0.0132 to +0.0269 | +2.06 |

* On 2022 to 2025 alone (1,084 games): market 67.80% and 0.6082, blend 67.53% and 0.6095; blend over market -0.0013 (interval -0.0043 to +0.0016).
* Resampling whole weeks instead of single games (games in one week are not independent) gives nearly the same intervals: blend over market -0.0029 to +0.0004 on all seasons and -0.0038 to +0.0012 on 2022 to 2025 (`paired.*.blend_vs_market.log_loss_gain_ci_cluster`).
* In words: home field and the quarterback flags add almost nothing to Elo; the line adds a lot to the stats model; the stats inputs add nothing measurable to the line.
* Code: `analytics/backtest.py:92-110` and `:322-332`; `analytics/metrics.py:109-136`.

**A10. VERIFIED. The blend is the market with small changes.**
* Command `blend_vs_market.py`, output `blend-vs-market.txt`: the blend's pick differs from the market's in 72 of 3,649 games (1.97%); in those 72 it was right 34 times. The two probabilities differ by 1.6 points on average and correlate at 0.993.
* The weights a fit on 2016 to 2025 gives: 1.03 on the line's log-odds, 0.016 on the Elo difference (same file).
* This is the evidence behind line 1 of the summary. What follows for the plan is a reading of these numbers, not a new measurement: while the line stays in the model with a weight near 1, an added input should change a pick only where it disagrees with the closing line strongly enough to cross 50%.

## One trap for the next lanes

**A13. VERIFIED. nflverse's spread has the opposite sign to the owner brief's.** In the schedule file a positive `spread_line` means the home team is favoured: of 2,284 games with a positive spread the home moneyline is negative in 2,283 (`feeds-extra.txt`). The brief (section 8) writes the home spread `h` so that the home team covers when margin + h > 0, which makes a favourite's `h` negative. So `h = -spread_line`. The app's own score helper uses the nflverse sign (`predictions/scores.py:24`). Lanes 18b, 18c and 18d must convert at one named place. The same file also holds prices for the spread and the total (`home_spread_odds`, `over_odds`: present for 3,662 of 3,663 games) that the app does not read today (`ingestion/nflverse.py:175-178`), and 90 spread pushes and 33 total pushes in 2012 to 2025.

## What this audit did not check

* The live database (this lane may not open it): the real 2026 prediction rows, the real ages of stored lines, the weather forecasts. `CLAUDE.md` records the weather adapter as untested live.
* The Odds API and Kalshi feeds of step 15: zero calls were made.
* Step 14c's code, which has not landed.
* The score model of step 9 beyond its own log.
* Where nflverse's lines and quarterback names come from, and when they are fixed.
