# Step 9 of 17: Tiebreaker scores

Session: owner's Mac, 2026-10-13, lane `scores` (worktree `.claude/worktrees/lane-scores`, branch `lane/scores`, base `main@d88d74e`), wave 4, run beside lanes alerts, news, model, coaches, sdk and group.
Coordinator: Claude (hive temp "Meredith", dispatched by the integrator). Builder: Codex. Lane claim `claims/scores`, coord task #5.
Evidence folder: `docs/gauntlet/logs/step-9-evidence/` (every log named below lives there unless a full path is given).

## 1. PLANNING
* **In the owner's words (D5):** "Predicted scores for two games only: Sunday night and Monday night (the Yahoo tiebreakers). No most/least-points team. Must be backtested before it ships." This step builds the score maths and the test that decides which score the app will show. It replaces nothing. It is not: the API, the web screen, the pick sheet, the worker, or `predictions/engine.py` (all wave 5).
* **Roadmap row:** PLAN.md row 9: predicted score for both teams in the two Yahoo tiebreak games, backtested against the line-implied score. Gate: MAE (mean absolute error: the average miss in points) against the implied score on 2022 to 2025, interval reported; ships only if it wins.
* **Tier:** T3 (the row's tier). Reversibility: two-way (two new modules and one test file; nothing calls them yet; no schema, API or stored data).
* **Decisions relied on:** D5 (above); the Yahoo rule looked up 2026-10-12 (`OWNER_DECISIONS_2026-10-12.md` line 334: ties break on closest total points, then home points, then road points); `CLAUDE.md` model rules (walk-forward by season only, no post-game data, closing line only as a labeled benchmark or blend, "better than X" needs a paired-bootstrap 95% interval that excludes zero, never invent data). The dispatch cites "Q9": no item carries that label in the decisions file.
* **Scope, and what is cut:** `backend/nflpi/predictions/scores.py`, `backend/nflpi/analytics/score_backtest.py`, `backend/tests/test_scores.py`. Cut: any caller (API, sheet, worker, web), storing a score, picking which two games are the tiebreakers (already in `predictions/sheet.py`), tuning of any setting.
* **Pre-flight:** Problem: Yahoo asks the owner for a final score in two games a week and he has no evidence-based number to type. Why now: the pick sheet (step 4) already names the two games; the score is the missing box. Scope: as above. Success metric: team-score MAE on 2022 to 2025 against the line-implied score, with total-points MAE beside it. Reversibility: two-way.
* **Assumptions:** `validated` nflverse `spread_line` is positive when the home team is favoured: on seasons up to 2021 only, its correlation with the home margin is +0.426 (`s9-explore.log`). `validated` no game from 2002 to 2025 lacks a spread or total in the schedule file (same log). `validated` 1,087 regular-season games in 2022 to 2025. `assumed` the nflverse line is the closing line (as `analytics/backtest.py` says), so the line score is a benchmark with a timing advantage over anything known mid-week, and a blend inherits it. `assumed` the two tiebreak games are the Sunday night and Monday games (D5); the gate uses every regular-season game for sample size and reports the two slots beside it.
* **Leak guard for the decision itself:** the candidates, their inputs, the metric and the ship rule were frozen and committed (`RED` commit below) before any 2022 to 2025 score was read. The only look at real data before the freeze used seasons up to 2021.
* **Instrumentation:** none added. PROCEEDING WITHOUT: nothing runs in the app yet; the operational record is the reproducible report (`s9-backtest.py`, one command) and its saved output.
* **Skills:** `/jevgrep`: `nfl-pickem-lanes-logs/s9-jg-seam.log` ranked `ingestion/service.py`, `ingestion/nflverse.py` and `models.py`; it showed the spread and total are parsed (`_spread`, `_total`), stored on `market_snapshots`, and dropped before the model frame (`jobs.py:64`), so no score code exists to reuse. `/graft`: N/A (file homes fixed by the lane map). `tdd`: no project tdd skill; the coordinator wrote the failing tests before any production code. `ponytail`: in every work order. `harness-engineering`: N/A (no runner or approval boundary). Design Gauntlet: N/A (no screen).
* **Tools:** `JEVGREP: ready` (`jg doctor` exit 0). `HEADROOM: not-routed` (doctor exit 2; not a blocker). Codex: `codex-cli 0.156.1`.
* **Test database:** own container `nflpi-lane-scores-db` on `127.0.0.1:15446`, no volume. The live stack on 5432 and 8000 is never used. Full runs take the shared lock `res:gate` (`s9-gate.sh`).
* **Security review:** not required by the dispatch rule: the new modules add no file, network or database access (criterion S15 tests this). The evidence scripts read the schedule file through the existing `nflverse.fetch_csv`.
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low (Codex builds); VERIFICATION high.

## 2. SPECIFICATION
Public seam (new files only): `nflpi.predictions.scores` (`implied_score`, `entry`, `tiebreak_score`, `scoring_form`, `add_score_features`, `ScoreModel`, `FORM_GAMES`, `STATS_FEATURES`, `BLEND_FEATURES`) and `nflpi.analytics.score_backtest` (`METHODS`, `predict_season`, `summary`, `pick_winner`, `is_tiebreak_slot`, `run_score_backtest`).
Gate: `backend/tests/test_scores.py`, then the full suite, ruff, `alembic check`, `npm run gen:api` with no drift, twice on the final commit; plus the real-data run and an independent hand check (S16).

Three methods are compared: `implied` (the betting line), `stats` (no betting line) and `blend` (line plus stats).

| # | Criterion (frozen) | Layer |
|---|---|---|
| S1 | `implied_score(spread, total)` = home `(total + spread) / 2`, road `(total - spread) / 2`; a positive spread favours the home team. It is `None` when either number is missing, not finite, the total is not above zero, or the spread is larger than the total | functional |
| S2 | `entry(points)` is the whole number typed into Yahoo: round half up, never below zero | functional |
| S3 | `tiebreak_score(spread, total)` is the app's answer today: `{home, away, method: "line_implied"}` from S1 and S2, or `None` when the line is missing. A model replaces it only after it wins S11 | user-facing |
| S4 | `scoring_form(df, games=FORM_GAMES)`: for each side, the mean points scored (`pf`) and allowed (`pa`) in that team's last `games` finished games before this one (both scores present, any season, any game type); missing when the team has none. `FORM_GAMES = 16`, fixed before the test, not tuned | functional |
| S5 | No leak: a game's form never changes when its own or any later score changes | functional |
| S6 | `add_score_features(df, elo)` adds `implied_home`, `implied_away` (S1; missing stays missing) and the form columns to the existing pre-game features. `STATS_FEATURES` = Elo gap, home field, two QB-change flags, four form columns; `BLEND_FEATURES` = the two implied columns plus `STATS_FEATURES` | functional |
| S7 | `ScoreModel.fit(df, features)` finds home points and road points by ordinary least squares with an intercept, on finished rows with every feature and both scores present; it raises `ValueError` with fewer rows than numbers to find. `predict` gives a missing prediction for a row with a missing feature | functional |
| S8 | Walk-forward: to test season S, both models are fitted only on seasons `S - window` to `S - 1`; only finished regular-season games of S are tested. Elo runs on its default settings (nothing is tuned) | functional |
| S9 | Every prediction is an `entry` (S2). The `implied` entry is the rounded line score. The `stats` entry does not change when the line changes | functional |
| S10 | `summary(preds)`: per method, `team_mae` = mean of (home miss + road miss) / 2 and `total_mae` = mean miss on combined points; per candidate, gain = line error minus candidate error (positive = candidate closer) with a paired-bootstrap 95% interval for each. With no games every number is null, not NaN | functional |
| S11 | Ship rule: a candidate wins only if its team-score interval lies wholly above zero AND its total-points gain is not below zero. `pick_winner` returns the winning candidate with the larger team-score gain, or `None`. Decided on all tested games, never on a subset | functional |
| S12 | `is_tiebreak_slot(weekday, kickoff)`: Monday, or Sunday at 7:00 pm Eastern or later | functional |
| S13 | `run_score_backtest(df, seasons, window=10)` returns `seasons, games, methods, comparisons, by_season, tiebreak_slots, ships` as plain JSON values, the same on every run; `tiebreak_slots` is the S10 summary of the S12 games, reported only | operational |
| S14 | Every method is scored on the same games: a game any method cannot predict is left out for all | functional |
| S15 | The two new modules do no file, network or database access | operational |
| S16 | On the real nflverse schedule, 2022 to 2025: the report is saved with its intervals, and the `implied` numbers equal an independent count that uses no project code | user-facing |

Decisions (each two-way):
* **Ship metric.** `JEV: policy:scores:ship-metric -> total_points_error 0.52 (unsure)`. `ADVISOR: sonnet -> both (team-score interval win AND total points not worse), unsure`. Coordinator took the advisor's stricter rule (S11): it satisfies the plan row ("MAE vs implied score"), honours Yahoo's first tiebreak (total points), and a wrong "no" only keeps the trusted line score. Both metrics are reported with intervals, so a different rule can be read off the same report. Revisit trigger: the owner wants total points alone to decide. Carried to the integrator because the advisor was not sure.
* **Candidates fixed in advance:** two, `stats` and `blend`, one fixed feature list each, no setting tuned (form window 16 games, train window 10 seasons, default Elo). Two candidates are tested against one benchmark with no correction for the second look; the report says so.
* **Entries, not raw decimals, are scored**, because a whole number is what gets typed (S9).
* **Elo on default settings** rather than the per-season tuned grid in `analytics/backtest.py`: that helper is private to lane model's file and tuning is not needed to answer the question.
* `JEV: model:scores:wo-1 -> sol 0.79, medium 0.76 (both just under sure)`. `ADVISOR: sonnet -> gpt-6-sol medium`. Start rung `gpt-6-sol`, medium.

Red: `s9-red.log`, `ImportError: cannot import name 'score_backtest' from 'nflpi.analytics'` at collection. Right reason: the modules do not exist. The tests were written together by the coordinator (the builder never writes its own bar), every expected number worked out by hand in the test comments.
BUILD_RUNG: gpt-6-sol medium (try 1 of 2). Reason: two small pure modules, but a leak or an off-by-one in the form or the walk-forward split would silently corrupt the ship decision.

### Spec amendments after the freeze
All came from the review of WO-1 (section 3). Red for each was written by the coordinator before the fix: `s9-red-2.log` (12 failed, 38 passed).
* **S2, S3, S9 (pair rounding).** New `entry_pair(home, away)`: each side is an `entry`, except when both numbers end in exactly .5: then the home side rounds up and the road side rounds down, so a whole-number line total is kept (line 44 with spread 3 is typed as 24-20, not 24-21). `tiebreak_score` and every backtest entry use it. Why: the first rule added a point to the total on those lines, and total points is Yahoo's first tiebreak. **This changes the benchmark after the 2022 to 2025 result was seen**, so the choice was made on other data: on 5,136 regular-season games of 2002 to 2021 the pair rule cut the line's total-points miss from 10.6377 to 10.6275, and "home up" was the best of three ways to split (`s9-rounding-pre2022.log`). It can only make the benchmark harder to beat. Both results are kept: before `s9-backtest-before-pair-rule.log`, after `s9-backtest.log`. The verdict is the same in both.
* **S11 (minimum sample).** `MIN_SHIP_GAMES = 200`: no candidate wins on fewer than 200 games (under one season). Why: on one game the interval has zero width and anything "wins".
* **S10.** `summary` raises `ValueError` when a prediction or a score is missing, instead of returning NaN.
* **S13.** `run_score_backtest` puts the games in kickoff order itself (the form and Elo read row order as time order), raises `ValueError` for an empty or repeated season list, and returns one more key, `excluded`: tested games left out under S14.
* Two coordinator tests added after WO-1 pin clauses that had no killing test: default Elo, the ten-season default window, and the decision on all games (`test_s8_s11_the_run_uses_default_elo...`).

## 3. IMPLEMENTATION
Provider: Codex, every production line. The coordinator wrote the tests, the evidence scripts and this log, inspected each diff (`git status`, `git diff`, untracked files) and reran every proof itself.

| Work order | Rung | Decision | Result (coordinator's own rerun) | Commit |
|---|---|---|---|---|
| WO-1 the two modules (`wo-1.md`) | `gpt-6-sol` medium, try 1 | `JEV: model:scores:wo-1 -> sol 0.79, medium 0.76`; `ADVISOR: sonnet -> sol medium` | 42 of 42 (`s9-wo1-proof.log`), ruff clean, 2 files in scope | `bf3613e` |
| WO-2 review fixes + pair rounding (`wo-2.md`) | `gpt-6-luna` medium, try 1 | `JEV: model:scores:wo-2 -> luna 0.97, medium 0.84` (follow) | 50 of 50 (`s9-wo2-proof.log`), ruff clean, 2 files in scope | `1c5e104` |

CLIMBS: none. STRIKES: none. Codex could not run `uvx ruff` in its sandbox on WO-3 and reported a lint error in the test file on WO-2 (the coordinator's own long line, fixed by the coordinator); the coordinator ran ruff itself each time.

**Review fan-out on `bf3613e`** (read-only, reports in `~/.claude/plans/nfl-pickem-lanes-reviews/`):
* `ecc:code-reviewer` (`s9-wo1-code-reviewer.md`): APPROVE, 0 CRITICAL, 0 HIGH, 1 MEDIUM, 4 LOW. It could not reach the test database, so it read the code only. MEDIUM: rounding both halves up adds a point to the total (fixed, pair rule). LOW: caller must sort (fixed), empty seasons crash (fixed), redundant copy (removed in cleanup), naive timestamp and the `BLEND_FEATURES` name clash (carried).
* `ecc:silent-failure-hunter` (`s9-wo1-silent-failure-hunter.md`): 3 HIGH, 8 MEDIUM, 3 LOW, all by reading. Fixed in WO-2: F1 ship on a tiny sample, F2 uncounted exclusions, F3 unsorted frame, F4 duplicate seasons, F8 NaN in `summary`. Rejected: F11 (old franchise codes are already mapped in `nflverse.parse_games`). Carried: section 6.
* `ecc:security-reviewer` and Dwight: not run. Reason: the dispatch asks for a security review only when file or network access is added; the modules are pure maths on a frame (S15 tests it).

**Real-data result (S16), 2022 to 2025, 1,087 regular-season games, 0 excluded** (`s9-backtest.log`, full numbers `s9-report.json`; schedule file sha256 `4a493272693cdb79`):

| Method | Team-score miss | Total-points miss | Against the line: team gain (95%) | Total gain (95%) | Wins |
|---|---|---|---|---|---|
| Betting line (closing spread and total) | 7.140 | 10.180 | | | |
| Stats model, no line | 7.344 | 10.435 | -0.204 (-0.299 to -0.107) | -0.255 (-0.431 to -0.074) | no |
| Stats model + line | 7.151 | 10.235 | -0.011 (-0.051 to +0.027) | -0.054 (-0.140 to +0.029) | no |

A positive gain would mean the candidate was closer than the line. **Nothing ships. The line-implied score stays the answer** (`tiebreak_score`).
* The stats model is clearly worse than the line on both measures (both intervals wholly below zero).
* The blend is not different from the line: both intervals include zero, and it is a little worse on both.
* Sunday night and Monday games only (152 games, reported, not the gate): line 7.099 / 10.289, stats 7.099 / 10.368, blend 7.062 / 10.401; no interval excludes zero.
* By season the order never flips in a way that matters: the blend is ahead on team score in 2022 and 2024 and behind in 2023 and 2025.
* Limits, said plainly: two candidates were tried against one benchmark with no correction; the line is the closing line, which the owner does not have mid-week; the average miss is about 7 points per team and 10 on the total for every method, so a typed score is a best guess, never a "lock".
* **Hand check:** `s9-handcheck.py` (csv and math only, no project code) recounts the line's numbers: 18 of 18 MATCH (games, both misses, per season, and the two-slot subset), and shows three games worked through (`s9-handcheck.log`).

## 4. CLEANUP
`/refactor` pass by the coordinator, scope-locked to the two modules (its `guide.md` was not re-read; the catalog names below are from the skill's table). Analysis: no long function (largest is `summary`, about 30 lines), no deep nesting, two duplications, one dead call.

| Smell | Transformation | Done by | Proof |
|---|---|---|---|
| The six `pred_*` column names were built twice | Extract constant `PRED_COLS` | Codex `gpt-6-luna` low, WO-3 (`wo-3.md`) | 50 of 50 (`s9-wo3-proof.log`) |
| `predict_season` turned a pair of number lists into two entry columns twice | Extract function `_entry_columns` | same | same |
| `.copy()` after `add_features`, which already returns a new frame | Remove dead code | same | S5 and S6 tests still green |

`JEV: model:scores:wo-3 -> luna 0.86 (sure), effort medium 0.37 (unsure)`; the coordinator took `low` from the skill's effort table for cleanup, because the full test file, the mutation pass and the gate all check it. Commit `c8def6e`. After the cleanup the real-data report is byte-identical to the one before it (`cmp` on `s9-report.json`). No change needed, with reasons: `summary` stays one function (splitting the method loop from the comparison loop would add a second pass over the same arrays); `BLEND_FEATURES` keeps its frozen name (carried). Left as findings: section 6.
