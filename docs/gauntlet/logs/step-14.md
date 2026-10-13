# Step 14 log: the model gets better (lane model)

Lane coordinator: Darryl (hive `worker-model`). Mode: Gauntlet ONE_SHOT, tier T3. Branch `lane/model`, base `main` at `d88d74e`.
Evidence folder: `docs/gauntlet/logs/step-14-evidence/`. Gate: `bash docs/gauntlet/logs/step-14-evidence/gate.sh <label>`.

## In plain words

* **What this step builds:** a fair test bench. It takes one idea for a better model, replays past seasons, and says "ships" or "does not ship" by the plan's rule. Two ideas go through it, in the plan's order: (1) refit the model's weights every week on games already played, (2) add a team rating built from EPA per play (EPA = expected points added, a measure of how much each play helped).
* **What it replaces:** nothing yet. The live model changes only if an idea wins, and wiring a winner into the live app is a later step (wave 5), because this lane may not touch the engine, the worker or the API.
* **What it is not:** not the weekly scorecard on the Results screen (that needs the API and the web app: wave 5), not a new odds source, not a change after one bad week.

## The owner's question: is the model updated to 2026?

**No for the weights, yes for the team ratings.** Read from the code, not from the live database (the live app is off limits to this lane):

* `jobs.train` calls `engine.train(session, through_season=season - 1)` (`backend/nflpi/jobs.py:47`). In the 2026 season that is `through_season = 2025`.
* `engine.train` fits on `train_window_seasons` (10, `backend/nflpi/config.py:28`) seasons ending there (`backend/nflpi/predictions/engine.py:99`): **seasons 2016 to 2025**. No 2026 game is in the weights.
* The worker retrains only when the active model's `trained_through_season < season - 1` (`jobs.py:144`): once per season.
* Elo (the team strength ratings) is recomputed from every finished game on each refresh, so 2026 results do move the ratings each week, and the market line is this week's.
* Candidate 1 below is exactly the missing piece: refit the weights each week with the 2026 games already played. Section 3 says whether it helps.

Not checked: the `model_versions` row in the live database. It should read `trained_through_season = 2025`.

## 1. PLANNING

