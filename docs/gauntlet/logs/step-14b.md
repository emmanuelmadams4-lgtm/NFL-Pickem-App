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

## 3. IMPLEMENTATION

Provider: Codex, one bounded work order at a time, prompt on stdin. The coordinator wrote the tests and the runner script (`ideas.py`), read every diff and reran the proof itself each time.

| Work order | Model, effort | JEV | Result | Commit |
|---|---|---|---|---|
| WO-1 code for ideas 1 to 4 (`wo-1.md`) | gpt-6-sol, medium, try 1 | sol 0.55, medium 0.36: unsure. I took Jev's own lean, the higher option, instead of paying for an advisor call on a model pick | 31 passed, first try. Five files, all in scope | `dfb0f71` |
| WO-2 code for idea 5 (`wo-2.md`) | gpt-6-sol, medium, try 1 | same job class as WO-1; not asked again | 34 passed, first try. Two files, in scope | `9d0d49a` |
| WO-3 review fixes and cleanup (`wo-3.md`) | gpt-6-luna, medium, try 1 | not asked: mechanical, behaviour-preserving, checked by rerunning every stage | 34 passed; every stored number identical after it | `7aec8c6` |

CLIMBS: none. STRIKES: none. No Codex limit was hit. EFFORT: coordinator session setting unchanged.

### What the real data says

Run: `cd backend && uv run python ../docs/gauntlet/logs/step-14b-evidence/ideas.py <stage>`, against live nflverse files, 2026-10-13, one stage at a time in the plan's order, each committed before the next ran. Stored: `step-14b-evidence/run-<stage>.json` (first run) and `final-<stage>.json` (the final code, section 4). Walk-forward, window 10 seasons, 3,649 regular-season games with a closing line, 2012 to 2025; tune 2,565 games; confirm 1,084 games in 72 season-weeks. Run time: 2 to 3 seconds per stage, 17 seconds for idea 1, about 70 seconds for idea 5 (24 seasons of play-by-play).

**Baseline check (operational layer):** market 66.57%, log loss 0.6094; blend 66.46%, 0.6107. On the confirm seasons: market 67.80%, 0.6082; blend 67.53%, 0.6095. Equal to step 14's stored numbers; the script now stops if they ever differ.

Gain = how much lower the idea's log loss is than the blend's (positive is better). Interval = paired bootstrap, 95%, game by game (this is the rule). "By week" = the same interval when whole season-weeks are resampled (shown beside it, never decides).

### Verdict table

**Read this first: the confirm set is 1,084 games. It cannot show a gain under about 0.001 log loss. Every "No" below means "no gain this test can see", not "proven useless".**

| # | Idea | Chosen on 2012 to 2021 | Gain on 2022 to 2025 | Interval (the rule) | Interval by week | Accuracy change | Ships |
|---|---|---|---|---|---|---|---|
| 1 | Cluster-bootstrap check of step 14's two candidates | (step 14's choices) | in-season refit +0.00035; EPA rating -0.00041 | -0.00029 to +0.00100; -0.00171 to +0.00086 | -0.00021 to +0.00095; -0.00185 to +0.00110 | 0.00; +0.37 points | **No verdict flips. The rule stands.** |
| 2a | Other ways to remove the bookmaker margin | power | +0.00023 | -0.00031 to +0.00072 | -0.00029 to +0.00074 | 0.00 points | **No** |
| 2b | Spread and total as extra inputs | spread and total together | -0.00034 | -0.00342 to +0.00276 | -0.00344 to +0.00261 | -0.37 points | **No** |
| 3 | Calibrated blend | Platt | -0.00007 | -0.00103 to +0.00093 | -0.00104 to +0.00089 | -0.09 points | **No** |
| 4 | Recency-weighted fit | half-life 8 seasons | +0.00020 | -0.00054 to +0.00099 | -0.00062 to +0.00105 | -0.18 points | **No** |
| 5 | Offence and defence EPA split with success rate | EPA split, half-life 8 games | -0.00064 | -0.00246 to +0.00120 | -0.00296 to +0.00162 | +0.09 points | **No** |

