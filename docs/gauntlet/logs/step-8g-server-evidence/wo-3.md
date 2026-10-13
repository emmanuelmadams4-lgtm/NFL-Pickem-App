# WO-3: Dwight's code-review fixes C1, C2, C3, L7, L8 (lane newswire, step 8g)

Make the four new tests at the end of `backend/tests/test_news_worker.py` (`test_c1_*`, `test_c2_*`, `test_c3_*`, `test_l7_l8_*`) pass, and keep all 21 older ones green. Edit ONLY `backend/nflpi/news_worker.py`. No test edits, no other file, no commit.
* C1: in `run_forever`'s loop, skip the sweep while `_inflight` is alive (a live run's `running` row is not "interrupted"). The sweep before the first run still happens.
* C2: when a wake is skipped because a run is alive, the message stays `"news run still running; wake skipped"` but now says its age in seconds: e.g. `"news run still running for 412 s; wake skipped"` (age = time since that thread was started; keep a module-level monotonic start time next to `_inflight`). Log at WARNING for the first two skipped wakes in a row and at ERROR from the third on (a module-level counter, reset when a run is started). The `False` return stays.
* C3: in `step()` put the `try/except Exception` OUTSIDE the `with session_factory()() as session:` so a failure to open or close the session is caught and logged `log.warning("news step failed: %s", type(exc).__name__)` (class name only, never the message). Nothing may escape the thread.
* L7: the "no teams loaded" skip logs at WARNING (it already says "teams").
* L8: `sweep_stale_runs` logs `log.warning("news runs marked interrupted: %d", swept)` when `swept > 0`.
Smallest diff, ruff line length 120. Run only `cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15441/nflpi_test uv run pytest tests/test_news_worker.py -q --color=no 2>&1 | grep -E "FAILED|passed|failed"` and `uvx ruff check nflpi/news_worker.py` if your sandbox allows (otherwise say so and stop).
