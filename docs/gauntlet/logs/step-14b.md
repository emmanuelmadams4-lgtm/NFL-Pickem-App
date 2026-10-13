# Step 14b log: five model ideas from the repo review (lane modelb)

Lane coordinator: Oscar (hive `worker-modelb`). Mode: Gauntlet ONE_SHOT, tier T3. Branch `lane/modelb`, base `main` at `eed7c61`.
Evidence folder: `docs/gauntlet/logs/step-14b-evidence/`. Gate: `bash docs/gauntlet/logs/step-14b-evidence/gate.sh <label>`.

## In plain words

* **What this step builds:** nothing new for the screen. It takes the five ideas the repo review found in other people's models and runs each one through the test bench step 14 built: replay past seasons, compare with today's model, say "ships" or "does not ship".
* **What it replaces:** nothing, unless an idea wins. A winner is committed here as a tested change with its proof; wiring it into the live app is a seam for the integrator (this lane may not touch the engine, the worker, the API or the web app).
* **What it is not:** not a new data source, not a change to the ship rule (that is the owner's call), not a change after one bad week.

Words used below. **Log loss:** a score for probabilities, lower is better; it punishes being sure and wrong. **Gain:** how much lower an idea's log loss is than today's model (positive is better). **Blend:** today's model, the stats model plus the closing betting line. **Bookmaker margin:** the two sides' prices add up to more than 100%; removing it gives the market's real estimate. **Tune seasons:** 2012 to 2021, where a setting may be chosen. **Confirm seasons:** 2022 to 2025, looked at once per idea, never used to choose.

## 1. PLANNING

* **Step:** PLAN.md row 14b (decision D60), tier T3. Dependencies: step 14 landed (PR #9, `684c2da`). `NEEDS: (none)` in `lanes.md`.
* **Scope (god's dispatch, 2026-10-13):** five ideas, one at a time, in this order: (1) cluster-bootstrap check of the ship rule on step 14's two candidates; (2) other ways to remove the bookmaker margin, and the spread and the total as extra inputs; (3) calibrated blend; (4) recency-weighted fit; (5) offence and defence EPA split with success rate, only if 2 to 4 show signal, stopping at one more miss.
* **Out:** `predictions/engine.py`, `jobs.py`, the API, the web app, the shared package, any new data source, any change to the ship rule.
* **Done when:** each idea has a walk-forward verdict on real nflverse data with every variant logged; the code is tested; the gate is green twice on the final commit; a new critic passes; lane guard is clean.
* **Files this lane may edit:** `predictions/{model,features,elo,market}.py`, `analytics/{backtest,metrics}.py`, `tests/test_model.py`, this log and its evidence folder.
* **One-way doors:** none. No schema, no API contract, no live model change. Reversibility: two-way.
* **Deployment reach:** none. Nothing here runs in the live app.
* **Prior decisions relied on:** CLAUDE.md "Model validation requirements" (walk-forward by season, closing line only as benchmark or blend, paired-bootstrap interval for "better than"); owner decision 2026-10-12 (each idea tested first, ships only if it wins); step 14 log (the bench, the rule, what already lost: weekly refit, EPA net rating; rest days dropped earlier); D60 (PLAN row 14b).

### Product Mode pre-flight

1. **Problem:** the owner asked whether every angle was looked at and whether the model could borrow from strong public models.
2. **Why now:** the repo review (`hive/research/model-repos-review.md`, 2026-10-13) named five testable ideas, and the bench to test them landed today.
3. **Scope:** the five ideas, on data the app already ingests. Cut: opening line and line movement (no history before 2026), boosted trees, score-distribution model, live wiring.
4. **Success metric:** confirm-season log-loss gain over the blend with a paired-bootstrap 95% interval; accuracy as the guard.
5. **Reversibility:** two-way.

### Assumptions

| Assumption | State |
|---|---|
| The model to beat is the walk-forward `p_blend` of `analytics/backtest.py`, window 10 seasons | validated (step 14 log) |
| Step 14 stored only summary numbers, not per-game predictions. "Re-score the stored candidates" therefore means: recompute them with the same code and data source, prove the game-level numbers equal the stored file, then add the cluster interval | validated (`run-3-candidates.json` holds no per-game rows); the equality check is printed by the run |
| nflverse moneylines start in 2006 (2006: 209 of 256 games, 2008: 185, complete from 2010); spread and total are complete from 2002 | validated (counted in the cached 2026-10-13 `games.csv`) |
| `spread_line` is positive when the home team is favoured | validated (2023 rows: +4.0 with home price -198; -4.0 with +170) |
| In a two-way market Shin's method gives the same number as the additive method | validated by a test on Shin's own defining equation (clause D1); so "Shin" and "additive" are one variant in substance and both are logged |
| A linear `total_line` input can only shift the home win chance up or down; the theory for the total is that the same spread means more in a low-scoring game, so one extra variant uses spread divided by total | assumed; frozen as the fourth input variant before any result |
| Five confirm looks at 95% each mean about a one in five chance that at least one idea would pass by luck if none were real | stated in the verdict; the rule itself is unchanged |

### Instrumentation

North star: confirm-season log-loss gain against the blend. Baseline: the blend's numbers from the same run (must match step 14: market 0.6094, blend 0.6107 on 3,649 games). Read by `ideas.py <stage>`, which prints one JSON per idea. Guardrail: accuracy must not drop. Check date: each new idea.

### Skills and tools

| Skill | Use |
|---|---|
| `/jevgrep` | `jg 0.8.0`, `jg doctor` OK (`JEVGREP: ready`). Question: "Where are closing spread and total lines stored and are they used as inputs to any win probability model?" Ranked `models.py`, `ingestion/service.py`, `engine.py`, `nflverse.py`, `features.py`. A follow-up grep of `engine.py` showed it reads only `market_prob` and `market_logit`: the spread and total are stored and unused by the model. Log: `jg-1.log`. |
| `/graft` | N/A: the seam files were named in the dispatch and read whole. |
| `/tdd` | No project `tdd` skill. Failing tests first, written by the coordinator (section 2). |
| `/ponytail` | In the work order: smallest correct diff, no new dependency, plain functions. |
| `harness-engineering` | N/A: no runner, evaluator service or approval boundary is created. |
| Design Gauntlet | N/A: no user interface. |
| Parallel Lanes | Lane claimed (`claims/modelb`), own worktree, own state file, coord task #17. |
| Headroom | `HEADROOM: not-routed` (`headroom doctor`: 1 failure, 5 warnings). Not a blocker. |
| `jev` skill | Not loaded. The model and review questions are the gauntlet skill's own Job 1 and Job 4 questions, word for word, sent through `decide.sh`. |

EFFORT: PLANNING and SPECIFICATION high (session setting, not changed).

## 2. SPECIFICATION

Public seam (the bench modules step 14 set as the place a model is judged):

* `metrics.bootstrap_ci(values, reps, seed, clusters=None)`, `metrics.paired_gain(p_new, p_old, y, clusters=None)`
* `backtest.evaluate(preds, candidates, tune, confirm, cluster=None)`
* `market.DEVIG_METHODS`, `market.devig_home_prob(home_ml, away_ml, method)`, `features.market_logit(df, method)`
* `model.LogitModel.fit(df, features, weights=None)`
* `backtest.idea_preds(df, seasons, window=10)`, `backtest.calibrated(preds, method)`, `backtest.RECENCY_HALF_LIVES`

### Frozen acceptance criteria (functional layer)

| ID | Clause |
|---|---|
| B1 | `bootstrap_ci(values, clusters=ids)` resamples whole clusters with replacement (as many draws as there are clusters) and takes the mean over the games drawn, so each game counts once. One game per cluster equals the plain bootstrap. A `clusters` array of another length raises `ValueError`. |
| B2 | `paired_gain(..., clusters=ids)` adds `log_loss_gain_ci_cluster`, `accuracy_diff_ci_cluster` and `ships_cluster` and changes none of the six step 14 keys. Without `clusters` the output is exactly step 14's. `ships_cluster` is true only when the low end of the cluster interval is above 0 and accuracy did not drop. A `clusters` array of another length raises `ValueError`. |
| B3 | `evaluate(..., cluster=[columns])` passes one cluster id per distinct combination of those columns to every `paired_gain` call. `ships` stays the game-level rule. |
| B4 | `evaluate` raises `ValueError` when a season is in both the tune and the confirm list. |
| D1 | `devig_home_prob` returns the home win chance with the margin removed, by method. multiplicative: today's `novig_home_prob`, unchanged. additive: the same amount off each side. power: both implied chances raised to one exponent so they sum to 1. odds_ratio: both sides' odds divided by one factor so the chances sum to 1. shin: Shin's insider-share model. Every method: the two sides sum to 1, and a price with no margin is returned as it is. |
| D2 | A missing price gives a missing value (`None`), never a guess. An unknown method raises `ValueError`. |
| D3 | `market_logit(df, method)` is the log-odds of that chance clipped to 1% to 99% (the clip `add_features` uses), missing where either price is missing. For multiplicative it equals the `market_logit` column of `add_features`. |
| R1 | `LogitModel.fit(..., weights=series)` weights each training row. All ones equals no weights; weight 2 equals having the row twice; a row dropped for a missing value drops its weight; a negative or non-finite weight raises `ValueError`. |
| V1 | `idea_preds` scores the same games as the step 14 bench (regular season, finished, with a price) for the seasons asked, and carries the same `p_blend`. |
| V2 | Every fit inside `idea_preds` uses only the `window` seasons before the test season. |
| V3 | Margin variants: `p_devig_<method>` (additive, shin, power, odds_ratio) is the blend refitted with `market_logit_<method>` in place of `market_logit`. |
| V4 | Line-input variants: the blend's inputs plus `spread_pts` = spread / 7 (`p_in_spread`), plus `total_pts` = (total - 45) / 10 (`p_in_total`), plus both (`p_in_both`), plus `spread_per_total` = 10 x spread / total (`p_in_ratio`). A game missing a needed line keeps the blend's own number; a line is never invented. |
| V5 | Recency variants: `p_recency_<h>` for h = 2, 4, 8 seasons is the blend's inputs fitted with row weight 0.5 ^ (age / h), age = seasons before the newest training season. |
| V6 | No variant's number for a game moves when the result of a game in that week or later changes. |
| C1 | `calibrated(preds, method)`: the value for season S is fitted only on walk-forward `p_blend` and results of seasons before S. The first season in `preds` is missing (nothing to learn from). An unknown method raises `ValueError`. Values are clipped to 1% to 99%. |
| C2 | platt: one slope and one intercept on the blend's log-odds. |
| C3 | isotonic: a non-decreasing step function of `p_blend` (it never reorders two picks). |
| X1 | Nothing existing changes: `BASE_FEATURES`, `BLEND_FEATURES`, `add_features`, `run_backtest`, `candidate_preds`, and every existing test. |

User-facing layer: N/A (no screen). The owner-facing output is this log's verdict table.
Operational layer: `ideas.py <stage>` runs from a clean checkout against live nflverse files, prints JSON with `allow_nan=False`, fails loudly on a download error, and its baseline must match step 14 (market 0.6094, blend 0.6107, 3,649 games; confirm 1,084 games).

### Protocol, frozen before any result was seen

* Baseline `p_blend`; tune 2012 to 2021; confirm 2022 to 2025; window 10. Data: live nflverse `schedules/games.csv` (and `stats_team` for idea 1), the way step 14 read it.
* **Ship rule, unchanged from step 14:** low end of the game-level paired-bootstrap 95% interval of the confirm log-loss gain above 0, and accuracy not lower. The cluster interval (season-week clusters) is printed beside it for every idea and never decides.
* **Power limit, to be said in every verdict:** the confirm set is 1,084 games; it cannot show a gain under about 0.001 log loss.
* For each candidate every variant is scored on the tune seasons and printed; the variant with the largest tune gain is scored once on the confirm seasons. No variant is added after a result is seen. A losing idea is logged as lost.
* Idea 1, `cluster`: step 14's two candidates recomputed (`candidate_preds`), game-level numbers checked against `step-14-evidence/run-3-candidates.json`, cluster interval added. A flipped verdict is reported to god; the rule does not change here.
* Idea 2a, `devig`: variants additive, shin, power, odds_ratio. Idea 2b, `inputs`: variants spread, total, both, ratio. Two candidates, two confirm looks.
* Idea 3, `calibration`: the reliability table of the blend on the tune seasons is printed first. Variants platt, isotonic. Walk-forward blend predictions are made from 2008 (the first season with two priced seasons behind it), so 2012 is calibrated on 2008 to 2011 and each later season on all scored seasons before it.
* Idea 4, `recency`: half-lives 2, 4, 8 seasons.
* **"Signal" (frozen):** an idea shows signal when its chosen variant has a positive gain on the tune seasons and a positive gain on the confirm seasons. Idea 5 runs only if at least one of 2a, 2b, 3, 4 shows signal; its own clauses are frozen in an addendum before its first run; if it does not ship, the step stops there.
* Five candidates, five confirm looks. If none of them were real, the chance that at least one passes a 95% rule by luck is about one in five. Said with the verdict.

### First failing tests

Twelve tests in `backend/tests/test_model.py`, written by the coordinator before any production code. Red for the intended reason, the seam does not exist (`red-1.log`): `TypeError: bootstrap_ci() got an unexpected keyword argument 'clusters'`, `AttributeError: module 'nflpi.predictions.market' has no attribute 'DEVIG_METHODS'`, `AttributeError: module 'nflpi.analytics.backtest' has no attribute 'idea_preds'`, and so on. The 19 step 14 tests still pass. The arithmetic behind the tolerances was checked with a throwaway script first (not committed): Platt on log-odds misses the truth by 0.005 on the test data, Platt on the raw probability by 0.025, so the 0.012 limit separates them.

### Baseline

`tests/test_model.py` on `eed7c61`: 19 passed (`baseline-test_model.log`). The full gate on `main` at `eed7c61` is the integrator's CI run (green, PR #10). The full gate runs here twice on the final commit.

### Addendum: idea 5, frozen 2026-10-13 before its first run

The gate opened by the frozen meaning of "signal": idea 2a (tune +0.00004, confirm +0.00023) and idea 4 (tune +0.00008, confirm +0.00020) gained on both periods. Both gains are about five times smaller than what the confirm set can detect, so this is signal by the letter of the rule, not evidence of a real effect. The rule was frozen before the results, so idea 5 runs.

| ID | Clause |
|---|---|
| E1 | `features.offence_defence(rows)`: per team and game, offence EPA per play and success rate from that team's own scrimmage plays; the defence values are what the opponent's offence did in the same game. A game without two usable sides is left out for both teams. |
| E2 | `backtest.split_preds`: each input is a pregame rating (weighted mean of earlier games only, the step 14 `epa_diff` rule, half-life 4, 8 or 16 games), home minus away, on a fixed scale (EPA x 10, success rate x 20). Fits use the seasons before the test season only. A game where a team has no rating keeps the blend's number. |
| E3 | No number for a game moves when the result of a game in that week or later changes. |

Protocol: candidate `offence_defence_split`, six variants fixed here: offence and defence EPA ratings at half-life 4, 8, 16 games (`p_split_<h>`), and the same plus offence and defence success-rate ratings (`p_split_sr_<h>`). Chosen on the tune seasons, scored once on the confirm seasons, same ship rule. If it does not ship, the step stops: no further variant.
Data: nflverse play-by-play 2002 to 2025 (`pbp/play_by_play_<season>.csv.gz`), read by the evidence script through the app's own download function (same host, timeout and retries); plays counted are passes and runs with an EPA value; `success` is nflverse's own 0/1 column. Step 14's team-week file has no success rate, which is why play-by-play is needed. The scales are fixed numbers chosen so each input varies by about one unit (the fit penalises large weights); they are not fitted.
Red: `red-2.log` (three tests, `AttributeError`: the functions do not exist).
