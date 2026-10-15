# Step 18m: simulator key numbers (|margin| 3 and 7) — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · security Dwight ·
integrator god. Worktree `.claude/worktrees/lane-web`, branch `lane/web`, fast-forwarded to origin/main `325f541` under
`res:git-integrate`. Coord task #39. Grant: god a0a460 (sim/params.py, game.py, distributions.py, __init__.py, new
keys.py; analytics/sim_backtest.py; tests/test_sim.py, test_sim_backtest.py; docs/model/SIMULATOR.md; this log and
evidence; 18c `confirm-result.json` regenerated plus a `confirm-result-pre18m.json` copy, as in 18k). engine.py and jobs.py
untouched.

## 1. PLANNING

**Goal (god 84b3fe).** The simulator gives far too few final margins of exactly 3 and 7 (about 7 and 5 percent against
14.8 and 8.0 real in the 18c confirm). Fix it; report before/after key-number rates and cover/over Brier on the same
seasons. Done = key-number rates near history, cover/over Brier and interval coverage not worse, CI green, critic PASS.

**Cause (read `sim/distributions.py`).** `paired_residual` draws `round(mu) + residual` per side, the residual taken from
a past game. Football's lumpiness is in the final margin, not in a residual around a rounded mean, so the sum smears it.

**Data.** Public nflverse `games.csv` (nfldata), rows before 2026-10-15 (D72), no database, no paid call. Tune seasons
2012-2021 (D18); confirm 2022-2025.

**Spike (tune seasons only, `step-18m-evidence/spike.py`, not production).** Real |margin| 3 / 7 on 2012-2021: 14.1 / 8.9
percent; today's sampler 7.5 / 4.8.
- (a) Exponentially tilted pool of real regulation score pairs (optionally kernel-weighted by expected points): 3/7 fixed
  (13.9 / 9.0) but margins too wide (sd 14.3-14.7 vs 13.7; randomized-PIT 80 percent coverage 84 vs 82). Rejected
  (`spike-tilted-pool.json`).
- (b) Keep `paired_residual`, reweight each final draw by r(|m|)^alpha, r = real/simulated frequency of each exact
  |margin| on the training window, then exponentially re-tilt the weights so the mean margin and total are unchanged,
  and resample. alpha 1.0: 14.7 / 9.3, but football-only cover Brier worse with a 95 percent interval above zero
  (+0.0011, +0.0002..+0.0019). alpha 0.75: 12.7 / 8.1, every cover, over and CRPS interval includes zero, sd and
  coverage unchanged (`spike-alpha.json`). Chosen design (god a0a460 approved).

**Tier T2** (model output shown on the game page). Prior decisions: D18 (tune 2012-2021, ship rule), D68, D72, CLAUDE.md
model validation rules; 18c and 18k logs. **Pre-flight.** (1) Problem: exact-margin and spread-push chances near 3 and 7
are wrong by half. (2) Why now: owner card after step 18 landed. (3) Scope: one new sampler option and its bench; cut: a
total-points key-number fix, any change to expected points. (4) Success: simulated 3/7 rates near the real ones with no
loss in cover/over Brier, CRPS or coverage. (5) Two-way door (a default and a constant; old stored parameters keep working).

**Assumptions.** validated: cause and fix on tune seasons (spike). assumed: the confirm seasons behave like the tune
seasons. Honesty note: 2022-2025 were already looked at once in 18c, so the confirm here is a check, not a fresh holdout.

**Skills.** grep/read of `sim/` and the 18c/18k logs pinned the seam; `/jevgrep` N/A (exact files); TDD (pytest at the
public seam `simulate_game`, `learn_params`, `sim.keys`, bench functions); `/ponytail` in each work order; Design Gauntlet
N/A (no new screen); security review: Dwight (stored-parameter JSON read by the engine).

## 2. SPECIFICATION (frozen before production code)

Sampler (`backend/nflpi/sim/`):
- K1 `DISTRIBUTIONS` gains `"key_weighted"`. With no ratio (`key_ratio == ()`) or `key_alpha == 0` it returns exactly the
  `paired_residual` draws for the same seed.
- K2 With a ratio favouring 3 and 7 it puts more mass on |margin| 3 and 7 and keeps the mean margin and total.
- K3 `keys.key_weight(a, b, rng, ratio, alpha)` keeps the mean margin and total of its input draws and returns as many.
- K4 `learn_params` learns `key_ratio` (a tuple of `KEY_MAX + 1` positive floats, `KEY_MAX = 60`) from its own rows:
  (real count + 0.5) / (simulated count + 0.5) per |final margin|, simulated with `paired_residual` from the learned
  pool; and sets `key_alpha = keys.KEY_ALPHA`.
