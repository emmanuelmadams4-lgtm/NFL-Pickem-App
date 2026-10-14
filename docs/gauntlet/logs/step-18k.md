
## Critic (checkpoint 6)
Fresh ecc:python-reviewer, no transcript, on `a773c41`: **PASS** (0 critical, 0 high). Carried medium/low findings, not fixed in this step (code left as the critic saw it):
* M1 `run_checker._ask` swallows a database error in `_reserve_call` without `session.rollback()`; the later commit could then raise. Add a rollback in the except branches.
* M2 a backfill run is one request for a whole season (about 270 games): likely too large, then no verdict drops those simulations. Skip or chunk the check for `kind="backfill"`.
* M3 the check shares the 60-a-day `AI_DAILY_CALL_LIMIT` with reports; an outage retries every 30 minutes. Give it its own budget or back off.
* M4 a report with `all_ok = false` could be passed by Claude. Block in Python first when `all_ok` is false (and save the call).
* Low: rows stored before 18k count as "last checked"; one query per game on a block; the spread-sign check reuses the same function as the simulator; `PASS` followed by a lowercase "fail" line is accepted; the note stores up to 500 characters of Claude text.

## Critic fixes (head after this section)
Fixed with red tests first: M1 rollback in every `_ask` failure path; M2 a backfill run is never sent to Claude (simulations stored missing, status `not_checked`, note says why); M3 own budget `AI_RUN_CHECK_DAILY_LIMIT` (default 6, own counter) and back-off 30 min doubling to 6 h, reset when the content changes; M4 a Python report with `all_ok = false` blocks the run without a Claude call. Security review: S1 any exception in the check still writes every prediction (status `no_verdict`, cause `error`); S2 only simulations stamped `simulation_checked` (a PASS) carry forward, the stamp is added after the inputs hash; S3 PASS must be the only non-empty line; S4 cause code (cap, provider, unparsed, error) stored and shown; L1 note is fixed text plus game ids; L2 exception type only is logged; L3 `git_dirty` out of the cache hash; L5 `allow_nan=False`.
**L4:** a FAIL is cached by content hash until the data changes (fail closed); only a changed run asks Claude again.
Gate (throwaway Postgres 17 on port 15733, removed after): backend 2335 passed, 1 skipped; ruff clean; `gen:api` run (status literal `not_checked`, new `cause` field); `tsc` clean. No real Claude calls.
Two existing tests in `test_wiring.py` changed: they used `kind="backfill"` to get a simulation, now they use live runs. One test bypasses `python_block` (see carried item 1).
Fresh critic (ecc:python-reviewer, final head 176c88e): **PASS**, 0 critical, 0 high.
Carried:
1. A simulation made with learned parameters on the test fixture fails the Python mean check (margin 5.5 vs 2.6). Unknown whether real data does too; if it does, every live run is blocked. Check on the first live run.
2. `_simulations(...)` in `refresh_predictions` is outside the new try; `log.exception` logs the message, not type only; rollback in the handler discards uncommitted caller work (no known caller has any).
3. A backfill run over a game with a live checked simulation writes a row with `None`.
4. A cap hit raises the back-off count though no call was made; `get_provider` errors are labelled `error`, not `provider`.
5. The web app does not show `simulation_check` yet.

## Mean check on real data (carried item 1)
Measured 2026-10-14 on public nflverse `schedules/games.csv` (rows before 2026-10-15 only, D72), live path: `sim_backtest.learn_for_season(table, S, "football_only")`, `engine._score_model`, `engine._simulation`, `run_check.check_game` (inputs marked present). No database, no paid call.

| Season | Games | All checks | Margin mean | Total mean | Sums | n |
|---|---|---|---|---|---|---|
| 2022 | 271 | 84.5% | 84.5% | 100% | 100% | 100% |
| 2023 | 272 | 86.4% | 86.4% | 100% | 100% | 100% |
| 2024 | 272 | 87.5% | 87.5% | 100% | 100% | 100% |
| 2025 | 272 | 83.8% | 83.8% | 100% | 100% | 100% |
| 2026 wk 1-5 | 79 | 97.5% | 97.5% | 100% | 100% | 100% |

Simulated minus inputs, margin: mean -0.46 to -0.51 per season (5%-95% about -0.73 to -0.21); total: mean -0.19 to +0.15. Sampling error about 0.13, slack 0.65. A 16-game week passes only if all 16 pass (about 0.85^16, 7%), so live runs would almost always be blocked.

