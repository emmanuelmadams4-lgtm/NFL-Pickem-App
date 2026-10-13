"""Insert-only live snapshots and per-source backoff state."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nflpi.models import LiveState, MarketQuote, SourceStatus

BACKOFF_FIRST = timedelta(minutes=15)
BACKOFF_MAX = timedelta(hours=24)
UNSET = object()
_LIVE_VALUES = ("state", "home_score", "away_score", "period", "clock", "home_wp", "tie_wp", "last_play_id")
_QUOTE_VALUES = ("kind", "home_prob", "away_prob", "raw_yes_bid", "raw_yes_ask", "overround", "home_ml", "away_ml")


def live_states_for(session: Session, game_ids: list[str]) -> dict[str, LiveState]:
    if not game_ids:
        return {}
    latest_ids = select(func.max(LiveState.id)).where(LiveState.game_id.in_(game_ids)).group_by(LiveState.game_id)
    rows = session.scalars(select(LiveState).where(LiveState.id.in_(latest_ids)))
    return {row.game_id: row for row in rows}


def in_progress_game_ids(session: Session) -> list[str]:
    latest_ids = select(func.max(LiveState.id)).group_by(LiveState.game_id)
    return list(session.scalars(select(LiveState.game_id).where(LiveState.id.in_(latest_ids), LiveState.state == "in")))


def add_live_state(
    session: Session,
    *,
    game_id: str,
    event_id: str,
    fetched_at: datetime,
    state: str,
    home_score: int | None,
    away_score: int | None,
    period: int | None,
    clock: str | None,
    home_wp: float | None,
    tie_wp: float | None,
    last_play_id: str | None,
) -> bool:
    session.flush()
    previous = session.scalar(
        select(LiveState).where(LiveState.game_id == game_id).order_by(LiveState.id.desc()).limit(1)
    )
    values = (state, home_score, away_score, period, clock, home_wp, tie_wp, last_play_id)
    if previous is not None and tuple(getattr(previous, name) for name in _LIVE_VALUES) == values:
        return False
    session.add(
        LiveState(
            game_id=game_id,
            espn_event_id=event_id,
            fetched_at=fetched_at,
            state=state,
            home_score=home_score,
            away_score=away_score,
            period=period,
            clock=clock,
            home_wp=home_wp,
            tie_wp=tie_wp,
            last_play_id=last_play_id,
        )
    )
    return True


def add_quote(
    session: Session,
    *,
    game_id: str,
    source: str,
    kind: str,
    home_prob: float | None,
    away_prob: float | None,
    raw_yes_bid: float | None,
    raw_yes_ask: float | None,
    overround: float | None,
    home_ml: float | None,
    away_ml: float | None,
    fetched_at: datetime,
    source_ts: datetime | None,
) -> bool:
    session.flush()
    previous = session.scalar(
        select(MarketQuote)
        .where(MarketQuote.game_id == game_id, MarketQuote.source == source)
        .order_by(MarketQuote.id.desc())
        .limit(1)
    )
    values = (kind, home_prob, away_prob, raw_yes_bid, raw_yes_ask, overround, home_ml, away_ml)
    if previous is not None and tuple(getattr(previous, name) for name in _QUOTE_VALUES) == values:
        return False
    session.add(
        MarketQuote(
            game_id=game_id,
            source=source,
            kind=kind,
            home_prob=home_prob,
            away_prob=away_prob,
            raw_yes_bid=raw_yes_bid,
            raw_yes_ask=raw_yes_ask,
            overround=overround,
            home_ml=home_ml,
            away_ml=away_ml,
            fetched_at=fetched_at,
            source_ts=source_ts,
        )
    )
    return True


def source_blocked_until(session: Session, source: str) -> datetime | None:
    row = session.get(SourceStatus, source)
    return row.blocked_until if row is not None else None


def last_confirmed(session: Session, source: str) -> datetime | None:
    row = session.get(SourceStatus, source)
    return row.last_ok_at if row is not None else None


def reserve(session: Session, source: str, now: datetime, interval: timedelta) -> bool:
    row = session.get(SourceStatus, source, with_for_update=True, populate_existing=True)
    created = row is None
    if row is None:
        row = SourceStatus(source=source, consecutive_failures=0, updated_at=now)
        session.add(row)
    if row.blocked_until is not None and row.blocked_until > now:
        session.rollback()
        return False
    row.blocked_until = now + interval
    row.updated_at = now
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if created:
            return False
        raise
    return True


def _status(session: Session, source: str, now: datetime) -> SourceStatus:
    row = session.get(SourceStatus, source)
    if row is None:
        row = SourceStatus(source=source, consecutive_failures=0, updated_at=now)
        session.add(row)
    return row


def mark_ok(
    session: Session,
    source: str,
    now: datetime,
    min_interval: timedelta,
    credits_left: int | None | object = UNSET,
) -> None:
    row = _status(session, source, now)
    row.consecutive_failures = 0
    row.blocked_until = now + min_interval
    row.last_ok_at = now
    row.last_error = None
    row.updated_at = now
    if credits_left is not UNSET:
        row.credits_left = credits_left


def mark_failed(
    session: Session,
    source: str,
    now: datetime,
    error: str,
    floor: timedelta = timedelta(0),
) -> None:
    row = _status(session, source, now)
    row.consecutive_failures += 1
    delay = min(BACKOFF_FIRST * 2 ** min(row.consecutive_failures - 1, 7), BACKOFF_MAX)
    row.blocked_until = now + max(floor, delay)
    row.last_error = error[:200]
    row.updated_at = now


def mark_stopped(session: Session, source: str, now: datetime, until: datetime, credits_left: int | None) -> None:
    row = _status(session, source, now)
    row.blocked_until = until
    row.credits_left = credits_left
    row.last_ok_at = now
    row.consecutive_failures = 0
    row.last_error = "credits low"
    row.updated_at = now