- K5 The ratio is deterministic and does not depend on row order.
- K6 Playoff games never end tied.
- K7 `SimParams` stored before 18m (no key fields) still load and simulate; new ones round-trip through the engine's
  JSON storage unchanged.
- K8 `learn_params` on 40,300 rows stays under 3 s.

Bench (`analytics/sim_backtest.py`):
- KB1 `pick_alpha`: the largest alpha in `KEY_ALPHAS = (1.0, 0.9, 0.8, 0.75, 0.5)` whose cover-Brier, over-Brier and CRPS
  paired-bootstrap 95 percent intervals (alpha minus `paired_residual`, per game) all have a lower end at or below zero
  (not significantly worse) for both sources; 0.0 if none. (Corrected before any code, Ryan f6dd59: the first text said
  upper end, which is not the rule the spike used.)
- KB2 `keys_tune` refuses confirm seasons and never reads them.
- KB3 `keys_tune` reports, per source, the real 3/7 rates and for the baseline and every alpha: key3, key7, CRPS, cover
  and over Brier (pushes out), margin sd, randomized-PIT coverage at 50/80/95, and the three intervals.
- KB4 `keys_confirm` needs the keys-tune record, runs once (exclusive create) and reports before/after per source.
- KB5 `keys.KEY_ALPHA` equals the recorded keys-tune alpha, and `DEFAULT_DISTRIBUTION` is `key_weighted` when it is
  above zero, else `paired_residual`.

Gate: `uv run pytest tests/test_sim.py tests/test_sim_backtest.py` (here with `--noconftest`: these files do not use
the database, and the Mac test database is down with Docker off; PR CI runs them with the database), ruff; then ONE
keys-tune run and ONE keys-confirm run with their numbers in section 3; PR CI the full suite.

**Red** (`--noconftest`, base `325f541`): 12 failed (K1-K7 ImportError / missing `key_ratio`; KB1-KB5 missing bench
functions and record), 71 passed. K8 passes today (it guards speed once the ratio is learned).

## 3. IMPLEMENTATION

- WO1 (Ryan, try 1) `f439e5b`: `sim/keys.py`, `key_ratio`/`key_alpha` with defaults, `key_weighted`. Coordinator rerun:
  82 passed (`--noconftest`), KB red as planned, ruff 0.
- KB1 rule text corrected before any bench code (`e8d0720`, Ryan f6dd59): lower end of each interval at or below zero.
- WO2 (Ryan, try 1 after re-issue) `a238966`: `pick_alpha`, `keys_tune`, `keys_confirm`, CLI. Rerun: 86 passed, KB5 red
  until the tune record exists; ruff 0.
- **Keys-tune run (ONCE, 2012-2021, 2,576 games, 10,000 simulations, 2,000 bootstrap resamples, 53 s CPU)** on public
  nflverse `games.csv` filtered to rows before 2026-10-15 (sha256 `08a09c14…ab1cc63`): `step-18m-evidence/keys-tune.json`,
  `keys-tune.log`. Real |margin| 3 / 7: 14.1 / 8.9 percent.

  | source | variant | 3 / 7 | cover Brier | over Brier | CRPS | margin sd | 80% coverage (PIT / inclusive) |
  |---|---|---|---|---|---|---|---|
  | football_only | paired_residual | 7.5 / 4.8 | 0.2565 | 0.2568 | 15.222 | 13.74 | 81.7 / 82.8 |
  | football_only | alpha 1.0 | 14.7 / 9.3 | 0.2572 | 0.2569 | 15.217 | 13.71 | 81.7 / 83.0 |
  | market_informed | paired_residual | 7.6 / 5.0 | 0.2503 | 0.2502 | 14.865 | 13.47 | 81.8 / 83.0 |
  | market_informed | alpha 1.0 | 14.7 / 9.3 | 0.2508 | 0.2501 | 14.860 | 13.64 | 82.5 / 83.7 |

  Intervals for alpha 1.0 (difference, 95 percent): football cover +0.0007 (-0.0002..+0.0015), over +0.0001
  (-0.0001..+0.0003), CRPS -0.005 (-0.012..+0.002); market cover +0.0005 (-0.0004..+0.0013), over -0.0001
  (-0.0003..+0.0001), CRPS -0.005 (-0.012..+0.003). **Rule picks alpha = 1.0.** Honest reading: cover Brier is slightly
  worse in the point estimate and the football-only interval only just includes zero (the spike, on other seeds, put it
  just above zero); "not significantly worse", not "better". Smaller alphas trade 3/7 accuracy for a smaller cover cost
  (0.75: 12.7 / 8.1, cover +0.0004).
