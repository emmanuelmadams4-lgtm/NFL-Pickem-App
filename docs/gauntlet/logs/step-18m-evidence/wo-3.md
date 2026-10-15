# CODEX WORK ORDER 3 — step 18m: set the tuned strength and the default (KB5)

Try 1 of 2. Baseline: `lane/web` at `081a4a3` (keys-tune record committed: alpha 1.0).
FAILING: `backend/tests/test_sim_backtest.py::test_kb5_key_alpha_and_default_follow_the_recorded_keys_tune_run`.
ALLOWED FILES: `backend/nflpi/sim/keys.py` (KEY_ALPHA line and its comment), `backend/nflpi/sim/distributions.py`
(DEFAULT_DISTRIBUTION line and its comment).
REQUIRED: `KEY_ALPHA = 1.0  # chosen on 2012-2021 only by the keys-tune rule: step-18m-evidence/keys-tune.json`;
`DEFAULT_DISTRIBUTION = "key_weighted"  # paired_residual (18c tune-result.json) reweighted toward real key margins
(step 18m keys-tune.json)`. Nothing else.
PROOF: `uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q --noconftest` all pass; ruff.
CONSTRAINTS: no test edits; do not commit; report to jim-mv5mje0k.
