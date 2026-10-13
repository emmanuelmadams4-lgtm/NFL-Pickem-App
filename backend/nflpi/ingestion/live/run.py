"""Refresh ESPN live states with a logged, source-specific backoff."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from nflpi.ingestion.live import espn, fetch, store
from nflpi.models import Game, IngestionRun, LiveState

log = logging.getLogger(__name__)
EASTERN = ZoneInfo("America/New_York")
ESPN_MIN_INTERVAL = timedelta(seconds=30)
KALSHI_MIN_INTERVAL = timedelta(seconds=60)
ODDS_MIN_INTERVAL = timedelta(hours=6)
MAX_SUMMARIES = 16


@dataclass(frozen=True)
class RefreshResult:
    source: str
    status: str
    inserted: int = 0
    skipped: int = 0
    detail: str = ""


def safe_error(exc: Exception) -> str:
    if isinstance(exc, fetch.FetchError) or isinstance(exc, ValueError) and str(exc) in ("shape", "event id"):
        return f"{type(exc).__name__}: {exc}"[:200]
    return type(exc).__name__[:200]


def run_source(
    session: Session,
    *,
    status_key: str,
    run_source: str,
    dataset: str,
    now: datetime,
    min_interval: timedelta,
    job: Callable[[], tuple[int, int, fetch.FetchError | None]],
    floor: timedelta = timedelta(0),
) -> RefreshResult:
    until = store.source_blocked_until(session, status_key)
    if until is not None and until > now:
        return RefreshResult(status_key, "skipped", detail=f"backing off until {until.isoformat()}")
    run = IngestionRun(source=run_source, dataset=dataset, status="running", started_at=now)
    session.add(run)
    session.commit()
    run_id = run.id
    try:
        inserted, skipped, blocking_error = job()
    except Exception as exc:
        session.rollback()
        run = session.get(IngestionRun, run_id)
        error = safe_error(exc)
        run.status, run.error, run.finished_at = "failed", error, now
        store.mark_failed(session, status_key, now, error, floor)
        session.commit()
        log.warning("%s refresh failed: %s", status_key, error)
        return RefreshResult(status_key, "failed", detail=error)
    run.rows, run.finished_at = inserted, now
    if blocking_error is not None:
        error = safe_error(blocking_error)
        run.status, run.error = "failed", error
        store.mark_failed(session, status_key, now, error, floor)
        log.warning("%s refresh failed: %s", status_key, error)
        result = RefreshResult(status_key, "failed", inserted, skipped, error)
    else:
        run.status = "ok"
        store.mark_ok(session, status_key, now, min_interval)
        result = RefreshResult(status_key, "ok", inserted, skipped)
    session.commit()
    return result


def _candidate_games(session: Session, events: list[espn.Event]) -> list[Game]:
    if not events:
        return []
    windows = [
        and_(Game.kickoff_utc >= event.start - timedelta(days=2), Game.kickoff_utc <= event.start + timedelta(days=2))
        for event in events
    ]
    return list(session.scalars(select(Game).where(or_(*windows))))


def _matching_game(event: espn.Event, games: list[Game]) -> Game | None:
    matches = [
        game
        for game in games
        if (
            {event.home_code, event.away_code} == {game.home_team, game.away_team}
            and event.start.astimezone(EASTERN).date() == game.kickoff_utc.astimezone(EASTERN).date()
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _needs_summary(event: espn.Event, previous: LiveState | None) -> bool:
    return (
        event.state == "in"
        or event.state == "post"
        and not (previous is not None and previous.state == "post" and previous.home_wp is not None)
    )


def _summary(event: espn.Event, get: Callable[[str], fetch.JsonResult]) -> espn.WinProb | None:
    try:
        return espn.parse_win_probability(get(espn.summary_url(event.event_id)).data)
    except fetch.Blocked:
        raise
    except fetch.FetchError:
        return None


def _save_event(
    session: Session,
    event: espn.Event,
    game: Game,
    probability: espn.WinProb | None,
    previous: LiveState | None,
    now: datetime,
) -> bool:
    same_orientation = event.home_code == game.home_team
    home_score = event.home_score if same_orientation else event.away_score
    away_score = event.away_score if same_orientation else event.home_score
    home_wp = probability.home if probability is not None else None
    tie_wp = probability.tie if probability is not None else None
    if not same_orientation:
        home_wp = 1 - home_wp - tie_wp if home_wp is not None and tie_wp is not None else None
    play_id = probability.play_id if probability is not None else None
    if event.state == "post" and previous is not None and not _needs_summary(event, previous):
        home_wp, tie_wp, play_id = previous.home_wp, previous.tie_wp, previous.last_play_id
    return store.add_live_state(
        session,
        game_id=game.game_id,
        event_id=event.event_id,
        fetched_at=now,
        state=event.state,
        home_score=home_score,
        away_score=away_score,
        period=event.period,
        clock=event.clock,
        home_wp=home_wp,
        tie_wp=tie_wp,
        last_play_id=play_id,
    )


def _espn_job(
    session: Session,
    get: Callable[[str], fetch.JsonResult],
    now: datetime,
) -> tuple[int, int, fetch.FetchError | None]:
    events, skipped = espn.parse_scoreboard(get(espn.SCOREBOARD_URL).data)
    games = _candidate_games(session, events)
    newest = store.live_states_for(session, [game.game_id for game in games])
    inserted, summaries = 0, 0
    blocking_error: fetch.FetchError | None = None
    for event in events:
        game = _matching_game(event, games)
        if game is None:
            skipped += 1
            log.debug("unmatched ESPN event %r", event.event_id[:64])
            continue
        probability = None
        if _needs_summary(event, newest.get(game.game_id)) and blocking_error is None and summaries < MAX_SUMMARIES:
            summaries += 1
            try:
                probability = _summary(event, get)
            except fetch.Blocked as exc:
                blocking_error = exc
        if _save_event(session, event, game, probability, newest.get(game.game_id), now):
            inserted += 1
            session.flush()
            newest[game.game_id] = session.scalar(
                select(LiveState).where(LiveState.game_id == game.game_id).order_by(LiveState.id.desc()).limit(1)
            )
    return inserted, skipped, blocking_error


def refresh_live_games(
    session: Session,
    *,
    get: Callable[[str], fetch.JsonResult] = fetch.fetch_json,
    now: datetime | None = None,
) -> RefreshResult:
    now = datetime.now(UTC) if now is None else now.astimezone(UTC)
    return run_source(
        session,
        status_key="espn_live",
        run_source="espn",
        dataset="live_scores",
        now=now,
        min_interval=ESPN_MIN_INTERVAL,
        job=lambda: _espn_job(session, get, now),
    )
