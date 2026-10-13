# Game-score simulator (step 18c)

Brief reference: `docs/model/OWNER_BRIEF_2026-10-13.md` section 7 (and 6, 10). Code: `backend/nflpi/sim/`. Bench: `backend/nflpi/analytics/sim_backtest.py`. Evidence: `docs/gauntlet/logs/step-18c.md`, `docs/gauntlet/logs/step-18c-evidence/`.

## What it is, and what it is not

A **game-score simulation**: given each team's expected points in one game, it draws many possible final scores (whole numbers, never negative) and reads win, tie, cover, over and under probabilities off them. It is **not** a play-by-play or drive-level engine: no downs, no clock, no fourth-down decisions. Nothing in it knows a game's story, only the two expected-points numbers and what past seasons say about how far real scores scatter around such numbers.

It is **not wired into the live app yet** (see Seam at the end).

## Public function

```python
simulate_game(team_a_features, team_b_features, n_simulations=10_000, *,
              params=None, seed=None, spread=None, total=None,
              neutral_site=False, distribution=DEFAULT_DISTRIBUTION, playoff=False) -> SimResult
```

* `TeamFeatures(expected_points)`: the only per-team input; finite and in (0, 100].
* `params`: a `SimParams` from `learn_params(...)` (learned on past seasons only). The `poisson` baseline needs none; the other three distributions raise without it.
* Conventions. Margin M = team A score minus team B score. `spread` is the quoted spread for team A: A covers when M + spread > 0, B covers when M + spread < 0, push when it equals 0 (nflverse `spread_line` is positive when the home team is favoured, so the home team's quoted spread is minus that number). Over when the total is above `total`, under when below, push when equal.
* `neutral_site` is recorded on the result only; the venue effect is already inside the expected points.
* `playoff=True` removes ties (see Overtime).
* Randomness: `numpy.random.default_rng(seed)`; the same seed gives the same output. 10,000 simulations of one game take a few milliseconds (a test fails above 100 ms).

`SimResult` carries the score samples (`a_score`, `b_score`), `p_a_win`, `p_b_win`, `p_tie`, `p_a_cover`, `p_b_cover`, `p_spread_push`, `p_over`, `p_under`, `p_total_push`, `expected_margin`, `expected_total`, 50/80/95 percent predictive intervals for margin and total, and `sampling_error`.

**Monte Carlo error is not model uncertainty.** `sampling_error` holds sqrt(p(1-p)/n) for each probability (and sd/sqrt(n) for the two expected values) and is labelled "sampling error only". More simulations shrink it; they do not repair biased expected points, missing information or leakage.

## Where expected points come from

Existing code, two variants, always reported separately:

* **football_only**: `ScoreModel` on `STATS_FEATURES` (Elo difference, home field, quarterback change, recent points scored and allowed), fit on the ten seasons before the game. No betting number.
* **market_informed**: the closing line's own implied score (`implied_score(spread, total)`). **A simulator priced at the market's own line sits near 50 percent on cover and over by construction. It is a reference point, not an independent discovery** (brief section 6).

## Distributions (regulation scores)

| name | idea | learned |
|---|---|---|
| `poisson` | two independent Poisson counts. Baseline. | nothing |
| `paired_residual` | stochastically rounded expected points plus a past (A residual, B residual) pair, residual = regulation score minus rounded expected points | the residual pairs |
| `bivariate_normal` | rounded two-variable normal, sd = sqrt(phi x expected points) | phi per side, correlation |
| `shared_gamma_poisson` | Poisson counts whose rate is multiplied by gamma factors that share a common part: overdispersed, and the two scores can move together | total and shared relative variance |

## Learned parameters, and how future data is kept out

`learn_params` is a pure function of the rows it is given. The bench gives it only the seasons `max(2004, S-10)` to `S-1` when testing season S, with expected points that were themselves produced walk-forward. Tests change every result from season S on and check the parameters do not move.

## Overtime, ties, season rules

Distributions give the score after regulation. A regulation tie goes to overtime: it stays a tie with the learned probability `ot_tie_frac` (regular season only) or one side (50/50, an assumption) gains a learned increment (the winning margins of past overtime games). The regulation score of a past overtime game is taken as the loser's final score for both sides (an approximation: wrong when both teams scored in a modified-sudden-death overtime). Rules by era: `sudden_death_15` before 2012, `modified_15` 2012 to 2016, `modified_10` from 2017; the learner uses only same-era overtime games when it has at least 30, else all training overtime games and flags `ot_era_fallback`. `playoff=True` sets the tie probability to zero.

## Results

All numbers from ONE confirm run on seasons 2022 to 2025, 1,087 regular-season games with a closing line, 10,000 simulations each, every variant (file `docs/gauntlet/logs/step-18c-evidence/confirm-result.json`, written once by `python -m nflpi.analytics.sim_backtest confirm`). The default distribution was picked before that look, on 2012 to 2021 only (`tune-result.json`, 2,576 games): pooled CRPS (margin plus total, lower is better) poisson 16.136, **paired_residual 15.047**, bivariate_normal 15.059, shared_gamma_poisson 15.061. The three learned distributions differ by 0.014 points; the choice among them is a near tie. Poisson is clearly worse.

**Short answer: no edge is shown.** The simulator reproduces the spread of real scores well enough to be useful for ranges and tie rates; it does not beat the betting market or the live blend at picking winners, covers or overs.

| variant (confirm) | margin MAE / RMSE | total MAE / RMSE | margin 50/80/95% coverage | total 50/80/95% coverage |
|---|---|---|---|---|
| football_only, poisson | 9.90 / 12.8 | 10.48 / 13.3 | 34 / 57 / 75 | 32 / 52 / 70 |
| football_only, paired_residual (default) | 9.89 / 12.8 | 10.46 / 13.3 | 55 / 81 / 97 | 54 / 82 / 96 |
| football_only, bivariate_normal | 9.91 / 12.8 | 10.47 / 13.3 | 58 / 82 / 95 | 53 / 83 / 95 |
| football_only, shared_gamma_poisson | 9.91 / 12.8 | 10.47 / 13.3 | 56 / 82 / 95 | 53 / 81 / 95 |
| market_informed, paired_residual | 9.49 / 12.4 | 10.19 / 13.0 | 55 / 82 / 96 | 56 / 83 / 95 |
| market_informed, bivariate_normal | 9.50 / 12.4 | 10.20 / 13.0 | 57 / 82 / 95 | 54 / 83 / 94 |
| market_informed, shared_gamma_poisson | 9.50 / 12.4 | 10.20 / 13.0 | 56 / 81 / 95 | 54 / 81 / 94 |
| market_informed, poisson | 9.50 / 12.4 | 10.20 / 13.0 | 36 / 57 / 75 | 32 / 53 / 72 |

(MAE and RMSE are of the simulated mean against the real margin and total.)

* **Independent Poisson is too narrow.** Its 50/80/95 percent intervals hold only about 35/57/75 percent of real margins. The three learned distributions come close to their nominal levels (a little wide at 50 percent for paired_residual).
* **Cover and over calibration (Brier; a flat 0.5 scores 0.25).** football_only: cover 0.2600 to 0.2615 and over 0.2574 to 0.2586 for the learned distributions, i.e. worse than a coin, so the football-only simulator has no cover or over edge against the closing line. market_informed: 0.2499 to 0.2502, i.e. about 0.25 by construction. Reliability tables (10 bins) are in the result file.
* **Ties.** Simulated final-tie rate 0.20 to 0.31 percent for the variants against a real 0.28 percent (3 of 1,087 games): consistent, but 3 games cannot validate it tightly.
* **Football key numbers (|margin| = 3 and 7).** Real games: 14.8 and 8.0 percent. Simulated: poisson 11.1 and 6.5, the learned distributions 7.1 to 7.8 and 4.9 to 5.3. **Every variant under-represents 3 and 7**, the learned ones by about half. The simulator smooths football's lumpy scoring; do not read exact-margin or middling-spread-push probabilities near 3 and 7 from it.
* **Win probability against the live blend** (`p_a_win + p_tie/2` for the home side, decided games only, 1,084 games; blend log loss 0.6095, market 0.6082): football_only paired_residual 0.6304, log-loss gain over the blend -0.0209 (95% -0.0317 to -0.0099, the simulator is worse) and accuracy 65.7 percent against the blend's 67.5; market_informed paired_residual 0.6068, gain +0.0027 (95% -0.0011 to +0.0065), accuracy 67.7 against 67.5. **The interval includes zero, so under the D18 ship rule nothing here beats the blend**; it is a tie by construction because the expected points are the market's.
* **Gap to the blend (cross-check).** football_only paired_residual: mean absolute gap 0.066, 242 of 1,087 games above 0.10, largest 0.36. market_informed: mean 0.023, largest 0.116, 1 game above 0.10. The largest football-only gaps are games the market knew more about than the stats model (checked by name, not by data: 2023 week 18 PIT at BAL, a game where Baltimore was expected to rest starters; 2022 week 1 DEN at SEA, the first game after a quarterback trade; 2025 week 6 LA at BAL). The simulator is consistent with its inputs; it is not independent of them.

## Limits

* A score sampler: no in-game state, no injuries during the game, no weather beyond what the expected points carry.
* Overtime winner is 50/50 and the overtime scoring pool is not tilted by team strength.
* Expected points are only as good as `ScoreModel` and the line; the simulator adds a shape, not information.
* `paired_residual` residuals are not scaled by the game's expected points.
* Score dependence is a single learned correlation for the whole league.
* Closing lines are used as a benchmark and as the market-informed input; they are not a fair pre-kickoff input for a pick made earlier in the week.

## Seam (for the integrator)

`SEAM: backend/nflpi/predictions/engine.py`. For each pregame snapshot: build `TeamFeatures(expected_points)` for the home and away team from the existing `ScoreModel`, call `learn_params(...)` once per season (training rows = the previous ten seasons, expected points walk-forward, as `sim_backtest.learn_for_season` does), then `simulate_game(home, away, params=params, seed=<game id hash>, spread=-spread_line, total=total_line, distribution=DEFAULT_DISTRIBUTION)`. Publish `p_a_win + p_tie / 2` only next to the classifier's probability and label the source of each number.
