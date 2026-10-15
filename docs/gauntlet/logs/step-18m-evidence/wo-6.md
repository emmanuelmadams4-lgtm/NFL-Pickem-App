# CODEX WORK ORDER 6 — step 18m: float scores in learn_key_ratio (PR #46 CI)

Try 1 of 2. Worktree **`.claude/worktrees/lane-web-18m`** (branch lane/web) at `46be5fe`. FAILING: `test_k11_*` in
backend/tests/test_sim.py (TypeError: cannot cast float64 to int64 in np.bincount, keys.py:67).
ALLOWED FILE: `backend/nflpi/sim/keys.py` only.
REQUIRED: in `learn_key_ratio`, turn the real final margins into int64 once: reject non-finite scores with a
ValueError naming the problem, then `np.rint` and cast. Same ratio as today for whole-number inputs. Nothing else.
PROOF: `cd backend && uv run pytest tests/test_sim.py tests/test_sim_backtest.py -q --noconftest` (all pass), ruff.
CONSTRAINTS: /ponytail; no test edits; do not commit or push; report to jim-mv5mje0k.