* **Step:** PLAN.md row 14, step 14 of 17. Dependencies: none (`NEEDS: (none)` in `lanes.md`).
* **Scope (god's dispatch, 2026-10-13):** test the listed candidates one at a time, in order, starting with the in-season refit. A candidate ships only if it beats the current blend by the plan's rule. If none wins, the step lands the evidence and no model change. **Out:** `predictions/engine.py`, the API, the web app, `jobs.py`, any market or odds source not already in the app. So the row's "weekly scorecard on Results" is not in this lane (wave 5).
* **Done when:** both candidates have a walk-forward verdict from real nflverse data, logged with every variant tried; the harness is tested; gate green twice on the final commit; a new critic passes; lane guard clean.
* **Files this lane may edit:** `predictions/{model,features,elo,market}.py`, `analytics/{backtest,metrics}.py`, `tests/test_model.py`, this log and its evidence folder.
* **Rigor tier:** T3 (the plan's tier). One-way doors: **none**. No schema, no API contract, no live model change. Reversibility: two-way.
* **Deployment reach:** none. Nothing here runs in the live app until wave 5 wires a winner.

### Product Mode pre-flight

1. **Problem:** the owner picks every game each week and wants the model to get better at choosing winners over time, with proof, not hope.
2. **Why now:** owner decision 2026-10-12 (the model must improve; every idea tested on past seasons first). He asked on 2026-10-13 whether the model knows about 2026.
3. **Scope:** a comparison harness plus two candidates. Cut: live wiring, the scorecard, "other" candidates beyond the two the plan names.
4. **Success metric:** log loss of the recommendation on 2022 to 2025 against the current blend (paired bootstrap 95% interval), with accuracy as the guard.
5. **Reversibility:** two-way.

### Assumptions

| Assumption | State |
|---|---|
| The "current model" to beat is the walk-forward `blend` in `analytics/backtest.py` (stats + closing line), window 10 seasons | validated (PLAN.md bar, CLAUDE.md decision 2026-10-11) |
| "Tune on 2012 to 2021, confirm once on 2022 to 2025" is done in code: the variant is picked on the tune seasons, then scored once on the confirm seasons | validated (PLAN.md row 14, B9) |
| "Weeks already played" means games that kicked off before the week's first kickoff (a postponed game is not "played") | assumed; stricter reading, costs nothing |
| nflverse `stats_team/stats_team_week_<season>.csv` carries `passing_epa` and `rushing_epa` per team per game, summed from play-by-play, for 2002 to 2025 | validated (all 24 files downloaded 2026-10-13; 0 missing values in the 2010 file) |
| A winner cannot go live in this lane (engine and worker belong to other lanes) | validated (`lanes.md`) |

### Instrumentation

North star: confirm-period log loss gain against the blend. Baseline: the blend's own walk-forward numbers from the same run. Read by: `candidates.py` in the evidence folder, which prints the table and saves the JSON. Guardrail: accuracy must not drop. Check date: each time a new candidate is proposed.

### Skills and tools

| Skill | Use |
|---|---|
| `/jevgrep` | `jg 0.8.0`: "Where are the live model weights fitted, on which seasons, and when are they refit?" ranked `engine.py` (train, lines 95 to 128) and `jobs.py` first. That pinned the answer to the owner's question. `JEVGREP: ready`. |
| `/graft` | N/A: the seam files were named in the dispatch and read whole (six files, 500 lines). |
| `/tdd` | No project `tdd` skill. Rules from the gauntlet skill: failing tests first, written by the coordinator; see section 2. |
| `/ponytail` | In every work order: smallest correct diff, no new dependency, no registry or plug-in layer. |
| `harness-engineering` | N/A: no runner, evaluator service or approval boundary is created; the harness is two pure functions. |
| Design Gauntlet | N/A: no user interface. |
| Parallel Lanes | Lane claimed (`claims/model`), own worktree, own state file, coord task #9. |
| Headroom | `HEADROOM: not-routed` (`headroom doctor`: 1 failure, 5 warnings). Not a blocker. |

Coordinator note: coord registered me twice (`--session model` = s29, and the edit hook's own session = s26). The edit hook refused my files while s29 held them, so task #9 and the locks were handed to s26. Same agent.

## 2. SPECIFICATION

Public seam (confirmed from the plan: the walk-forward backtest module is where a model is judged):

* `metrics.game_log_loss(p, y)`, `metrics.paired_gain(p_new, p_old, y)`
* `backtest.inseason_blend(frames, season, window)`, `backtest.candidate_preds(df, seasons, window=10, epa=None)`, `backtest.evaluate(preds, candidates, tune, confirm)`
* `features.team_game_epa(rows)`, `features.epa_diff(df, epa, half_life)`

### Frozen acceptance criteria

Functional layer:

| ID | Clause |
|---|---|
| S1 | `game_log_loss` returns one loss per game; its mean is `log_loss`. |
| S2 | `paired_gain` reports `n`, `log_loss_gain` = mean of (old loss minus new loss) per game, and `accuracy_diff` = new accuracy minus old accuracy. Both intervals come from one bootstrap of the per-game differences (paired). |
| S3 | `ships` is a plain `bool`, true only when the low end of the log-loss gain interval is above 0 **and** accuracy did not drop. |
| S4 | In-season refit: a game is predicted with blend weights fitted on the prior `window` seasons plus same-season games that kicked off before that week's first kickoff. Week 1 therefore equals the season-level blend. |
| S5 | In-season refit never uses the result of a game in the same or a later week, nor of a postponed game that had not been played. |
| S6 | In-season refit never trains on a season older than the window or newer than the test season. |
| S7 | `evaluate`: for each candidate, every variant is scored on the tune seasons and listed; the variant with the largest tune gain is chosen; only that variant is scored on the confirm seasons; `ships` is the confirm verdict. Seasons outside both lists are ignored. |
| S8 | `candidate_preds` scores only games that have a market line, for the seasons asked, and carries the baseline `p_blend` beside each candidate column. |
| S9 | `team_game_epa`: a team's EPA per play in a game is (passing_epa + rushing_epa) / (attempts + sacks_suffered + carries); its net value is its own minus its opponent's in the same game. A game with a missing or zero-play side is left out for both teams. |
| S10 | `epa_diff`: before each game, a team's rating is the weighted mean of its net EPA per play in earlier games only, weight halving every `half_life` games; the feature is home rating minus away rating; a team with no earlier rated game gives a missing value (never an invented one). |
| S11 | The EPA candidate fits on seasons before the test season only, and falls back to the baseline blend probability where the feature is missing. |
| S12 | Nothing existing changes: `BASE_FEATURES`, `BLEND_FEATURES`, `run_backtest` output and every existing test stay as they are. |

User-facing layer: N/A (no screen in this lane). The owner-facing output is this log's plain-words verdict and the table in section 3.
Operational layer: `candidates.py` runs from a clean checkout against live nflverse files, prints the verdict table and exits non-zero on a download failure. Its baseline numbers must match the documented ones (market 66.6%, blend 66.5%, 2012 to 2025).

### Protocol (B9), frozen before any result was seen

* Baseline: `p_blend` from `predict_season`. Tune seasons 2012 to 2021, confirm seasons 2022 to 2025, window 10.
* Candidate 1, `inseason_refit`: one variant, no knob.
* Candidate 2, `epa_rating`: `BLEND_FEATURES + epa_diff`, half-life 4, 8 or 16 games (three variants, fixed here).
* Ship rule: PLAN.md row 14. Low end of the paired-bootstrap log-loss gain interval on 2022 to 2025 above 0, and accuracy not lower.
* Every variant's tune numbers are printed. The confirm period is scored once, for the chosen variant only.

### First failing tests

Committed with this section, before any production code. Red for the intended reason (the seam does not exist):
`ImportError: cannot import name 'candidate_preds' from 'nflpi.analytics.backtest'` (`step-14-evidence/red-1.log`).

### Baseline

`gate.sh baseline` on `d88d74e`: see section 3.