**In plain words:** none of the five ideas beats the current model, so **the live model does not change**. Every interval includes zero. The two positive gains (2a and 4) are a fifth of the smallest gain this test can detect, and idea 4 also picked fewer winners. For scale: the closing line itself is 0.0013 ahead of the blend. Five ideas were each looked at once on the confirm seasons; had one passed, there would have been about a one in five chance of that happening by luck. None passed, so that caveat does not bite.

### Every variant tried (tune seasons, 2,565 games)

| Idea | Variant | Tune gain | Tune interval | Chosen |
|---|---|---|---|---|
| 1 | in-season refit | -0.00015 | -0.00058 to +0.00028 | yes |
| 1 | EPA rating, half-life 4 / 8 / 16 games | +0.00019 / +0.00012 / -0.00015 | see `run-cluster.json` | 4 |
| 2a | additive | +0.00002 | -0.00014 to +0.00016 | no |
| 2a | Shin (same numbers as additive: one method in substance) | +0.00002 | -0.00014 to +0.00016 | no |
| 2a | power | +0.00004 | -0.00025 to +0.00028 | yes |
| 2a | odds ratio | +0.00001 | -0.00017 to +0.00018 | no |
| 2b | + spread | +0.00028 | -0.00055 to +0.00106 | no |
| 2b | + total | +0.00043 | -0.00033 to +0.00118 | no |
| 2b | + spread and total | +0.00072 | -0.00044 to +0.00185 | yes |
| 2b | + spread divided by total | +0.00000 | -0.00050 to +0.00052 | no |
| 3 | Platt | -0.00056 | -0.00209 to +0.00097 | yes |
| 3 | isotonic | -0.00798 | -0.01387 to -0.00243 (clearly worse) | no |
| 4 | half-life 2 seasons | -0.00019 | -0.00155 to +0.00123 | no |
| 4 | half-life 4 seasons | +0.00006 | -0.00067 to +0.00083 | no |
| 4 | half-life 8 seasons | +0.00008 | -0.00029 to +0.00048 | yes |
| 5 | EPA split, half-life 4 / 8 / 16 games | -0.00036 / -0.00017 / -0.00026 | all include zero | 8 |
| 5 | EPA split plus success rate, half-life 4 / 8 / 16 games | -0.00134 / -0.00108 / -0.00075 | half-life 8 is clearly worse | no |

That is every variant: 4 recomputed from step 14 and 19 new (three distinct margin methods, since Shin equals additive). Nothing else was run on the confirm seasons. One extra tune-only check was run after the reviews (below).

### Notes on each idea

* **Idea 1.** The recomputed game-level numbers equal step 14's stored file key by key (`matches_step14_stored_numbers: true`). Resampling by week moves the interval little: slightly narrower for the refit, about 14% wider for the EPA rating. Same-week games are not correlated enough here to change a verdict. Nothing to send to the owner.
* **Idea 2a.** The fit already has its own weight on the market's log-odds, which absorbs most of what a different margin method changes.
* **Idea 2b.** The spread and total looked best of all on the tune seasons (+0.00072) and came out negative with fewer right picks on the confirm seasons: the pattern of an input that repeats what the moneyline already says and adds noise.
* **Idea 3.** Reliability table first (blend, tune seasons, by the picked side): said 55.3%, won 53.3% (794 games); said 64.8%, won 62.9% (827); said 74.5%, won 77.3% (661); said 83.8%, won 84.1% (258); said 91.8%, won 88.0% (25). Every bucket is within 3 points and the market's own table has the same shape. There is little to correct, and correcting it on small samples costs more than it gains (isotonic most of all).
* **Idea 4.** After the reviews (finding M1) I checked, on the tune seasons only, whether the small recency gains came from recency or from a side effect: weights below 1 also strengthen the fit's penalty. With the weights rescaled to mean 1 the tune gains shrink (half-life 8: +0.00008 to +0.00002; half-life 4: +0.00006 to -0.00004; half-life 2: -0.00019 to -0.00041; `run-recency-check.json`). So even the small recency "signal" was partly that side effect. This check is a diagnostic, not a candidate; the confirm seasons were not touched for it.
* **Idea 5.** Play-by-play gave 12,998 team-games and a rating for all 6,499 finished games; no scored game lacked one. Splitting EPA into offence and defence was worse than the blend on the tune seasons in all six variants. Net EPA lost in step 14, the split loses here: the closing line already carries this. Stopped, as ordered.
* **Fallbacks:** in every stage the count of scored games missing an input is 0 (`scored_games_missing_an_input` in each `final-<stage>.json`), so no variant was scored on the blend's own number.