Cause: the paired_residual pool mean (margin -0.41 to -0.52) shifts the simulated mean; simulated mean = mu + pool mean to within sampling error (mean gap 0.004). The pool shift comes from 2019 (-2.68) and 2020 (-2.01): older walk-forward models over-predicted home margin there. The target season's mu is fit on those same seasons, so the shift counts the home-field drop a second time. On 2022-2025 (1087 games) the bias actual minus mean margin is +0.11 for mu and +0.60 for the simulation (worse in 3 of 4 seasons); MSE +0.20 (95% CI -0.57 to 0.97).

Verdict: case (b), double count. Simulator, check and numbers left unchanged; sent to god as an owner-level model change (D70, D74).

## Simulator double-count fix
Built 2026-10-14 on lane/runcheck from fd86c67 under the integrator's grant (sim/params.py, sim_backtest.py, test_sim*.py, SIMULATOR.md). Not landed: waits for the owner (HAG-75). Public nflverse `schedules/games.csv`, rows before 2026-10-15 only (D72); no database for the bench, no paid call. Script and raw numbers: `step-18k-evidence/simfix/bench.py`, `bench.json` ("current" = `params_old.py`, a copy of `git show fd86c67:backend/nflpi/sim/params.py`, run from that folder).

Candidates (red tests first: `test_learn_params_centres_the_pool_on_the_final_score_so_a_biased_mu_is_not_counted_twice`, `test_simulated_mean_matches_the_inputs_when_the_past_model_was_biased`, both failed on fd86c67: pool mean off by 1.87, simulated margin 6.80 against inputs 3.70):
1. **Centred pool (kept).** `learn_params` subtracts each side's mean final-score residual, mean(score - rint(mu)), from its integer pool: floor(offset) off every row and 1 more off k = round(frac x n) evenly spaced rows of the sorted pool, so the mean is exact to 1/(2n) (about 0.0002) and the pool is shifted, not reshaped. The pool keeps the mean overtime adds over regulation, which the overtime step adds back. Deterministic and row-order invariant (existing test).
2. **In-sample pool (measured, not kept).** Pool residuals against the target season's own score model predicted on its training rows. Needs the feature frame inside `learn_for_season` and the jobs path; measured in the bench script only.

Bench, football_only (the live source), paired_residual, 2022-2025 walk-forward, 1,087 games, 10,000 simulations, same seeds. Gain = current minus fixed (positive = fixed better); bias, calibration and coverage gains = how much closer to 0 (or to nominal) the fixed mean is. 95% intervals: paired bootstrap over 72 season-weeks, 2,000 draws.

| Measure | Current (95%) | Centred | Gain vs current (95%) | In-sample | Gain vs current (95%) |
|---|---|---|---|---|---|
| Bias margin, actual - mean | +0.598 (-0.15 to 1.35) | +0.134 | +0.464 (-0.465 to 0.472) | +0.194 | +0.404 (-0.404 to 0.413) |
| Bias total | -0.277 (-1.05 to 0.44) | -0.233 | +0.044 (-0.056 to 0.072) | -0.220 | +0.056 (-0.067 to 0.084) |
| MSE margin | 163.99 | 163.61 | +0.38 (-0.33 to 1.12) | 163.52 | +0.47 (-0.15 to 1.09) |
| MSE total | 177.00 | 176.93 | +0.07 (-0.17 to 0.32) | 176.84 | +0.17 (-0.08 to 0.42) |
| CRPS margin | 7.1480 | 7.1413 | +0.0067 (-0.0084 to 0.0214) | 7.1388 | +0.0092 (-0.0043 to 0.0226) |
| CRPS total | 7.4475 | 7.4440 | +0.0035 (-0.0024 to 0.0099) | 7.4418 | +0.0057 (-0.0000 to 0.0116) |
| Brier cover (no push) | 0.2615 | 0.2613 | +0.0002 (-0.0008 to 0.0011) | 0.2612 | +0.0003 (-0.0007 to 0.0011) |
| Brier over (no push) | 0.2574 | 0.2572 | +0.0002 (-0.0002 to 0.0006) | 0.2573 | +0.0001 (-0.0003 to 0.0005) |
| Cover calibration, mean p - rate | -0.0108 | +0.0045 | +0.0063 (-0.0156 to 0.0156) | +0.0031 | +0.0077 (-0.0142 to 0.0142) |
| Over calibration | +0.0170 | +0.0154 | +0.0016 (-0.0019 to 0.0025) | +0.0155 | +0.0015 (-0.0017 to 0.0024) |
| Margin coverage 50 / 80 / 95 | 55.3 / 81.3 / 96.6 | 54.1 / 81.8 / 96.4 | +1.2 (0.4 to 2.1) / **-0.5 (-0.9 to 0.5)** / +0.2 (-0.2 to 0.6) | 54.5 / 81.9 / 96.2 | +0.8 / **-0.6 (-1.0 to 0.6)** / +0.4 |
| Total coverage 50 / 80 / 95 | 54.0 / 82.2 / 95.8 | 54.0 / 82.5 / 95.1 | 0.0 / **-0.3 (-0.6 to 0.0)** / +0.6 (-0.7 to 1.1) | 54.0 / 82.1 / 95.1 | 0.0 / +0.2 / +0.6 |
| Win log loss (decided games) | 0.63040 | 0.62989 | +0.0005 (-0.0014 to 0.0024) | 0.62963 | +0.0008 (-0.0010 to 0.0026) |
| Tie rate / abs 3 / abs 7 (real 0.28 / 14.8 / 8.0%) | 0.21 / 7.64 / 5.08% | 0.21 / 7.62 / 5.06% | | 0.21 / 7.65 / 5.07% | |

