"""Background thread that polls the news feeds slowly and prunes old rows."""

import logging
import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from nflpi.db import session_factory
from nflpi.ingestion.news import run, store
from nflpi.ingestion.news.sources import SOURCES, Source
from nflpi.models import IngestionRun, Team

log = logging.getLogger(__name__)
WAKE_SECONDS = 600
RUN_DEADLINE = 180
STALE_RUNNING = timedelta(minutes=10)
STUCK_ERROR_AFTER = 3
_inflight: threading.Thread | None = None
_inflight_started = 0.0
_skipped_wakes = 0


def news_step(
    session: Session,
    now: datetime,
    *,
    resolver: Callable[[str], list[str]] | None = None,
    transport: httpx.BaseTransport | None = None,
    sources: Sequence[Source] = SOURCES,
) -> list[IngestionRun]:
    if not session.scalar(select(func.count()).select_from(Team)):
        log.warning("news skipped: no teams loaded yet")
        return []
    made = run.run_news(session, now=now, resolver=resolver, transport=transport, sources=sources)
    store.prune(session, now)
    return made


def run_with_deadline(fn: Callable[[], object], seconds: float) -> bool:
    global _inflight, _inflight_started, _skipped_wakes
    if _inflight is not None and _inflight.is_alive():
        _skipped_wakes += 1
        level = logging.ERROR if _skipped_wakes >= STUCK_ERROR_AFTER else logging.WARNING
        age = int(time.monotonic() - _inflight_started)
        log.log(level, "news run still running for %d s; wake skipped", age)
        return False
    _skipped_wakes = 0
    thread = threading.Thread(target=fn, daemon=True, name="news-run")
    _inflight = thread
    _inflight_started = time.monotonic()
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        log.warning("news run past its deadline")
        return False
    return True


def sweep_stale_runs(session: Session, now: datetime) -> int:
    swept = session.execute(
        update(IngestionRun)
        .where(
            IngestionRun.status == "running",
            IngestionRun.started_at < now - STALE_RUNNING,
            IngestionRun.dataset.like("news:%"),
        )
        .values(status="failed", error="interrupted", finished_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    session.commit()
    if swept > 0:
        log.warning("news runs marked interrupted: %d", swept)
    return swept


def run_forever(
    stop: threading.Event,
    *,
    now: Callable[[], datetime] | None = None,
    wait: Callable[[float], bool] | None = None,
    resolver: Callable[[str], list[str]] | None = None,
    transport: httpx.BaseTransport | None = None,
    sources: Sequence[Source] = SOURCES,
) -> None:
    now = now or (lambda: datetime.now(UTC))
    wait = wait or stop.wait
    log.info("news worker started")

    def sweep() -> None:
        try:
            with session_factory()() as session:
                sweep_stale_runs(session, now())
        except Exception as exc:  # noqa: BLE001 - a failed sweep must not stop the worker
            log.warning("news sweep failed: %s", type(exc).__name__)

    def step() -> None:
        try:
            with session_factory()() as session:
                news_step(session, now(), resolver=resolver, transport=transport, sources=sources)
        except Exception as exc:  # noqa: BLE001 - keep the news worker alive; closing the session rolls back
            log.warning("news step failed: %s", type(exc).__name__)

    sweep()
    while not stop.is_set():
        run_with_deadline(step, RUN_DEADLINE)
        if wait(WAKE_SECONDS):
            break
        if _inflight is None or not _inflight.is_alive():
            sweep()


def start() -> threading.Thread:
    thread = threading.Thread(target=run_forever, args=(threading.Event(),), daemon=True, name="news-worker")
    thread.start()
    return thread
