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
| S13 | Added after review round 1 (tightening only): `paired_gain` raises `ValueError` on empty input, unequal lengths or any non-finite value, so a missing prediction is never scored as a wrong pick. S9 also treats a non-finite value ("nan", "inf") as missing. S10 also refuses rows that are not in kickoff order. |

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

`gate.sh baseline` on `d88d74e` (logs `step-14-evidence/baseline-*.log`):

```text
PASS pytest exit=0 :: 172 passed in 1563.07s (0:26:03)
PASS ruff exit=0 :: All checks passed!
PASS alembic exit=0 :: No new upgrade operations detected.
PASS genapi exit=0 :: no drift
```

The suite takes 26 minutes tonight because six lanes share the machine (load average about 40). During the build only
`tests/test_model.py` is run; the full gate runs on the final commit.

Commit: `a27cfd0` (this section, the gate script, the first failing tests).

## 3. IMPLEMENTATION

Provider: Codex, one bounded work order at a time, prompt on stdin. Models picked through `decide.sh` (decision desk). The coordinator read every diff and reran the proof itself each time.

| Work order | Model, effort | JEV | Result | Commit |
|---|---|---|---|---|
| WO-1 harness + in-season refit (`wo-1.md`) | gpt-6-sol, medium, try 1 | sol 0.82, medium 0.92: follow | 14 of 15 tests passed. Codex stopped and reported that one test of mine was wrong: it flipped every week 3 result, and Elo rightly moves between games of one week. That was the coordinator's fault, not the builder's (Build Ladder rule 2): I fixed the test (flip only from the last game of the week on) and added an "own result" check. No second try was needed. | `b8c2f6c` |
| WO-2 EPA rating (`wo-2.md`) | gpt-6-sol, medium, try 1 | sol 0.82, medium 0.97: follow | 18 passed, first try. | `2c4ece6` |
| WO-3 review fixes + cleanup (`wo-3.md`) | gpt-6-luna, medium, try 1 | luna 0.83: follow. Effort unsure (medium 0.48): I took medium, the higher option, instead of paying for an advisor call on an effort level. | see section 4 | see section 4 |

CLIMBS: none. STRIKES: none. No Codex limit was hit.

### What the real data says

Run: `cd backend && uv run python ../docs/gauntlet/logs/step-14-evidence/candidates.py` against live nflverse files, 2026-10-13. Raw output of the final code: `step-14-evidence/run-3-candidates.json` (section 4). Walk-forward, window 10 seasons, 3,649 regular-season games with a closing line, 2012 to 2025.

**Baseline check (operational layer):** market 66.57% accuracy, log loss 0.6094; blend 66.46%, log loss 0.6107. This matches the documented 66.6% / 0.609 and 66.5%.
On 2022 to 2025 (1,084 games): market 67.80%, 0.6082; blend 67.53%, 0.6095.

Gain = how much lower the candidate's log loss is than the blend's (positive is better). Interval = paired bootstrap, 95%.

| Candidate | Variant | Tune 2012 to 2021 (2,565 games): gain, interval | Accuracy change (tune) | Chosen | Confirm 2022 to 2025 (1,084 games): gain, interval | Accuracy change (confirm), interval | Ships |
|---|---|---|---|---|---|---|---|
| 1. In-season refit | (one) | -0.00015, -0.00058 to +0.00028 | -0.04 points | yes | **+0.00035, -0.00029 to +0.00100** | 0.00 points, -0.37 to +0.37 | **No** |
| 2. EPA rating | half-life 4 games | +0.00019, -0.00007 to +0.00043 | -0.16 points | yes | **-0.00041, -0.00171 to +0.00086** | +0.37 points, -0.28 to +1.02 | **No** |
| | half-life 8 games | +0.00012, -0.00022 to +0.00044 | -0.23 points | no | not scored (by the protocol) | | |
| | half-life 16 games | -0.00015, -0.00034 to +0.00005 | 0.00 points | no | not scored (by the protocol) | | |

Every variant tried is in this table: four in all. Nothing else was run.

**Verdict, in plain words:** neither idea beats the current model. Both intervals include zero, so by the plan's rule neither ships and **the live model does not change**. The size of the effect is also tiny: three to four parts in ten thousand of log loss, where the market itself sits 13 parts ahead of the blend. Refitting weekly barely moves the weights because one season adds about 270 games to about 2,700. The closing line already knows what EPA knows.

**Data note:** nflverse has 12,990 team-game rows for 2002 to 2025. 6,491 of 6,499 finished games got an EPA value. The 8 left out are Jacksonville home games in 2002, where the source file has one row instead of two; they are left out, not guessed. No game scored in the test (2012 on) lacked a rating (`epa_missing_scored_games`, section 4).

### Review round 1 (on `2c4ece6`, before cleanup)

| Reviewer | Verdict | Report |
|---|---|---|
| `ecc:code-reviewer` | APPROVE. No leak, no wrong maths, no misalignment. 1 MEDIUM, 3 LOW | `~/.claude/plans/nfl-pickem-lanes-reviews/s14-r1-code-reviewer.md` |
| `ecc:silent-failure-hunter` | 4 HIGH, 4 MEDIUM, 3 LOW, all about missing values passing silently | `~/.claude/plans/nfl-pickem-lanes-reviews/s14-r1-silent-failure-hunter.md` |
| Dwight (security) | see section 5 | |

Rulings (each accepted finding went back to a failing test first, commit `a3a7a80`, log `red-3.log`):

* Accepted, mapped to the project rule "missing stays missing": `paired_gain` refuses missing or empty input (S13); "nan" and "inf" EPA values count as missing (S9); `epa_diff` refuses rows out of kickoff order (S10); the script prints with `allow_nan=False` and reports how many rows it read, kept and scored without a rating.
* Kept as frozen: the EPA candidate falls back to the blend where the rating is missing (S11). The count is now printed, and it is 0 for the scored games.
* Carried, advisory: per-reason drop counts in `team_game_epa`; a unique `game_id` check; a count of tied games; a check that tune and confirm seasons do not overlap; `fetch_csv` does not chain the original error (lane coaches owns that file).

AGENTS: `ecc:code-reviewer`, `ecc:silent-failure-hunter` ran. `ecc:security-reviewer` not run: the security review is Dwight's by the dispatch. `ecc:python-reviewer`, `ecc:pr-test-analyzer` not run: work item is "standard" size (no security surface, public API or new dependency). `ecc:planner`, `ecc:architect`, `ecc:code-explorer` not run: the plan and the six seam files were given by the dispatch.
