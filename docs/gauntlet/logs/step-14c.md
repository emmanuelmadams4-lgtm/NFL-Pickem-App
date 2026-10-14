# Step 14c log: model ideas, round three (lane modelc)

Lane coordinator: Darryl (hive `worker-modelc`). Mode: Gauntlet ONE_SHOT, tier T3. Branch `lane/modelc`, base `main` at `53660d0`.
Evidence folder: `docs/gauntlet/logs/step-14c-evidence/`. Gate: `bash docs/gauntlet/logs/step-14c-evidence/gate.sh <label>`.

## In plain words

* **What this step builds:** nothing for the screen. The owner asked (2026-10-13): "all we really need is to update the model according to the machine learning and data influenced techniques from the github". The repo review listed what other people's models do. Steps 14, 14b, 8b and 9 tested most of it and none won. This step tests what is left that the bench can test, one idea at a time, and gives an honest "ships" or "does not ship" for each.
* **What it replaces:** nothing, unless an idea wins. A winner is committed here as a tested change with its proof; wiring it into the live model is a seam message to the integrator (this lane may not touch the engine, the worker, the API or the web app).
* **What it is not:** not a new data source, not a change to the ship rule (the owner's call), not a change after one bad week.

Words used below. **Log loss:** a score for probabilities, lower is better; it punishes being sure and wrong. **Gain:** how much lower an idea's log loss is than today's model (positive is better). **Blend:** today's model: the stats model plus the closing betting line. **Boosted trees:** a model that adds many small decision trees one after another, each fixing the last one's misses. **Early stopping:** stop adding trees when a held-out season stops improving. **Stacked blend:** today's blend and the best tree model averaged with one weight. **Margin model:** predicts the home team's winning margin in points; a win chance comes from "margin divided by a typical miss". **Explosive play:** a pass gaining 20 or more yards or a run gaining 10 or more. **Tune seasons:** 2012 to 2021, where a setting may be chosen. **Confirm seasons:** 2022 to 2025, looked at once per idea, never used to choose.

## 1. PLANNING

* **Step:** 14c (owner's ask of 2026-10-13, lane map "Lane modelc"). Dependencies: steps 14, 14b, 8b, 9 landed. `NEEDS: (none)`.
* **Scope (god's dispatch):** in this order, one at a time: (1) boosted trees on the blend's inputs, then on a wider set; (2) stacked blend; (3) margin and total model turned into a win chance, alone and as an input to the blend; (4) explosive-play rate as a pregame rating (stop at the first miss; skip if play-by-play needs anything the bench does not already use); (5) confidence points, a finding for the pick sheet, no probability changes.
* **Out:** `predictions/engine.py`, `jobs.py`, the API, the web app, the shared package, any new data source, any new dependency, any migration, any change to the ship rule.
* **Done when:** each idea has a walk-forward verdict on real nflverse data with every variant logged, tune gain beside confirm gain; the code is tested (one test per frozen clause that fails when the clause is broken); the gate is green twice on the final commit; a new critic passes; lane guard is clean.
* **Files this lane may edit** (`lanes.md`): `analytics/model_c.py`, `tests/test_model_c.py`, the bench files of 14, 14b, 8b and 9, this log and `step-14c-evidence/**`. Existing bench files are touched only by adding to them; this step needs no edit to any of them.
* **One-way doors:** none. Reversibility: two-way. Deployment reach: none.
* **Prior decisions relied on:** CLAUDE.md "Model validation requirements"; owner decision 2026-10-12 (each idea tested first, ships only if it wins; no change after one loss); steps 14, 14b, 8b and 9 logs (the bench, the rule, what already lost); `hive/research/model-repos-review.md` Part 2 and Part 5 (ideas only; no repo code copied).
* **Rigor tier:** T3 (it can change the model).

### Product Mode pre-flight

1. **Problem:** the owner wants the live model to borrow what works from strong public models.
2. **Why now:** the owner asked today; the review named trees, a stacked blend, a score model and play-quality ratings as untested or only partly tested.
3. **Scope:** the five items above on data the bench already reads. Cut: opening line and line movement (no history before 2026), any new data source, any live wiring.
4. **Success metric:** confirm-season log-loss gain over the blend with a paired-bootstrap 95% interval; accuracy as the guard.
5. **Reversibility:** two-way.

### Assumptions

| Assumption | State |
|---|---|
| The model to beat is the walk-forward `p_blend` of `analytics/backtest.py`, window 10 seasons; the baseline must equal step 14's stored numbers (market 0.6094, blend 0.6107 on 3,649 games; confirm 1,084 games) | validated by the runner on every run (it stops if they differ) |
| Boosted trees overfit small data (about 250 priced games a season, about 2,500 in a 10-season window). The repo review's own evidence: one repo's XGBoost (58.9%) is far below its logistic (67.4%) | stated; the tuning gain is printed next to the confirm gain for every variant so a gap is visible |
| `roof` is known before kickoff. `temp` and `wind` in nflverse are the conditions recorded at the game, not a forecast; using them is a small look-ahead (a forecast stand-in). They are missing for domes, which trees take as missing | stated; labelled in the verdict; it can only flatter the "wide" tree set, so a pass there would need the owner |
| The spread and total columns are the closing line (`spread_line` is positive when the home team is favoured, validated in step 14b) | validated |
| Margin model: step 9's `ScoreModel` (least squares on home score and road score) predicts home margin = home minus road. Its line-based features come from the closing line | validated (step 9 code) |
| Explosive plays: passes of 20+ yards and runs of 10+ yards, from nflverse play-by-play through the app's existing download function (same host, retries, timeout as step 14b's idea 5). Nothing is cached on disk by the bench; step 14b downloaded the same files the same way | stated; no new host, no new dependency |
| This is the eighth or later confirm look across steps 14, 14b, 8b and 14c (step 14: 2 candidates; 14b: 5 new; 8b: 2; this step: up to 6 more). A pass at 95% two-sided is about a 1 in 40 false alarm for one candidate; across about 15 looks it is about a 1 in 3 chance that at least one passes by luck even if none is real | stated in the verdict. A narrow pass is "needs the owner", not a win |

### Skills and tools

| Skill | Use |
|---|---|
| `/jevgrep` | Recorded in the evidence folder (`jg-1.log`). |
| `/graft` | N/A: seam files named in the dispatch and read whole. |
| `/tdd` | No project `tdd` skill. Failing tests first, written by the coordinator (section 2). |
| `/ponytail` | In every work order: smallest correct diff, no new dependency, plain functions. |
| `harness-engineering` | N/A: no runner, evaluator service or approval boundary is created. |
| Design Gauntlet | N/A: no user interface. |
| Parallel Lanes | Lane claimed (`claims/modelc`), own worktree, own state file, coord task #29. |

EFFORT: PLANNING and SPECIFICATION high (session setting, not changed).

## 2. SPECIFICATION

Public seam: `nflpi.analytics.model_c` (new file), built on the step 14 bench (`backtest._elo_frames`, `_train_rows`, `predict_season`, `evaluate`, `LogitModel`, `ScoreModel`, `epa_diff`). No existing file is edited.

### Frozen acceptance criteria (functional layer)

| ID | Clause |
|---|---|
| T1 | `TREE_SETS["core"]` is the blend's five inputs; `TREE_SETS["wide"]` is those plus `spread_line`, `total_line`, `rest_diff`, `roof_indoor`, `temp_f`, `wind_mph`, `div_flag`. `TREE_GRID` is depth {2,3} x smallest leaf {30,80} (four settings per set, eight variants), learning rate 0.05, at most 300 trees. Variant names are `p_tree_<set>_d<depth>_l<leaf>` |
| T2 | `tree_inputs(frame)` returns a copy with `roof_indoor` (dome or closed 1, outdoors or open 0, missing stays missing) and `div_flag` (1 or 0); the input frame is not changed |
| T3 | `TreeModel.fit_early(train, features, depth, leaf)`: fit on every training season except the last one, count the trees that minimise log loss on that last training season (at least 1), refit on all training seasons with exactly that many trees. Missing inputs are allowed (trees take them as missing); rows without a result are dropped |
| T4 | `tree_preds(df, seasons, window)` scores the same games as the step 14 bench, carries `p_blend`, and adds the eight variants. Every fit, early-stopping set included, uses only the `window` seasons before the test season. No number moves when the result of a game in that week or later changes. A game missing an input a variant cannot take (the price) keeps the blend's number |
| S1 | `stack_weight(p_blend, p_tree, y)` is the weight on the grid 0, 0.05, ..., 1 that minimises log loss of `(1-w) p_blend + w p_tree`; a tie goes to the smaller weight |
| S2 | `stacked(preds, tree_col)` for season S uses the weight fitted on seasons before S in `preds` only; the first season is missing |
| G1 | `margin_to_prob(margin, sigma)` is the normal cdf of margin / sigma; sigma must be positive and finite; a missing margin stays missing |
| G2 | `margin_sigma(train, features)` is the standard deviation of the miss in home margin, where each training season's margin is predicted by a `ScoreModel` fitted on the other training seasons (so the spread is not shrunk by fitting and scoring the same games) |
| G3 | `margin_preds(df, seasons, window)` carries `p_blend` and: `p_m_stats` (margin from the stats features, no line, as a win chance), `p_m_line` (margin from the stats plus line features), `p_m_in_stats` (blend inputs plus the stats margin / 7), `p_m_in_stats_total` (plus the stats total points (total - 45) / 10), `p_m_in_line` (blend inputs plus the line model's margin / 7). Training rows use the out-of-season margin of G2; test rows use the fit on all training seasons; sigma comes from the training seasons only. Nothing uses a season at or after the test season; no number moves when the result of that week or a later game changes. A game missing a line keeps the blend's number in the two line variants; a line is never invented |
| E1 | `explosive_net(rows)`: per team and game, own explosive rate minus the opponent's in the same game, in the `game_id, team, net_epa` shape that `epa_diff` reads. A game without two sides or with zero plays is left out for both |
| E2 | `explosive_preds(df, seasons, explosive, window)`: for half-life 4, 8, 16 games a pregame rating (the step 14 rule, earlier games only), home minus away, times 50; the blend's inputs plus that rating, fitted on the window before the test season; a game without a rating keeps the blend's number. No number moves when a game in that week or later changes |
| P1 | `week_points(week, order)`: games of one week get points week-size down to 1 in the given order; `expected` is the sum of points times the chance of the picked side, `actual` the sum of points of the games picked right. Picked side = home when the chance is above one half, else away. Orders: `sort` (highest chance first, ties by game id), `market` (by the market's chance), `kickoff` (earliest game most points), `reverse` (lowest chance first), `oracle` (right picks first). An unknown order raises `ValueError` |
| P2 | `points_order(week, "sort")` equals what `predictions.sheet.order` gives with no AI evidence, so the sheet today is the sort |
| P3 | `swap_ceiling(week)` is the most expected points the sheet's tie rule can give up: scan the sorted picks the way `sheet.order` does and add the chance gap of each adjacent pair closer than 0.01 that it would swap (non-overlapping) |
| P4 | `points_report(preds)`: per order the mean expected and actual points per week, per season, `sort_minus_order_actual` (mean and paired-bootstrap 95% interval with weeks as the units), `swap_ceiling_per_week` |
| C1 | `evaluate_c(preds, candidates, tune, confirm, cluster)` returns exactly what `backtest.evaluate` returns plus `all_variants`: for every variant its tune gain, its confirm gain (a point value, never used to choose or to ship) and `gap` = tune gain minus confirm gain. Overlapping tune and confirm seasons raise `ValueError` |
| X1 | Nothing existing changes; every existing test stays green and unedited |

User-facing layer: N/A (no screen). The owner-facing output is this log's verdict table.
Operational layer: `run.py <stage>` runs from a clean checkout against live nflverse files, prints JSON with `allow_nan=False`, fails loudly on a download error, and its baseline must match step 14 (market 0.6094, blend 0.6107, 3,649 games; confirm 1,084 games).

### Protocol, frozen before any result was seen

* Baseline `p_blend`; tune 2012 to 2021; confirm 2022 to 2025; window 10. Data: live nflverse `schedules/games.csv` (and play-by-play for idea 4), read through the app's download function. The stack weights need earlier walk-forward history, so trees, stack and margin stages also score 2008 to 2011 (history only; scored for tune and confirm only from 2012).
* **Ship rule, unchanged from step 14:** the low end of the game-level paired-bootstrap 95% interval of the confirm log-loss gain above 0, and accuracy not lower. The season-week cluster interval is printed beside it and never decides.
* **Power limit, said in every verdict:** the confirm set is 1,084 games; it cannot show a gain under about 0.001 log loss.
* For each candidate every variant is scored on the tune seasons; the variant with the largest tune gain is the one scored for the ship decision on the confirm seasons. The confirm gain of the other variants is printed as a point value with the gap to the tune gain (descriptive; it chooses nothing). No variant is added after a result is seen. A losing candidate is logged as lost.
* Candidates, each one confirm look: `tree_core` (4 variants), `tree_wide` (4), `stack` (2 variants: fitted weight, fixed one half; the tree is the one with the largest tune gain over all eight, a tune-only choice), `margin_alone` (`p_m_stats`, `p_m_line`), `margin_input` (`p_m_in_stats`, `p_m_in_stats_total`, `p_m_in_line`), `explosive` (3 half-lives; stop at the first miss, no further variant). Idea 5 (confidence points) changes no probability and has no ship decision.
* "Stop" rule: idea 4 runs after 1 to 3 regardless of their result (the owner's order); it is one candidate. No follow-up idea is gated on confirm results.
* Six confirm looks here after nine before them: stated with the verdict.

### First failing tests

`backend/tests/test_model_c.py`, written by the coordinator before any production code. Red for the intended reason (`red-1.log`): `ImportError: cannot import name 'model_c' from 'nflpi.analytics'`. The 34 step 14, 14b tests in `test_model.py` still pass (`baseline-test_model.log`).

## 3. IMPLEMENTATION

Provider: the dispatch said try Codex once. `codex exec` with the default model refused: `The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account` (`step-14c-evidence/codex-wo1.log`). Per the dispatch, each bounded work order then went to a Sonnet subagent (never Opus for building, never the critic). The coordinator wrote the spec and the tests first, read every diff, and reran the proof itself.

| Work order | Builder | Result | Commit |
|---|---|---|---|
| WO-1 trees, stack, `evaluate_c` (`wo-1.md`) | Sonnet subagent, try 1 | 10 tests green after I fixed one flaw in my own test data (the stacked test's "earlier results teach 2022" check used a case where the weight stays at 1 either way) | `b18f017` |
| WO-2 margin, explosive, points (`wo-2.md`) | Sonnet subagent, try 1 | 12 of 13 green; the 13th failed because **my test was wrong** (I asserted that the oracle order has more expected points than the sort; the sort maximises expected points by definition). I corrected the test, not the code | `b18f017` |

CLIMBS: none. STRIKES: none. Jev was not asked for model picks: the dispatch fixed the builder (Sonnet after the Codex refusal). EFFORT: session setting unchanged. After both work orders: `tests/test_model_c.py` 22 passed (`green-1.log`), ruff clean. The 34 earlier `test_model.py` tests are untouched and green.

## 4. What the real data says

Run: `cd backend && uv run python ../docs/gauntlet/logs/step-14c-evidence/run.py <stage>`, against live nflverse files, 2026-10-13, one stage at a time in the dispatch's order, each under a gate lock (`locked-stage.sh`). Stored: `run-<stage>.json` (trees, stack, margin, explosive, points). Walk-forward, window 10 seasons, 3,649 regular-season games with a closing line, 2012 to 2025; tune 2,565 games; confirm 1,084 games in 72 season-weeks. Run time: trees 107 s, stack 150 s, margin 3 s, explosive 73 s (24 seasons of play-by-play, 12,998 team-games, 6,499 rated games), points 6 s.

**Baseline check (operational layer):** market 66.57%, log loss 0.6094; blend 66.46%, 0.6107. On the confirm seasons: market 67.80%, 0.6082; blend 67.53%, 0.6095. Equal to step 14's stored numbers; the runner stops if they ever differ. No scored game lacked a spread, total or margin input (`scored_games_missing_an_input` is 0 in every file).

Gain = how much lower the idea's log loss is than the blend's (positive is better). Interval = paired bootstrap, 95%, game by game (this is the rule). "By week" = the same when whole season-weeks are resampled (beside it, never decides). Label (owner brief D68, section 6): **market-informed** = the model reads the closing line or a number derived from it; **football-only** = it does not.

### Verdict table

**Read this first: the confirm set is 1,084 games. It cannot show a gain under about 0.001 log loss. Every "No" below means "no gain this test can see", not "proven useless". This is the sixteenth confirm look in all (the critic corrected "eighth or later"): steps 14, 14b, 8b and this step have each looked at the confirm seasons for 2, 5, 2 and 6 candidates, 15 in all. For one candidate a pass at this rule is a roughly 1 in 40 false alarm; across 15 looks, if none of the ideas were real, there would be about a 1 in 3 chance that at least one passes by luck (somewhat less, since the candidates overlap). So a narrow pass would have been "needs the owner", not a win. None passed.**

| # | Candidate | Label | Chosen on 2012 to 2021 | Tune gain | Confirm gain | Interval (the rule) | Interval by week | Accuracy change | Ships |
|---|---|---|---|---|---|---|---|---|---|
| 1a | Boosted trees, blend's five inputs | market-informed | depth 2, leaf 30 | -0.00448 | **-0.00664** | -0.01183 to -0.00118 | -0.01219 to -0.00083 | +0.18 points | **No** (clearly worse) |
| 1b | Boosted trees, wider set (line, total, rest, roof, weather, division) | market-informed | depth 2, leaf 30 | -0.00453 | -0.00552 | -0.01119 to +0.00033 | -0.01165 to +0.00108 | -0.46 points | **No** |
| 2 | Stacked blend: blend and best tree, one weight fitted on prior seasons | market-informed | fitted weight (tree: 1a's winner) | -0.00027 | -0.00062 | -0.00152 to +0.00037 | -0.00157 to +0.00043 | -0.28 points | **No** |
| 3a | Margin model turned into a win chance (alone) | `p_m_line` market-informed; `p_m_stats` football-only | line-based margin | -0.00026 | +0.00014 | -0.00428 to +0.00440 | -0.00380 to +0.00404 | +0.65 points | **No** |
| 3b | Margin and total as extra inputs to the blend | market-informed | stats margin and total | +0.00068 | -0.00093 | -0.00406 to +0.00236 | -0.00431 to +0.00212 | -0.55 points | **No** |
| 4 | Explosive-play rate rating | market-informed (added to the blend) | half-life 16 games | -0.00003 | -0.00008 | -0.00046 to +0.00031 | -0.00046 to +0.00028 | -0.28 points | **No** |
| 5 | Confidence points order | n/a (no probability changes) | | | | | | | **Finding, below** |

**In plain words:** none of the candidates beats the current model, so **the live model does not change** and there is no seam for the integrator. The trees are not just "no gain": on the confirm seasons the tree on the blend's own inputs is clearly worse (interval wholly below zero). That fits the review's warning that trees overfit about 250 games a season; the stacked blend (which gives the tree only 5% to 25% of the weight, per season) comes out at zero within noise, which is what a blend of "same as today" and "worse" should do. Nobody should read the margin model's `+0.00014` or the margin-input tune gain of `+0.00068` as a signal: the first has an interval of plus or minus 0.0043, and the second turned into `-0.00093` on the confirm seasons.

### Every variant tried (tune seasons, 2,565 games, beside the confirm seasons, 1,084 games)

Confirm gains for non-chosen variants are descriptive point values; they chose nothing and nothing was added or dropped after seeing them. The gap is tune minus confirm (a large positive gap = it looked better in tuning than it was).

| Candidate | Variant | Tune gain | Confirm gain | Gap |
|---|---|---|---|---|
| 1a | core, depth 2, leaf 30 (chosen) | -0.00448 | -0.00664 | +0.00216 |
| 1a | core, depth 2, leaf 80 | -0.00686 | -0.00664 | -0.00022 |
| 1a | core, depth 3, leaf 30 | -0.00553 | -0.00740 | +0.00187 |
| 1a | core, depth 3, leaf 80 | -0.00655 | -0.00710 | +0.00055 |
| 1b | wide, depth 2, leaf 30 (chosen) | -0.00453 | -0.00552 | +0.00099 |
| 1b | wide, depth 2, leaf 80 | -0.00503 | -0.00583 | +0.00080 |
| 1b | wide, depth 3, leaf 30 | -0.00652 | -0.01077 | +0.00426 |
| 1b | wide, depth 3, leaf 80 | -0.00855 | -0.01488 | +0.00633 |
| 2 | fitted weight (chosen) | -0.00027 | -0.00062 | +0.00035 |
| 2 | fixed one half | -0.00066 | -0.00228 | +0.00163 |
| 3a | stats margin, no line (football-only) | -0.01544 | -0.02156 | +0.00612 |
| 3a | line margin (chosen) | -0.00026 | +0.00014 | -0.00040 |
| 3b | + stats margin | -0.00006 | +0.00003 | -0.00009 |
| 3b | + stats margin and total (chosen) | +0.00068 | -0.00093 | +0.00161 |
| 3b | + line margin | -0.00011 | +0.00058 | -0.00069 |
| 4 | half-life 4 games | -0.00017 | -0.00020 | +0.00003 |
| 4 | half-life 8 games | -0.00008 | -0.00012 | +0.00004 |
| 4 | half-life 16 games (chosen) | -0.00003 | -0.00008 | +0.00006 |

That is every variant: 8 tree settings, 2 stack variants, 5 margin variants, 3 explosive half-lives. Nothing else was scored. Wider trees overfit more (gap grows with depth: +0.00426 and +0.00633 for depth 3). The stack weights fitted on prior seasons ran from 0.05 to 0.25 (`run-stack.json`).

Notes: the tree on the wider set uses temperature and wind **as recorded at the game** (a forecast stand-in, labelled in the assumptions); it still lost. The margin model's football-only variant (`p_m_stats`, no betting line at all) is 0.0154 log loss worse than the blend on the tune seasons, the same size of gap that step 9 found between the stats model and the line. Trees, margin and explosive stages scored every game with every input present (0 fallbacks to the blend's number except coincidences where the two numbers matched: `variant_columns_equal_to_blend` in each file).

### Idea 5: confidence points (a finding for the pick sheet; no probability changes)

Setting: each week of the 3,649 scored games (243 weeks, about 15 games a week; only games with a closing line are scored) gets points from the week's size down to 1. Today's sheet orders by win chance, highest first, and only swaps two neighbours less than one point apart when the AI's evidence disagrees (`sheet.order`). Without that AI evidence the sheet **is** the pure sort (clause P2, tested). Per week, 2012 to 2025, with the confirm seasons beside it:

| Order | Expected points per week | Actual points per week (all) | Actual, confirm seasons | Sort minus this order, actual (all), 95% by week |
|---|---|---|---|---|
| Pure sort by our win chance (today's sheet without AI evidence) | 86.41 | 86.87 | 87.71 | |
| Sort by the market's win chance | 86.26 | 87.03 | 88.06 | -0.16 (-0.47 to +0.16) |
| Earliest kickoff gets the most points | 80.32 | 80.89 | 82.93 | +5.98 (+4.56 to +7.47) |
| Lowest chance gets the most points | 74.26 | 73.81 | 76.39 | +13.07 (+11.14 to +15.12) |
| Perfect hindsight (right picks first) | 84.84 (not a real order) | 103.84 | 105.42 | -16.97 |

What the owner can conclude: ordering by win chance is worth about 6 points a week over ordering by kickoff, and the gap's interval is well above zero. Sorting by the market's chance instead of ours is a statistical tie (-0.16, interval spans zero). The AI tie-break can give up at most **0.017 expected points a week** (the "swap ceiling": every neighbouring pair closer than one point swapped) and it cannot be replayed in the past because no AI evidence was stored for past seasons, so its actual effect is unmeasured and small by construction. What the owner cannot conclude: whether going against the crowd (pick shares) pays in his group; that needs his group's pick shares, which this bench does not have. Hindsight at 103.84 is the ceiling no order can reach; the sort sits at 83% of it.

## 5. VERIFICATION

**Gate ruling (god, decision D71, 2026-10-14):** the Mac cannot finish a full test run in useful time tonight (out of memory). The FULL GATE on the final head is the CI of the lane's pull request, which god opens: alembic upgrade and check, the whole pytest suite, ruff, the web build and types, the browser suite and the docker build, on the merge with main. God merges only if it is green. This lane ran only its own test files locally.

- **Gate 1 (earlier, on head b476ebb, base a028f2a):** 1483 passed in 679.54 s; ruff clean; alembic "no new upgrade operations"; generated API types: no drift. The four small gate 1 logs (under 16 KB each) are kept in `step-14c-evidence/`; the empty gate 2 log was deleted. Gate 2 never finished locally (memory); CI replaces it.
- **Mutation sweeps** (`mutate-sweep1.log`, `mutate.log`): sweep 1 caught 33 of 43; 9 tests added; sweep 2 caught 43 of 43.
- **Own test files, once, 2026-10-14** (database `nflpi-lane-modelb-db` on 127.0.0.1:15448): `tests/test_model_c.py` + `tests/test_model.py`: 61 passed in 339.8 s.
- **Critic (ecc:mle-reviewer, new, no transcript), on head b476ebb: PASS.** It checked every verdict and variant row against `run-*.json` (all match), the ship rule (no candidate has a game-level interval wholly above zero; all `ships` flags false), walk-forward fitting in `model_c.py` lines 1 to 230, and the confirm-look count (2+5+2+6 = 15 earlier looks stated). It reran `test_model_c.py`: 27 passed. Unchecked by it: `model_c.py` after line 230. Findings, none changing a verdict: the "eighth or later" wording (fixed above); "coincidences" for equal columns is unevidenced (at most 19 of 3,649 games); `p_m_stats` uses no line and the log now says so in the notes.
- **Lane-guard** (`lane-guard.py check lanes.md modelc main`): OK.
- **Public names:** none changed; the diff against the base only adds files.

## 6. LANDING

Nothing ships: no seam. The live model does not change. Branch `lane/modelc`, base `a028f2a`; main is now `6c2846a` (docs and `test_model_audit.py` only); no conflict, so no rebase. God opens the PR and merges on green CI.
