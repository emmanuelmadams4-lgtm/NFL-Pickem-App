PASS

Scope: git diff 325f541..fd24b98 (backend), step log, evidence JSON, SIMULATOR.md.

Findings
- MEDIUM backend/nflpi/analytics/sim_backtest.py:304 (pick_alpha) and step-18m.md section 3: the frozen rule ("lower end at or below zero") is weak. It picked alpha 1.0 even though the football cover-Brier delta is +0.0007 (-0.0002..+0.0015) in tune, and the spike on other seeds put it just above zero. The rule is followed exactly, and the log says "not significantly worse", not "better", so the claim is honest. In confirm the delta is 0.0000 on both sources, so this is only a residual risk.
- LOW backend/nflpi/sim/keys.py:25-37: the tilt Newton loop runs at most 50 times and does not report non-convergence. Mean and total preservation then holds only if it converged. The +1e-9 ridge keeps solve() finite. The tests check preservation on 200k draws within 0.15 (K2, K3), so a silent failure would likely show, but there is no assertion in production code.
- LOW backend/nflpi/sim/keys.py:44-59: the ratio is learned in-sample (mu and the residual pool come from the same training rows). That is walk-forward valid, and the confirm run shows it holds up.
- LOW SIMULATOR.md and the log both say 2022-2025 is a check, not a fresh holdout. Good. Nothing to fix.

Checks, all OK
- K1-K8 and KB1-KB5 are each implemented and tested. The tests are not tautological. K1 compares arrays exactly. K2, K3 and K6 measure the effect. K5 permutes rows. K7 does a JSON round trip using the engine's _SIM_ARRAYS rule. KB2 scrambles seasons 2022 and later and requires identical output. KB4 checks the once-only run with FileExistsError.
- Leakage: learn_for_season uses seasons [season-10, season-1] only, and learn_key_ratio sees only the rows learn_params is given. keys_tune raises ValueError for seasons 2022 and later and filters the table to before 2022. The alpha rule text matches the log (ALPHA_RULE). All commits are dated 2026-10-15.
- Playoff ties: key_weight resamples post-overtime draws, so no ties appear. K6 passes.
- Backward compatibility: key_ratio and key_alpha have defaults (() and 0.0). load_sim_params(**row) accepts old rows and they behave as paired_residual. New rows store key_ratio as a JSON list of floats. After a load it is a list rather than a tuple, which np.asarray and len() handle. engine.py is unchanged.
- Performance: the K8 test with 40,300 rows takes 0.09s, against a 3s limit.
- Every number in log section 3 and SIMULATOR.md Key numbers matches keys-tune.json and keys-confirm.json. That covers 3/7 rates, Brier, CRPS, sd, PIT and inclusive coverage, the CIs, the game counts (2,576 and 1,087) and the real rates (14.1/8.9 and 14.8/8.0). I did not re-verify the sha256 and sha1 values or the "matches_stored_confirm" claim.
- The log has PLANNING, SPECIFICATION (red commit 5446a41 precedes feat f439e5b), IMPLEMENTATION and CLEANUP.

Commands
- uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q -p no:cacheprovider --noconftest (sandbox off for the uv cache): 87 passed in 15.6s.
- uvx ruff check nflpi tests: All checks passed.
- The K8 test alone: 0.09s.
- A python script compared all JSON values to the log. No mismatch.
- I did not run keys-tune or keys-confirm, Docker, or any DB tests.
