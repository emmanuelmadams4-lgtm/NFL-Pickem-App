# CODEX WORK ORDER 2 — step 18m: the key-number bench (KB1-KB4)

Try 1 of 2. Baseline: `lane/web` at `f439e5b` (WO1 committed). Spec: `docs/gauntlet/logs/step-18m.md` §2 KB1-KB5.
Tests: the `test_kb*` block at the end of `backend/tests/test_sim_backtest.py`. Reference for the metrics:
`step-18m-evidence/spike.py` (not production).

ALLOWED FILE: `backend/nflpi/analytics/sim_backtest.py` only. KB5 stays red (it needs the tune run; not yours).

REQUIRED:
- `KEY_ALPHAS = (1.0, 0.9, 0.8, 0.75, 0.5)`, `N_BOOT = 2000`, `ALPHA_RULE` (one sentence: the largest alpha whose cover-Brier,
  over-Brier and CRPS paired-bootstrap 95% intervals, alpha minus paired_residual per game, all have a LOWER end at or
  below zero (not significantly worse) for both sources; 0.0 if none). Corrected after Ryan f6dd59.
- `pick_alpha(by_alpha: dict[str, dict[source, dict]]) -> float` per that rule (reads the `[mean, lo, hi]` lists' `lo`).
- One shared per-game pass used by both commands: for each season, source: `params = learn_for_season(...)`; per game,
  seed `zlib.crc32(game_id) ^ base_seed` as `_game_row`; draws = `simulate_game(..., distribution="paired_residual",
  spread=quoted_home_spread(...), total=total_line)`; for each alpha `keys.key_weight(a, b,
  np.random.default_rng([seed, round(alpha * 100)]), params.key_ratio, alpha)`. Per game and variant: CRPS(margin) +
  CRPS(total) (`crps`), cover prob with pushes removed (p_cover / (1 - p_push)), over prob likewise, rate of |margin| 3 and
  7, margin sd, randomized PIT of the real margin (below + U * at, U from a per-game rng), and 18c-style inclusive
  interval hits at 50/80/95 (`_intervals`-style quantiles). Real outcomes per game (cover / over as 0/1, pushes NaN).
- A block per variant and source: `key3`, `key7`, `crps`, `cover_brier`, `over_brier` (pushes out), `margin_sd`,
  `pit_coverage` {"0.5","0.8","0.95"} (share of |PIT - 0.5| <= level/2), `coverage` {"0.5","0.8","0.95"} (inclusive hits).
  Per alpha also `cover_brier_ci`, `over_brier_ci`, `crps_ci`: `[mean, lo, hi]` of the per-game difference (alpha minus
  baseline; Brier rows with a push dropped), paired bootstrap over games, `n_boot` resamples, rng seeded from base_seed.
- `keys_tune(table, *, seasons=TUNE_SEASONS, alphas=KEY_ALPHAS, n_simulations=N_SIMULATIONS, base_seed=BASE_SEED,
  n_boot=N_BOOT) -> dict`: raise ValueError mentioning "confirm" for any season >= 2022; drop rows >= 2022 before
  anything else. Returns `{"seasons", "n_simulations", "n_boot", "games", "real": {source: {"3","7"}}, "baseline":
  {source: block}, "by_alpha": {str(alpha): {source: block+cis}}, "alpha": pick_alpha(...), "rule": ALPHA_RULE}`.
- `keys_confirm(table, *, keys_path, out_path, seasons=CONFIRM_SEASONS, n_simulations, base_seed, n_boot) -> dict`:
  alpha from `keys_path` (FileNotFoundError when missing, before anything else); open `out_path` with "x" before the run
  (as `confirm` does; delete only if the run raises); report `{"seasons", "alpha", "games", "n_simulations", "n_boot",
  "by_source": {source: {"real", "baseline": block, "key_weighted": block, "cover_brier_ci", "over_brier_ci",
  "crps_ci"}}}`; `json.dump(..., allow_nan=False)`.
- CLI in `main`: `keys-tune` writes `<out_dir>/keys-tune.json` and prints per source the real, baseline and per-alpha
  key3/key7/cover/over/crps and the chosen alpha; `keys-confirm` writes `<out_dir>/keys-confirm.json` and prints the
  before/after lines. Usage string updated.

PROOF: `cd backend && uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q --noconftest` (all pass except KB5),
`uvx ruff check nflpi tests`.
CONSTRAINTS: /ponytail: reuse `crps`, `quoted_home_spread`, `learn_for_season`, `_intervals`-style quantiles; no new
dependency; no test edits; keep the 18c commands unchanged. Do not commit. Report to jim-mv5mje0k when done.
