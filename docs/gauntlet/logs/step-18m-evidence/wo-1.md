# CODEX WORK ORDER 1 — step 18m: the key_weighted sampler (K1-K8)

Try 1 of 2. Baseline: `lane/web` at `5446a41` (red committed). Spec: `docs/gauntlet/logs/step-18m.md` §2 K1-K8. Tests:
`backend/tests/test_sim.py` (the `test_k*` block at the end). Design reference (not production): `step-18m-evidence/spike.py`.

ALLOWED FILES: `backend/nflpi/sim/keys.py` (new), `sim/params.py`, `sim/game.py`, `sim/distributions.py`, `sim/__init__.py`.
Nothing else (no bench, no engine, no test edits).

REQUIRED:
- `sim/keys.py`: `KEY_MAX = 60`; `KEY_ALPHA = 0.0` (placeholder; set after the keys-tune run, comment says so);
  `KEY_TOTAL_DRAWS = 2_000_000`.
  - `key_weight(a, b, rng, ratio, alpha) -> (a, b)`: if `alpha == 0` or `not ratio`, return `a, b` unchanged (same arrays,
    no rng use). Else weights `w = ratio[min(|a-b|, KEY_MAX)] ** alpha`, then an exponential tilt `w * exp(l1*m + l2*t)`
    (m = a-b, t = a+b) with (l1, l2) found by a few Newton steps so the weighted mean margin and total equal the input
    draws' means (start at 0, stop at 1e-9 or 50 steps; work in log space), then `idx = rng.choice(n, n, p=w)` and return
    `a[idx], b[idx]`.
  - `learn_key_ratio(mu_a, mu_b, reg_a?, ..., params) -> tuple[float, ...]`: your signature, but: simulate each training
    row with the paired_residual pool (regulation draw + overtime, as `simulate_game` does, using `params`) with
    `max(1, KEY_TOTAL_DRAWS // n_rows)` draws per row, vectorised (no Python loop per row); rng
    `np.random.default_rng(<fixed seed from target_season>)`; rows sorted by (mu_a, mu_b, score_a, score_b) first so row
    order never matters; sim histogram of |final margin| capped at KEY_MAX, averaged per row; real histogram of the
    rows' |final margin| (final scores, capped); `ratio = (real + 0.5) / (sim + 0.5)` with both as per-row frequencies
    times n_rows (i.e. counts). Return python floats.
- `SimParams`: add `key_ratio: tuple[float, ...] = ()` and `key_alpha: float = 0.0` at the END (defaults: rows stored
  before 18m still load). `learn_params` fills them (`key_alpha = keys.KEY_ALPHA`), leaving every other field as today.
- `DISTRIBUTIONS` gains `"key_weighted"` at the end; `sample_regulation` treats it as `paired_residual`.
  `simulate_game`: after `resolve_overtime`, `if distribution == "key_weighted": a, b = key_weight(a, b, rng,
  params.key_ratio, params.key_alpha)` (params is required, as for paired_residual).
- Export `keys` from `nflpi.sim` (`from nflpi.sim import keys` must work).
- `DEFAULT_DISTRIBUTION` stays `"paired_residual"` in this order (it changes only after the tune run).

PROOF: `cd backend && uv run pytest tests/test_sim.py -q --noconftest` (all pass, K1-K8 included; the test DB is down,
these tests do not need it) and `uvx ruff check nflpi tests`. test_sim_backtest KB* stay red (next order).
CONSTRAINTS: /ponytail: numpy only, no new dependency, smallest diff, a `ponytail:` comment on any deliberate ceiling.
No test edits. Do not commit. Report to jim-mv5mje0k when done.
