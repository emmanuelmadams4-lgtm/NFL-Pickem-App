"""Background thread that keeps live scores and market quotes fresh while a game is near or on."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, tuple_, update
from sqlalchemy.orm import Session

from nflpi.db import session_factory
from nflpi.ingestion.live import fetch, run, store
from nflpi.models import Game, IngestionRun, LiveState

log = logging.getLogger(__name__)
WAKE_SECONDS = 5
MAX_GAME = timedelta(hours=5)
ESPN_DEADLINE = 45
QUOTE_DEADLINE = 45
KALSHI_EVERY = timedelta(seconds=120)
KALSHI_LEAD = timedelta(hours=2)
ODDS_EVERY = timedelta(hours=6)
ODDS_LEAD = timedelta(hours=24)
STALE_RUNNING = timedelta(minutes=10)
LIVE_RUN_KEYS = (("espn", "live_scores"), ("kalshi", "market_quotes"), ("oddsapi", "market_quotes"))

Get = Callable[[str], fetch.JsonResult]


@dataclass(frozen=True)
class Schedule:
    next_kalshi: datetime | None = None
    next_odds: datetime | None = None


@dataclass(frozen=True)
class StepResult:
    schedule: Schedule
    results: tuple[run.RefreshResult, ...]


def _candidates(session: Session, now: datetime) -> list[tuple[datetime, LiveState | None]]:
    games = session.execute(
        select(Game.game_id, Game.kickoff_utc).where(
            Game.kickoff_utc > now - MAX_GAME, Game.kickoff_utc <= now + max(KALSHI_LEAD, ODDS_LEAD)
        )
    ).all()
    newest = store.live_states_for(session, [game_id for game_id, _ in games])
    return [(kickoff, newest.get(game_id)) for game_id, kickoff in games]


def _any_in_window(candidates: list[tuple[datetime, LiveState | None]], now: datetime, lead: timedelta) -> bool:
    return any(
        now - MAX_GAME < kickoff <= now + lead and (state is None or state.state != "post")
        for kickoff, state in candidates
    )


def in_window(session: Session, now: datetime, lead: timedelta) -> bool:
    now = now.astimezone(UTC)
    return _any_in_window(_candidates(session, now), now, lead)


def with_deadline(get: Get, seconds: float, clock: Callable[[], float]) -> Get:
    started = clock()

    def bounded(url: str) -> fetch.JsonResult:
        if clock() - started > seconds:
            raise fetch.FetchError("deadline")
        return get(url)

    return bounded


def _attempt(session: Session, name: str, call: Callable[[], run.RefreshResult]) -> run.RefreshResult | None:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - one source failing must not stop the others
        session.rollback()
        log.warning("live %s refresh failed: %s", name, type(exc).__name__)
        return None


def live_step(
    session: Session,
    now: datetime,
    schedule: Schedule,
    *,
    get: Get = fetch.fetch_json,
    clock: Callable[[], float] = time.monotonic,
    odds_key: str | None = None,
) -> StepResult:
    now = now.astimezone(UTC)
    try:
        candidates = _candidates(session, now)
    except Exception as exc:  # noqa: BLE001 - a broken window query skips this wake
        session.rollback()
        log.warning("live window query failed: %s", type(exc).__name__)
        return StepResult(schedule, ())
    results: list[run.RefreshResult | None] = []
    if _any_in_window(candidates, now, timedelta(0)):
        bounded = with_deadline(get, ESPN_DEADLINE, clock)
        results.append(_attempt(session, "espn", lambda: run.refresh_live_games(session, get=bounded, now=now)))
    if (schedule.next_kalshi is None or now >= schedule.next_kalshi) and _any_in_window(candidates, now, KALSHI_LEAD):
        bounded_k = with_deadline(get, QUOTE_DEADLINE, clock)
        results.append(_attempt(session, "kalshi", lambda: run.refresh_kalshi_quotes(session, get=bounded_k, now=now)))
        schedule = replace(schedule, next_kalshi=now + KALSHI_EVERY)
    if (schedule.next_odds is None or now >= schedule.next_odds) and _any_in_window(candidates, now, ODDS_LEAD):
        bounded_o = with_deadline(get, QUOTE_DEADLINE, clock)
        results.append(
            _attempt(
                session,
                "odds",
                lambda: run.refresh_odds_quotes(session, get=bounded_o, now=now, api_key=odds_key),
            )
        )
        schedule = replace(schedule, next_odds=now + ODDS_EVERY)
    return StepResult(schedule, tuple(r for r in results if r is not None))


def sweep_stale_runs(session: Session, now: datetime) -> int:
    swept = session.execute(
        update(IngestionRun)
        .where(
            IngestionRun.status == "running",
            IngestionRun.started_at < now - STALE_RUNNING,
            tuple_(IngestionRun.source, IngestionRun.dataset).in_(LIVE_RUN_KEYS),
        )
        .values(status="failed", error="interrupted", finished_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    session.commit()
    return swept


def run_forever(
    stop: threading.Event, *, get: Get = fetch.fetch_json, wait: Callable[[float], bool] | None = None
) -> None:
    wait = wait or stop.wait
    log.info("live worker started")
    try:
        with session_factory()() as session:
            sweep_stale_runs(session, datetime.now(UTC))
    except Exception as exc:  # noqa: BLE001 - a failed sweep must not stop the worker
        log.warning("live sweep failed: %s", type(exc).__name__)
    schedule = Schedule()
    while not stop.is_set():
        try:
            with session_factory()() as session:
                schedule = live_step(session, datetime.now(UTC), schedule, get=get).schedule
        except Exception as exc:  # noqa: BLE001 - keep the live worker alive
            log.warning("live step failed: %s", type(exc).__name__)
        if wait(WAKE_SECONDS):
            break


def start() -> threading.Thread:
    thread = threading.Thread(target=run_forever, args=(threading.Event(),), daemon=True, name="live-worker")
    thread.start()
    return thread
