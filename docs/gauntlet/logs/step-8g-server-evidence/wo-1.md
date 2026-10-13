# WO-1: backend/nflpi/news_worker.py + 2 lines in backend/nflpi/jobs.py (lane newswire, step 8g)

Make `backend/tests/test_news_worker.py` pass. Read it first (it is the spec), and `docs/gauntlet/logs/step-8g-server.md` section 2a.
Follow `backend/nflpi/live_worker.py` (same pattern: daemon thread, sweep, log exception CLASS NAME only). Smallest diff, no new dependency.
You may edit ONLY: new file `backend/nflpi/news_worker.py`, and `backend/nflpi/jobs.py` (change `from nflpi import live_worker` to also import `news_worker`; add `news_worker.start()` right after `live_worker.start()`; nothing else). Do not edit any test. Do not run pytest (no database in your sandbox).

Interface (the tests use exactly these names):
```
WAKE_SECONDS = 600            # read from the module at call time (tests patch it)
RUN_DEADLINE = 180            # seconds; read at call time
STALE_RUNNING = timedelta(minutes=10)
_inflight: threading.Thread | None = None     # the one run in flight, module level

def news_step(session, now, *, resolver=None, transport=None, sources=SOURCES) -> list[IngestionRun]:
    # 1. if the teams table is empty: log.info("news skipped: no teams loaded yet") and return []   (no request, no ingestion_runs row)
    # 2. made = run.run_news(session, now=now, resolver=resolver, transport=transport, sources=sources)
    #    (import as `from nflpi.ingestion.news import run, store`; run_news already holds the 30 min / 24 h rules: do NOT add or change any)
    # 3. store.prune(session, now) on EVERY step (also when nothing was due, also when everything is blocked)
    # 4. return made
def run_with_deadline(fn, seconds) -> bool:
    # if _inflight is alive: log.warning("news run still running; wake skipped") and return False (fn NOT called)
    # else start a daemon thread running fn (name "news-run"), remember it in _inflight, join(seconds)
    # return True if it finished within seconds, else log.warning("news run past its deadline") and return False
def sweep_stale_runs(session, now) -> int:
    # UPDATE ingestion_runs SET status='failed', error='interrupted', finished_at=now WHERE status='running'
    # AND started_at < now - STALE_RUNNING AND dataset LIKE 'news:%'   (same style as live_worker.sweep_stale_runs; commit; return rowcount)
def run_forever(stop, *, now=None, wait=None, resolver=None, transport=None, sources=SOURCES) -> None:
    # now defaults to lambda: datetime.now(UTC); wait defaults to stop.wait
    # log.info("news worker started")
    # loop while not stop.is_set():
    #     sweep (own short session, errors logged by class name only, never stops the loop)
    #     run_with_deadline(step, RUN_DEADLINE) where step() opens `with session_factory()() as session:` INSIDE the thread and calls news_step(session, now(), resolver=..., transport=..., sources=...)
    #         step() catches Exception, session.rollback() when it can, and logs log.warning("news step failed: %s", type(exc).__name__)  (class name ONLY: never the message, a URL or a header)
    #     if wait(WAKE_SECONDS): break
    # The sweep runs once before the loop and again each wake (tests count the calls: at least one per wake plus one at start).
def start() -> threading.Thread:
    # daemon thread, name "news-worker", target run_forever with a fresh threading.Event(); start it; return it
```
`news_step` must be looked up as a module global at call time (tests monkeypatch `news_worker.news_step`, `sweep_stale_runs`, `RUN_DEADLINE`, `WAKE_SECONDS`).
Ruff line length 120. Typed signatures. Comments only where a reader would be surprised.
