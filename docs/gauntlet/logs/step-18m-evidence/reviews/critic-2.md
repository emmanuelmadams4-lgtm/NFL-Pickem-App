PASS

Scope: git diff fd24b98 f86e87f (game.py, keys.py, test_sim.py, logs). HEAD f86e87f.

Commands
- uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q -p no:cacheprovider --noconftest: 89 passed in 16.22s (sandbox off for the uv cache).
- uvx ruff check nflpi tests: All checks passed.

Checks
- K9 met. game.py:82-83 labels "paired_residual" when key_ratio is empty/None or key_alpha == 0. This matches the key_weight early return (keys.py:18, alpha == 0 or len(ratio) == 0), so draws are unchanged. The label is passed through at game.py:104. test_k9 covers both no-op cases and asserts "key_weighted" for ratio plus alpha 1.0, so it is not tautological.
- K10 met. keys.py:25-43 runs TILT_STEPS=50 Newton steps. A for/else warns "did not converge" and returns a, b unchanged, so drifted weights are never used for resampling.
- Converged path unchanged. The break skips the else block, and the weights, rng.choice call and rng consumption are identical to before. The tune/confirm numbers stay valid. Cases that previously resampled after 50 non-converged steps now return unweighted draws. That is the intended change.

Findings
- LOW, backend/tests/test_sim.py (test_k10): it forces the branch with TILT_STEPS=0 rather than with a case that really fails to converge. It covers the warn-and-return path, not the numerical trigger. The warning then prints "mean error [nan nan]" because delta is the initial NaN. This does not block the PASS.

No CRITICAL, HIGH or MEDIUM findings.
