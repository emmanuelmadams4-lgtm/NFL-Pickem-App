PASS

Scope: git diff aae0b32 HEAD (keys.py, test_sim.py k11, test_wiring.py, docs).

Commands
- `uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q -p no:cacheprovider --noconftest`: 90 passed, 18.85s (needed sandbox off for the uv cache).
- `uvx ruff check nflpi tests`: all checks passed.

Findings
- LOW, backend/nflpi/sim/keys.py:59-61: fix is correct and minimal. Whole-number inputs are unchanged: rint then int64 gives the old margins, and bincount sees the same values. Non-finite scores now raise a clear ValueError. Non-whole floats would round silently, but the upstream table (engine.py:98-99, float64 and NaN-filtered in sim_backtest.py:80) never produces them.
- LOW, backend/nflpi/sim/params.py:88-94: with float64 scores (jobs.py:60 via sim_backtest.py:91-92 `.to_numpy()`), `sa` and `sb` stay float, so `reg_a`, `pool_a` and `pool_b` (and the stored SimParams.residual_a/b) become float64 where int-fed data gives int64. Values are whole numbers, so nothing breaks. distributions.py:16 adds int64 to float and distributions.py:57 casts back to int64. `_overtime_rates` already casts to int64, and the lexsort/mean/corrcoef paths are float-safe. Not a bug, but params differ in dtype from the int path. k11 asserts only `key_ratio`, not the residual pools or other fields. Suggest one `np.rint(...).astype(np.int64)` of sa/sb at learn_params entry plus an assert on the pools. Optional.
- LOW, backend/tests/test_wiring.py:67: the 'key_weighted' expectation matches DEFAULT_DISTRIBUTION (distributions.py:8). Correct.
- No pandas nullable (Int64/pd.NA) path was found: the table is float64 and NaN-filtered, and overtime is a plain int list (sim_backtest.py:58).

No CRITICAL or HIGH issues.
