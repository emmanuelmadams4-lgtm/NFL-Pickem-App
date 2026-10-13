"""Refresh ESPN live states with a logged, source-specific backoff."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from nflpi.config import get_settings
from nflpi.ingestion.live import espn, fetch, kalshi, oddsapi, store
from nflpi.models import Game, IngestionRun, LiveState, SourceStatus
from nflpi.predictions.market import implied_prob, novig_home_prob

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
    if isinstance(exc, fetch.FetchError) or (isinstance(exc, ValueError) and str(exc) in ("shape", "event id")):
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


def _quote_game(games: list[Game], teams: set[str], game_date: date) -> Game | None:
    matches = [
        game
        for game in games
        if {game.home_team, game.away_team} == teams and game.kickoff_utc.astimezone(EASTERN).date() == game_date
    ]
    return matches[0] if len(matches) == 1 else None


def _quote_candidates(session: Session, now: datetime) -> list[Game]:
    return list(session.scalars(select(Game).where(Game.kickoff_utc >= now - timedelta(days=3))))


def _source_time(value: datetime | None, now: datetime) -> datetime | None:
    return value if value is not None and now - timedelta(days=7) <= value <= now + timedelta(days=1) else None


def _save_kalshi(session: Session, markets: list[kalshi.Market], game: Game, now: datetime) -> bool:
    by_team = {kalshi.TEAM_CODES[market.team]: market for market in markets}
    home, away = by_team[game.home_team], by_team[game.away_team]
    home_mid, away_mid = (home.bid + home.ask) / 2, (away.bid + away.ask) / 2
    total = home_mid + away_mid
    if total == 0:
        return False
    updated = max(home.updated_time, away.updated_time) if home.updated_time and away.updated_time else None
    return store.add_quote(
        session,
        game_id=game.game_id,
        source="kalshi",
        kind="live" if now >= game.kickoff_utc else "pregame",
        home_prob=home_mid / total,
        away_prob=away_mid / total,
        raw_yes_bid=home.bid,
        raw_yes_ask=home.ask,
        overround=total - 1,
        home_ml=None,
        away_ml=None,
        fetched_at=now,
        source_ts=_source_time(updated, now),
    )


def _kalshi_job(session: Session, get: Callable[[str], fetch.JsonResult], now: datetime) -> tuple[int, int, None]:
    grouped: dict[str, list[kalshi.Market]] = {}
    skipped, cursor = 0, None
    for page in range(3):
        data = get(kalshi.markets_url(cursor)).data
        markets = kalshi.parse_markets(data)
        skipped += len(data["markets"]) - len(markets)
        for market in markets:
            grouped.setdefault(market.event_ticker, []).append(market)
        next_cursor = data.get("cursor")
        if (
            page == 2
            or not isinstance(next_cursor, str)
            or kalshi.CURSOR.fullmatch(next_cursor) is None
            or next_cursor == cursor
        ):
            break
        cursor = next_cursor
    games = _quote_candidates(session, now)
    inserted = 0
    for ticker, markets in grouped.items():
        parts = kalshi.event_parts(ticker)
        if parts is None:
            skipped += 1
            continue
        game_date, (away, home) = parts
        if len(markets) != 2 or {market.team for market in markets} != {away, home}:
            skipped += 1
            continue
        game = _quote_game(games, {kalshi.TEAM_CODES[away], kalshi.TEAM_CODES[home]}, game_date)
        if game is None:
            skipped += 1
            log.debug("unmatched Kalshi event %r", ticker[:64])
        elif (markets[0].bid + markets[0].ask + markets[1].bid + markets[1].ask) == 0:
            skipped += 1
        elif _save_kalshi(session, markets, game, now):
            inserted += 1
    return inserted, skipped, None


def refresh_kalshi_quotes(
    session: Session,
    *,
    get: Callable[[str], fetch.JsonResult] = fetch.fetch_json,
    now: datetime | None = None,
) -> RefreshResult:
    now = datetime.now(UTC) if now is None else now.astimezone(UTC)
    return run_source(
        session,
        status_key="kalshi",
        run_source="kalshi",
        dataset="market_quotes",
        now=now,
        min_interval=KALSHI_MIN_INTERVAL,
        job=lambda: _kalshi_job(session, get, now),
    )


def _save_odds(session: Session, event: oddsapi.Event, book: oddsapi.Book, game: Game, now: datetime) -> bool:
    home_ml, away_ml = (
        (book.home_ml, book.away_ml)
        if oddsapi.TEAM_NAMES[event.home] == game.home_team
        else (book.away_ml, book.home_ml)
    )
    home_prob = novig_home_prob(home_ml, away_ml)
    return store.add_quote(
        session,
        game_id=game.game_id,
        source="oddsapi:" + book.key,
        kind="live" if now >= game.kickoff_utc else "pregame",
        home_prob=home_prob,
        away_prob=1 - home_prob if home_prob is not None else None,
        raw_yes_bid=None,
        raw_yes_ask=None,
        overround=implied_prob(home_ml) + implied_prob(away_ml) - 1,
        home_ml=home_ml,
        away_ml=away_ml,
        fetched_at=now,
        source_ts=_source_time(book.updated, now),
    )


def _odds_job(
    session: Session,
    get: Callable[[str], fetch.JsonResult],
    now: datetime,
    key: str,
    credits: list[int | None],
) -> tuple[int, int, None]:
    result = get(oddsapi.odds_url(key))
    header = result.headers.get("x-requests-remaining")
    if isinstance(header, str) and oddsapi.CREDIT.fullmatch(header) is not None and int(header) <= 1_000_000:
        credits[0] = int(header)
    events, skipped = oddsapi.parse_events(result.data)
    games = _quote_candidates(session, now)
    inserted = 0
    for event in events:
        game = _quote_game(
            games,
            {oddsapi.TEAM_NAMES[event.home], oddsapi.TEAM_NAMES[event.away]},
            event.commence.astimezone(EASTERN).date(),
        )
        if game is None:
            skipped += 1
            continue
        for book in event.books:
            if _save_odds(session, event, book, game, now):
                inserted += 1
    return inserted, skipped, None


def refresh_odds_quotes(
    session: Session,
    *,
    get: Callable[[str], fetch.JsonResult] = fetch.fetch_json,
    now: datetime | None = None,
    api_key: str | None = None,
) -> RefreshResult:
    key = api_key if api_key is not None else get_settings().odds_api_key
    if not isinstance(key, str) or oddsapi.KEY.fullmatch(key) is None:
        return RefreshResult("oddsapi", "skipped", detail="ODDS_API_KEY is not set")
    now = datetime.now(UTC) if now is None else now.astimezone(UTC)
    until = store.source_blocked_until(session, "oddsapi")
    if until is not None and until > now:
        return RefreshResult("oddsapi", "skipped", detail=f"backing off until {until.isoformat()}")
    status = session.get(SourceStatus, "oddsapi")
    if status is not None and status.credits_left is not None and status.credits_left < 50:
        return RefreshResult("oddsapi", "skipped", detail="credits low")
    credits: list[int | None] = [None]
    result = run_source(
        session,
        status_key="oddsapi",
        run_source="oddsapi",
        dataset="market_quotes",
        now=now,
        min_interval=ODDS_MIN_INTERVAL,
        floor=ODDS_MIN_INTERVAL,
        job=lambda: _odds_job(session, get, now, key, credits),
    )
    if result.status == "ok":
        store.mark_ok(session, "oddsapi", now, ODDS_MIN_INTERVAL, credits_left=credits[0])
        if credits[0] is not None and credits[0] < 50:
            store.mark_stopped(session, "oddsapi", now, now + timedelta(days=35), credits[0])
        session.commit()
    return result
