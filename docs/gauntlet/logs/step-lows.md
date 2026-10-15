# HAG-82: carried LOWs cleanup — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web-lows` from origin/main `984de84` (19b landed; upstream unset so a
push can only go to `lane/web-lows`). Grant: god f555db, 2026-10-15 17:16 UTC. Limits: `engine.py` only the sim-params
load and the 19a block; `test_sim.py` K10 only; `check18k.spec.ts` wording only; no migration, no new API field.
Database tests prove in draft-PR CI (Mac test database off; Docker stays off).

## 1. PLANNING

**Goal.** Close the LOW findings carried from 13b, 18l, 18m, 19a and 19b that god put IN scope (f555db). Each item was
located on origin/main by an exploration agent (none fixed yet; 18m's Dwight review has N1 and N2 only).
**OUT (parked on the card by god):** 13b `train()` move and `ai`→`api.readmodels` layering; the simulator zero floor
(needs the sim bench); the stale news badge (a feature); 19a L2 stays refuse-and-log.

**Tier T1** (fixes with no new user-facing behaviour except one wording). Prior decisions: D71 (PR CI is the full
gate), D72, god 57e1b4 (19a guards), 65e0b3 (19b rule). **Assumptions.** validated: every location read on
origin/main. assumed: book prices are never stored twice for one observed time (`save_prices` skips a stored key), so
L2's rows come from many observed times. **Skills.** exploration agent + grep pinned each seam; TDD (one red test per
item, `tests/test_lows.py`); `/ponytail` per work order; security review: Dwight (database reads, logging, file writes).

## 2. SPECIFICATION (frozen before production code)

Simulator (18m):
- L-N1 `keys.key_weight` returns `(a, b, weighted)`; `simulate_game` labels `key_weighted` only when `weighted`, else
  `paired_residual` (a NaN ratio must never show as key-weighted).
- L-N2 non-convergence (and L-ESS) warn once per process at WARNING (module flag `keys._warned`), later ones at DEBUG.
- L-ESS when the effective number of draws `1 / Σw²` is under 10% of n, the draws are returned unweighted
  (`weighted=False`).
- L-R1 `learn_key_ratio` raises `ValueError` ("whole") on a finite but non-whole final score (no silent `np.rint`).
- L-pools `learn_params` with float scores gives `int64` residual pools.
- L-K10 `test_sim.py` K10 forces real non-convergence (NaN ratio) instead of `TILT_STEPS = 0`, and unpacks the new
  3-tuple.
- L-L3 `sim_backtest.write_tune` creates its file exclusively (`FileExistsError` if it exists).
- L-L1/L4 (DB) `engine.load_sim_params`: `key_ratio` loads as a tuple; one that is not KEY_MAX+1 finite positive
  numbers is dropped (`key_ratio = ()`, so the simulator runs unweighted and is labelled so) with a WARNING naming
  `key_ratio`.
- L-R2 (DB) `load_sim_params` logs a WARNING naming the season when no parameters are stored (a failed train no
  longer means a silent season without simulations).

Value ratings (18l):
- L-D1 `ValueRatingOut.expected_value` rejects NaN and ±inf (`Field(allow_inf_nan=False)`).
- L-D2 (DB) a rating that cannot be computed warns once per process per (game, market, side) (`readmodels.
  _warned_ratings`), DEBUG after.
- L-L2 (DB) `value.load_snapshots` gives the same answer but loads only the chosen pair's rows: one aggregate query
  finds, per book, the newest observed time and line with every side present; one row query reads those rows. A newer
  lone side still never wins.

Fresh line (19a):
- L-19a-dead remove the dead `or line_only` term in the non-line alert branch.
- L-19a-L1 the churn rule keeps a previous quote only while it is at most `FRESH_MAX_AGE` old (an nflverse previous
  line is unaffected).
- L-19a-L6 `market.novig_home_prob` returns `None` for a NaN moneyline.
- L-19a-L4 (DB) a `pregame_quotes` error is logged (WARNING, "quotes") and the frame uses the nflverse line.
- L-19a-L7 (DB) an unreadable stored `market_seen_at` is treated as missing; the frame still builds.

Week read (13b):
- L-dup (DB) `readmodels.summaries` for one week reads the predictions table once (`sheet.compute_week` takes the
  recommendations already read); the summaries are unchanged.
- L-gate `tests/test_layering.py` gains `private_reaches(rel, tree) -> list` used by its tests: it resolves relative
  imports (`from ..api import _x` inside `ai/`) and flags `getattr(module, "_name")` on another package's module. If
  the stricter gate finds real violations in `nflpi/`, the builder reports them; they are fixed only if one line each.

Points bench (19b):
- L-19b-out `points_bench.write_report(path, output)`: exclusive create and `allow_nan=False` (no file left on error);
  `main` uses it.
- L-19b-D72 `_summary` calls `report.guard_scored`.
- L-19b-len an assert that the candidate column has one value per prediction row (no test: the assert is the check).

Other:
- L-14c `docs/gauntlet/logs/step-14c-evidence/run.py` calls `bt.elo_frames` (renamed on main).
- L-wording the simulator check cause `provider` reads "Claude's call failed" (`simulation.tsx`; `check18k.spec.ts`
  updated to the same words).

Gate: `uv run pytest --noconftest -q tests/test_lows.py -k "<pure>"` locally (14 pure tests), `uvx ruff check nflpi
tests`, `tests/test_sim.py tests/test_points_bench.py tests/test_fresh_line.py -k test_f` unchanged; the whole file and
the full suite in draft-PR CI from `lane/web-lows` (D71).
**Red (local, pure):** 14 failed for the intended reasons (N1 label `key_weighted`; `key_weight` returns 2 values; 3
warnings; R1 DID NOT RAISE; pools float64; L3 DID NOT RAISE; D1 DID NOT RAISE; 19a L1 stale quote kept; L6 NaN; dead
term present; no `private_reaches`; no `write_report`; `_summary` unguarded). 7 database tests run in CI.
