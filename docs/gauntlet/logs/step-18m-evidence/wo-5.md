# CODEX WORK ORDER 5 — step 18m: Dwight M1 and M2 (K9, K10)

Try 1 of 2. Baseline: `lane/web` at `0e7d72c`. FAILING: `test_k9_*`, `test_k10_*` in backend/tests/test_sim.py.
ALLOWED FILES: `backend/nflpi/sim/keys.py`, `backend/nflpi/sim/game.py`.
REQUIRED:
- M1 (game.py): when `distribution == "key_weighted"` and there is nothing to weight (`not params.key_ratio` or
  `params.key_alpha == 0`), the SimResult's `distribution` is `"paired_residual"` (the draws are already identical).
  Smallest form, e.g. compute the label once before building the result.
- M2 (keys.py): `TILT_STEPS = 50` module constant used by the Newton loop; on no convergence (for/else), `log.warning(
  "key weighting did not converge after %d steps (mean error %s); draws left unweighted", TILT_STEPS, delta)` with a
  module logger, and return `a, b` unchanged (no resample).
- Nothing else.
PROOF: `uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q --noconftest` all pass (89); ruff.
CONSTRAINTS: /ponytail; no test edits; do not commit; report to jim-mv5mje0k.