Reading: no measure is worse with an interval that excludes zero. On point estimates the centred pool is better or equal on every measure except 80% coverage of margin (0.5 points further from 80, about 5 of 1,087 games) and of total (0.3 points, about 3 games; interval upper bound 0.0). The in-sample pool has the same margin-80% slip. The bias and calibration "closer to zero" intervals bootstrap |current| - |fixed|, which is near-symmetric around zero whenever the true bias is small against the outcome noise (about 0.4 points): read them as "not shown", not as a significance test. The shift itself is exact (simulated margin moves +0.46 toward the inputs). The total 80% coverage interval's upper bound is exactly 0.0, a borderline case. Neither candidate shows a gain with an interval above zero on MSE, CRPS, Brier or log loss: the fix is about the mean check, not accuracy.

Python mean check (`run_check.check_game`, live path `engine._simulation`, inputs marked present):

| Season | Games | Game pass current / centred / in-sample | Week pass (all weeks) | 16-game weeks all pass | Mean sim - inputs, margin |
|---|---|---|---|---|---|
| 2024 | 272 | 87.5 / **100** / 100% | 2 of 18 / **18 of 18** / 18 of 18 | 0 of 10 / **10 of 10** / 10 of 10 | -0.46 / **-0.01** / -0.09 |
| 2025 | 272 | 83.8 / **99.6** / 99.6% | 1 of 18 / **17 of 18** / 17 of 18 | 0 of 9 / **8 of 9** / 8 of 9 | -0.51 / **-0.03** / -0.13 |
| 2026 wk 1-5 | 79 | 97.5 / **100** / 100% | 3 of 5 / **5 of 5** / 5 of 5 | 3 of 4 / **4 of 4** / 4 of 4 | -0.42 / **-0.04** / -0.13 |

The one game left failing, `2025_16_LV_HOU` (expected 30.96 to 11.62), is a different cause: scores are floored at zero, which lifts a low expected score's simulated mean (margin 18.68 against 19.34, slack 0.60). It is not the double count and is not changed here (distributions.py is outside the grant); with it, 2025 week 16 is blocked under this fix.

Choice: centred pool. It removes the double count exactly in `learn_params` alone, leaves the smallest margin shift in the mean check (at most 0.04 against 0.13 in-sample), and needs no change on the live path. The in-sample pool is a near tie on accuracy (its points are slightly better on MSE and CRPS, all within noise) but leaves part of the shift because its training rows are a subset of the model's.

Knock-on (for the integrator): `report --simulate` compares a fresh re-run with the stored 18c `confirm-result.json` at tolerance 1e-9, so after this lands it will report "does not reproduce" for the paired_residual variants until the confirm file is regenerated (step-18c evidence, not in this grant). The market_informed pool is centred too (its mean error was the closing line's own); live uses football_only only.
