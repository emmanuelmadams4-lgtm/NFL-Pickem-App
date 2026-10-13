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
