# Step 13b: backend cleanup S7, S14, S12 backend half

Lane `cleanup13`, branch `lane/cleanup13`, base `d1b8a07`, tier T1, One-Shot. Temp worker-cleanup13 (Andy). Scope from god's dispatch; rows S7/S12/S14 of `STRUCTURE_REVIEW.md`, gates from `PLAN.md` row 13. B8 timing, the S12 web caveat and the week-6 report are out of scope.

## 1. PLANNING
* Gates: same suite green; no cross-package private imports (grep gate); week endpoint prediction queries <= 3 (query-count test); backtest numbers unchanged.
* Baseline (throwaway Postgres on 127.0.0.1:54713, removed after): 2345 passed, 1 skipped. Backtest fingerprint on the test fixture (`run_backtest`, seasons 2021-2023, window 3, labels removed): sha256 `4b636deac397...d568`, 8151 bytes.
* Found in the code: `performance()` already groups predictions once (defaultdict), so the quadratic part of S14 is gone; what remains is `_latest_by_game` loading full history and the week board reading predictions 3 times (`compute_week`, `summaries`, `performance`). The 4th "predictions" hit in a naive count is the `EXISTS` inside `sheet.finalize`, a games query.
* Not done (carried): moving `train()` from `predictions/engine.py` to analytics. It needs `load_frame` and the engine's hash helper, so it is not a pure move. The `ai` to `api.readmodels` import stays (it is a read-model import now, not `views`). Dropping the duplicate `recommendations` call needs a `sheet.compute_week` signature change (seam file, grant was `is_locked` only).

## 2. SPECIFICATION (frozen)
| ID | Clause | Test |
|---|---|---|
| C1 | No module imports a `_private` name from another package (`from x import _y`) | `test_layering.py::test_no_cross_package_private_imports` |
| C2 | No module uses `imported_module._private` across packages | `test_no_cross_package_private_attribute_use` |
| C3 | `predictions`, `analytics`, `notify` do not import `nflpi.api.views` or `readmodels` | `test_lower_layers_do_not_import_api_views` |
| C4 | `ChangeEvent` lives in `predictions/events.py` with only a `dataclasses` import | `test_notify_does_not_pull_in_pandas_for_a_dataclass` |
| C5 | Week endpoint runs 1..3 `SELECT predictions.*` statements | `test_week_queries.py` |
| C6 | Backtest numbers byte-identical (labels excluded) | fingerprint above, before and after |
* Red: the four layering tests failed on the base (engine imported `_elo_frames`, `push._send` etc., no `events` module, `sheet` imported `api.views`).

## 3. IMPLEMENTATION
* `elo_frames` public (was `_elo_frames`), callers in analytics, engine, tests renamed.
* `ChangeEvent` to `predictions/events.py`; `notify/push.py` and `engine.py` import it from there (engine still exposes the name).
* `is_locked` defined in `predictions/sheet.py`; `sheet` no longer imports `api.views`; the read models import it.
* `api/views.py` renamed to `api/readmodels.py` (git mv, pure move); `views.py` is a star re-export shim; `ai/research.py` and `api/main.py` import `readmodels`.
* `push.send`, `push.record`, `stars.star_report` public (granted by god), call sites in `star_alerts.py`, `passkey.py`, two test monkeypatch names.
* S14: `_latest_by_game` uses `DISTINCT ON (game_id) ORDER BY game_id, id DESC` (last row per game, same result).
* S12: backtest label "Stats model (Elo + QB + home)" (rest was dropped from the features).

## 4. CLEANUP
* ruff clean (`uvx ruff check nflpi tests`).

## 5. VERIFICATION
* Suite: 2350 passed, 1 skipped (2345 + 5 new). Backtest fingerprint identical. Week endpoint: 3 `SELECT predictions` statements.
* lane-guard vs origin/main: only `tests/test_api.py` and `tests/test_star_alerts.py` outside the lane (rename strings, import path); grant requested from god.
* Security review: Dwight (see below). Fresh critic: see below.

## 6. LANDING
Hand-off to god; no push.
