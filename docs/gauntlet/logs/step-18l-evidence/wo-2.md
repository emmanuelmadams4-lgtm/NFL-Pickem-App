# CODEX WORK ORDER 2 — step 18l: rounded or broken stored chances never fail the game reply

Try 1 of 2 (re-issued: baseline `c8af484`, A8 now uses realistic sums 0.9999/1.0001; the 0.001 band stands). Baseline: `lane/web` at the commit named in the hive message (WO1 3f6cde9 + red A8).

FAILING: `backend/tests/test_value_api.py::test_a8_*` (4 cases). The engine stores simulator chances rounded to 4
places (`engine.py` `_clean`), so cover + push + miss can be 0.9999; `SettlementProbs` needs 1 within 1e-9 and raises
`BettingError`, which 500s `GET /api/games/{id}`.

ALLOWED FILE: `backend/nflpi/api/readmodels.py`, only inside `_value_ratings`.

REQUIRED: before building `SettlementProbs` for spread/total, let `total = sum(parts)`; if `abs(total - 1) > 0.001`
skip the price; else scale each part by `1 / total`. Then build `SettlementProbs` and call `rate_price` inside
`try/except (BettingError, ValueError, TypeError)` (BettingError from `nflpi.betting.odds`) around the WHOLE per-rating
call (SettlementProbs and rate_price) and skip the price on error, with `log.warning("value rating skipped for %s %s %s",
game_id, market, selection, exc_info=True)` on the module logger (add `log = logging.getLogger(__name__)` only if none). (Dwight V1.)
Name the 0.001 as a module constant with a one-line comment (rounding of stored chances). Nothing else changes.

PROOF: `cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test APP_ACCESS_TOKEN=test-token uv run pytest tests/test_value_api.py -q`; ruff.
CONSTRAINTS: /ponytail; no test edits; do not commit; report when done.
