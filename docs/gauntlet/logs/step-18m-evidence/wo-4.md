# CODEX WORK ORDER 4 — step 18m CLEANUP: one paired-residual draw

Try 1 of 2. Baseline: `lane/web` at the commit named in the hive message. Behaviour must not change.

FINDING (coordinator `/refactor` read): `keys.learn_key_ratio` re-implements the paired_residual draw (pool index,
stochastic rounding per side, clip at 0) that `distributions.sample_regulation("paired_residual", ...)` already does;
it accepts array expected points (numpy broadcasts) and draws in the same order (index, then side A, then side B).
ALLOWED FILE: `backend/nflpi/sim/keys.py` only.
REQUIRED: replace the inline draw with `reg_a, reg_b = sample_regulation("paired_residual", a_mu, b_mu, n_draws, rng,
params)` (import inside the function, like `resolve_overtime`, to avoid the params <-> keys import cycle). Type `params`
as `SimParams` under `TYPE_CHECKING` if that is free; otherwise leave it. Nothing else.
PROOF: the learned ratios must be IDENTICAL: the coordinator compares `learn_for_season(...).key_ratio` for 2012 and 2022,
both sources, before and after (reference saved). Also `uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q
--noconftest`, ruff.
CONSTRAINTS: /ponytail; no test edits; do not commit; report to jim-mv5mje0k.
