# Step 19b: confidence-pool points bench and candidates — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web-19b` from origin/main `cde9f14` (19a landed). Grant: god 65e0b3,
2026-10-15 16:53 UTC: `backend/nflpi/analytics/points_bench.py`, `backend/tests/test_points_bench.py`, this log and
`step-19b-evidence/**`. Public nflverse release CSVs only; no database, no Docker, no spend. Bench code only: a winning
candidate ships under a separate grant.

## 1. PLANNING

**Goal (god bf613c, 65e0b3).** The owner's league is a confidence pool: each week every game gets a unique 1..N weight
and a right pick scores its weight. Measure points per week for market, blend and stats, then score four pre-registered
candidates once each against the live blend.

**What exists (read on origin/main; exploration log in this session).**
- `picks/pool.py:18` `confidence_pool`: share = win + half tie; sort by share descending, ties by game id; weights N..1.
- `analytics/backtest.py` `elo_frames(df)` and `predict_season(frames, season, window)`: walk-forward per season on a
  DataFrame (no database); columns `p_market`, `p_blend`, `p_logistic` (stats).
- `analytics/metrics.py:87` `bootstrap_ci(values, reps, seed)`; `game_log_loss`.
- `analytics/report.py:69` `guard_scored`: D72 guard (no game on or after 2026-10-15 is scored).
- `model_c.week_points` always picks and weights by `p_blend`, so it cannot score the market's own picks: not reused.
- `features.qb_changes`: `*_qb_change` = 1 when the starter differs from the team's previous game this season; it has no
  direction (god 7f480e: Lamar Jackson returning was scored like a backup coming in).
- Data: nflverse `games.csv` (public). The 14c points script calls `bt._elo_frames`, gone from main: outside this
  grant; carried.

**Tier T2** (new decision support numbers; no user-facing change in this step). Prior decisions: D18 (owner), D71, D72,
AUDIT A10/A11/A14, god 65e0b3 (ship rule below). **Pre-flight.** (1) Problem: the owner scores points, but every bench
so far scored log-loss or accuracy. (2) Why now: the season is live; step 19 is the model step. (3) Scope: one bench
module; cut: shipping any feature (separate grant), live wiring, web. (4) Success: a points/week number per model with
its 95% interval, and one ship verdict per candidate. (5) Two-way door: bench code only.

**Assumptions.** validated: all inputs are DataFrame-based (read). assumed: tied games are left out, as in every bench
(A14). unknown: whether any candidate wins (A10: the model differs from the market in 72 of 3,649 games).

**Skills.** grep/read and an exploration agent pinned the seams above; TDD with pure pytest (no database); `/ponytail`
in each work order; security review: low risk (public CSV read, no auth, no database), Dwight asked for a light read.

## 2. SPECIFICATION (frozen before production code)

**Ship rule (god 65e0b3, pre-registered).** Base = the live blend `p_blend`. PRIMARY: points/week gain on 2022-2025,
scored with `pool.confidence_pool`, week-cluster paired bootstrap 95% interval lower bound **> 0**. GUARDS (all must
hold): accuracy not lower (`accuracy_diff >= 0`); log-loss gain point estimate `>= 0`; 2012-2021 walk-forward
points/week gain point estimate `>= 0`. One win in four looks is weaker evidence and will be said so.

`backend/nflpi/analytics/points_bench.py`:
- B1 `points_week(frame, prob_col) -> DataFrame` one row per (season, week), sorted: `points`, `max_points`, `correct`,
  `n`. Each game becomes `GameInputs(game_id, p_home_win=p, p_away_win=1-p)`; picks and weights from
  `pool.confidence_pool` (default rules); a pick scores its weight when its side won (`home_win` 1 = home). B1b equal
  shares order by game id (the live rule).
- B2 the named column picks AND orders; nothing is taken from `p_blend` unless it is named.
- B3 `compare(frame, cand_col, base_col, seasons, reps=2000, seed=7) -> dict`: rows of `seasons` where both chances are
  finite (a game missing either is left out of both sides); `n_weeks`, `n_games`, `points_gain` (mean over weeks of
  cand − base points), `points_gain_ci` ([lo, hi] from `bootstrap_ci` over the per-week differences: weeks are the
  resampled unit), `accuracy_diff` (per game, cand − base), `log_loss_gain` (mean base − cand game log-loss). B3b the
  same seed gives the same dict.
- B4 `decide(test, guard) -> dict` with `ship` True only when the primary and all three guards hold;
  `TEST_SEASONS = 2022..2025`, `GUARD_SEASONS = 2012..2021`.
- B5 `compare` refuses (D72 error) a frame with a scored game on or after 2026-10-15 (reuse `report.guard_scored`).
- B6 `qb_direction(df)` adds `home_qb_in`, `home_qb_back`, `away_qb_in`, `away_qb_back` (see c1).
- B7 `python -m nflpi.analytics.points_bench <games.csv> <out.json> [candidate]`: builds the walk-forward frame
  (`elo_frames` once, `predict_season` for 2012-2025, window 10, REG games, ties left out), writes the baseline
  (points/week, interval, accuracy for `p_market`, `p_blend`, `p_logistic`; `compare` market vs blend and stats vs
  blend on both windows) and, when a candidate is named, its `compare` on both windows and `decide`.