### Review round 1 (on `c0cbc4e`, before cleanup)

| Reviewer | Verdict | Report |
|---|---|---|
| `ecc:code-reviewer` | WARNING. No CRITICAL, no HIGH, no leak found. 2 MEDIUM, 7 LOW | `~/.claude/plans/nfl-pickem-lanes-reviews/s14b-r1-code-reviewer.md` |
| `ecc:silent-failure-hunter` | No HIGH. 5 MEDIUM, 10 LOW | `~/.claude/plans/nfl-pickem-lanes-reviews/s14b-r1-silent-failure-hunter.md` |

Neither reviewer could run the tests (their sandbox could not reach the lane database); the coordinator's own runs are the test evidence.

Rulings:

* **Accepted, fixed in the runner (coordinator's file):** the script exits non-zero when the baseline differs from step 14's stored numbers or when the recomputed step 14 candidates differ (a cut-short download can no longer pass quietly); it prints, per input column, how many scored games were missing it.
* **Accepted, fixed in WO-3:** no in-place change of the shared frames and no ninefold recomputation in `idea_preds`; one helper for "missing input keeps the blend's number" and one for "only games with a price"; `calibrated` clips before taking log-odds; `offence_defence` lost its broad `except`; spread divided by total is missing when the total is not above 0.
* **Accepted as a finding, no code change (M1, both reviewers):** recency weights also change the penalty. The clause and its variants were frozen before the result, so the verdict stands as run; the tune-only check above shows the effect and it weakens the idea further.
* **Accepted as a finding (M2):** Shin equals additive with two outcomes. Already in the assumptions; the tables say three distinct methods.
* **Kept as built:** bench-only functions stay in `analytics/backtest.py` (lane-owned file; a new module would be outside the lane's files). `add_features` is not refactored to call `market_logit` (the live path stays untouched).
* **Carried, advisory:** a fit drops training rows with a missing input without printing a count (none of the scored inputs were missing here; the split ratings miss only each team's first game of 2002); `market_logit` and `calibrated` clip without counting; a moneyline of 0 behaves differently by method (existing `implied_prob` has no guard); a probability of exactly 0.5 counts as an away pick (existing); NaN cluster keys are not refused; step 14's EPA rating input was not rescaled, so the fit's penalty shrank its weight by an estimated fifth (idea 5 used fixed scales; it still lost).

AGENTS: `ecc:code-reviewer`, `ecc:silent-failure-hunter` ran. `ecc:security-reviewer` and Dwight not run: no auth, user input, database query or new network path; the runner downloads from the same nflverse host through the app's existing download function and reads one committed JSON file. `ecc:python-reviewer`, `ecc:pr-test-analyzer` not run: standard-size work item. `ecc:planner`, `ecc:architect`, `ecc:code-explorer` not run: the plan and the seam files came with the dispatch. `ecc:mle-reviewer` is the fresh critic (section 5).

## 4. CLEANUP

Explicit scope-locked refactor pass on the touched code (`/refactor` rules: behaviour unchanged, touched functions only), done by Codex in work order 3 (`wo-3.md`, gpt-6-luna), commit `7aec8c6`.

* **Simplified:** `_predict_or_blend` replaces eleven copies of one expression across `candidate_preds`, `idea_preds` and `split_preds`; `_market_games` replaces three copies of the closing two lines; `idea_preds` builds its seven input columns once and attaches them with `assign` (it used to write into each of the nine Elo frames); the two hard-coded method tuples became `DEVIG_METHODS[1:]`; `offence_defence` went from hand-unpacked `first_*` / `second_*` names and a `try/except` to one loop over the two sides; the two clip limits in `calibrated` are named constants.
* **No change needed:** `metrics.py`, `market.py`, `model.py` and `features.market_logit` are already minimal.
* **Proof after the edit:** `tests/test_model.py` 34 passed (`green-3.log`); ruff clean; all six stages rerun on the final code (`final-<stage>.json`) and compared with the first runs key by key: identical in every number.
* **Remaining findings, classified:** all advisory, listed under "Carried" above.
