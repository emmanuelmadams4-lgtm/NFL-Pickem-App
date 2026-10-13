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