**Pre-registered c1 (signed QB change), defined before any run.** For a team's game with `*_qb_change == 1`, count
each QB's starts for that team earlier in the same season (before this game). `*_qb_back = 1` when the new QB's count
is at least the previous game's QB's count and above 0 (a starter returning); otherwise `*_qb_in = 1` (a backup coming
in). Both 0 without a change. Model c1 = the walk-forward blend with `home_qb_change`/`away_qb_change` replaced by the
four columns (stats model and blend refit the same way as `predict_season`, window 10, same Elo tuning). Candidate column
`p_c1`, scored once against `p_blend` with `decide`.

c2 (fitted mix weight), c3 (non-QB injuries, as-of), c4 (play-by-play efficiency) are pre-registered in this log before
each is scored. "Fresher line timing" is untestable on history (only closing lines exist; no pregame quote history);
19a does it live.

Gate: `uv run pytest --noconftest -q tests/test_points_bench.py`; `uvx ruff check nflpi tests`; the B7 run on the
public `games.csv` (rows before 2026-10-15) with its JSON in `step-19b-evidence/`. PR CI runs the full suite (D71).
**Red (local):** 13 failed: `ImportError` (no `points_bench`); B5 fails on the same import.

## 3. IMPLEMENTATION

- WO1 (Ryan, try 1) `c4c1d5a`: `points_bench.py` (B1-B7, c1). Committed by the coordinator (builder `.git` read-only).
  Coordinator rerun: 13 passed, ruff 0. Alignment check on the real file (not a scoring run): in every Elo frame,
  `*_qb_in + *_qb_back == *_qb_change` on every row and game ids match the games order (867 "backup in", 364 "starter
  back").
- Data: nflverse `games.csv`, rows before 2026-10-15 (sha256 `08a09c145930747d…`, the 18m file).

**Baseline** (`step-19b-evidence/baseline.json`; tied games left out):

| window | model | weeks | points/week | accuracy |
|---|---|---|---|---|
| 2022-2025 | market | 72 | 88.01 | 67.53% |
| 2022-2025 | blend (live) | 72 | 87.71 | 67.53% |
| 2022-2025 | stats | 72 | 83.36 | 63.65% |
| 2012-2021 | market | 171 | 86.70 | 66.08% |
| 2012-2021 | blend | 171 | 86.61 | 66.02% |
| 2012-2021 | stats | 171 | 84.08 | 64.89% |

Market vs blend: +0.31 pts/week [-0.28, +0.89] (2022-2025), +0.18 [-0.26, +0.60] (2012-2021): no significant
difference. Stats vs blend: -4.35 [-5.78, -2.92]. Note: AUDIT A9 has market accuracy 67.80% on 2022-2025; here 67.53%
(this bench picks home at exactly 0.5, as `choose_su` does, and leaves ties out). Carried; it does not touch the
candidate comparisons (each is vs the blend on the same rows).

**c1 signed QB change: scored once** (`step-19b-evidence/c1.json`). 2022-2025: c1 87.81 pts/week; gain vs blend
**+0.10 [-0.18, +0.39]**, accuracy diff 0.0000, log-loss gain -0.00008 (1,084 games). 2012-2021: +0.03 [-0.16, +0.22],
accuracy -0.0004, log-loss gain -0.00046. **Decision: does not ship** (CI lower bound not above 0; log-loss worse).

**Pre-registered c2 (fitted model + market mix), defined before it is built or scored.** Inputs: the walk-forward
out-of-sample chances `p_market` and `p_logistic` (stats) of every season. For season s, fit a logistic regression of
`home_win` on `[logit(p_market), logit(p_logistic)]` (chances clipped to [0.01, 0.99]) using only the rows of seasons
2012..s-1 with a market; predict season s. Season 2012 (no earlier out-of-sample season) and any game without a market
keep `p_blend`. Candidate column `p_c2`, scored once against `p_blend` with `decide`. Spec B8: `mix_c2(preds) ->
Series` aligned to `preds`; a season's own results never enter its fit; B8b no market → blend. Red: 2 failed
(`AttributeError: no mix_c2`), 13 passed.

- WO2 (Ryan, try 1) `026a0e1`: `mix_c2` and the `c2` CLI choice. Coordinator rerun: 15 passed, ruff 0.

**c2 fitted mix: scored once** (`step-19b-evidence/c2.json`). 2022-2025: c2 87.97 pts/week, accuracy 67.90%; gain vs
blend **+0.26 [-0.10, +0.67]**, accuracy +0.0037, log-loss gain +0.00091 (1,084 games). 2012-2021: +0.19
[-0.09, +0.49], accuracy -0.0016, log-loss gain +0.00081. **Decision: does not ship** (CI lower bound not above 0; the
three guards hold).

**Pre-registered c3 (non-QB injuries), defined before it is built or scored.** Data: public nflverse
`injuries_{season}.csv`, 2009-2025 (17 files; combined sha256 of the per-file sums `f45d18f2535cff0f…`). Each row is a
player's status on that team's final injury report for that week, published before the game (as-of by publication;
nflverse keeps one row per player-week; a later file revision cannot be ruled out: assumed). For each game,
`*_out_nonqb` = the number of that team's players in that season and week with `report_status` "Out" (trimmed, any
case) and `position` not "QB" (QBs are c1's subject; Questionable and Doubtful are not counted). Team codes go through
`nflverse.franchise`. `inj_diff = (home_out_nonqb − away_out_nonqb) / 5`; 0 where no row exists (seasons before 2009
included). Model c3 = the walk-forward blend with `inj_diff` added to the stats and the blend features (refit like c1,
window 10). Column `p_c3`, scored once against `p_blend` with `decide`. Spec B9 `injury_counts(games, injuries)`.
Red: 1 failed (`AttributeError: no injury_counts`), 15 passed.
