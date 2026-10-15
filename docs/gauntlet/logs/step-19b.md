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
