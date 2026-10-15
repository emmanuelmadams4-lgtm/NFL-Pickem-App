# CODEX WORK ORDER 2 — step 19a: CI D3 defect + refused quote (F1b, F3)

Try 1 of 2. Worktree `.claude/worktrees/lane-web`, branch `lane/web-19a` at `b378059`.
FAILING: `test_f1b_*`, `test_f3_*` (locally); `test_d3_*` in CI on aa5a7a1 (an unchanged quote wrote a new row:
raw quote prob on the first run vs the 4-place prob of the kept previous line → different market_logit digits).
ALLOWED FILES: `backend/nflpi/predictions/fresh_line.py`, `backend/nflpi/predictions/engine.py` (load_frame only).
REQUIRED:
- `choose_line` uses each eligible quote's probability rounded to 4 places (`round(p, 4)`) for everything (sanity, churn,
  the returned Line). Its second return value is now the refused `Quote` (or None) instead of the string "sanity".
- `load_frame`: log the refused quote returned by `choose_line` (game id, nflverse prob, quote prob, source) and delete
  the block that re-derives it. Nothing else.
PROOF: pure tests (`-k "test_f1 or ... test_f8" --noconftest`, 19 pass) and ruff. The coordinator pushes for the DB
clauses in CI.
CONSTRAINTS: /ponytail; no test edits; do not commit or push; report to jim-mv5mje0k.
