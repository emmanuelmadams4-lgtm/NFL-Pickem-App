"""Refresh ESPN live states with a logged, source-specific backoff."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from nflpi.config import get_settings
from nflpi.ingestion.live import espn, fetch, kalshi, oddsapi, store
from nflpi.models import Game, IngestionRun, LiveState, SourceStatus
from nflpi.predictions.market import implied_prob, novig_home_prob
from nflpi.value import save_prices

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
    if isinstance(exc, fetch.FetchError) or (
        isinstance(exc, ValueError) and str(exc) in ("shape", "event id", "no match")
    ):
        return f"{type(exc).__name__}: {exc}"[:200]
    return type(exc).__name__[:200]


def run_source(
    session: Session,
    *,
    status_key: str,
    ingestion_source: str,
    dataset: str,
    now: datetime,
    min_interval: timedelta,
    job: Callable[[], tuple[int, int, fetch.FetchError | None]],
    floor: timedelta = timedelta(0),
) -> RefreshResult:
    if not store.reserve(session, status_key, now, max(min_interval, floor)):
        until = store.source_blocked_until(session, status_key)
        return RefreshResult(status_key, "skipped", detail=f"backing off until {until.isoformat()}")
    session.add(run := IngestionRun(source=ingestion_source, dataset=dataset, status="running", started_at=now))
    session.commit()
    run_id = run.id
    try:
        inserted, skipped, blocking_error = job()
        run.rows, run.finished_at, run.status = inserted, now, "ok"
        if blocking_error is not None:
            error = safe_error(blocking_error)
            run.status, run.error = "failed", error
            store.mark_failed(session, status_key, now, error, floor)
        else:
            store.mark_ok(session, status_key, now, min_interval)
        result = RefreshResult(status_key, run.status, inserted, skipped, run.error or "")
        session.commit()
        if result.status == "ok":
            log.info("%s: %d inserted, %d skipped", status_key, inserted, skipped)
    except Exception as exc:
        session.rollback()
        error = safe_error(exc)
        for attempt in range(2):
            try:
                run = session.get(IngestionRun, run_id)
                run.status, run.error, run.finished_at = "failed", error, now
                store.mark_failed(session, status_key, now, error, floor)
                session.commit()
                break
            except Exception:
                session.rollback()
                if attempt == 1:
                    raise
        log.warning("%s refresh failed: %s", status_key, error)
        return RefreshResult(status_key, "failed", detail=error)
    if blocking_error is not None:
        log.warning("%s refresh failed: %s", status_key, error)
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
    return espn.parse_win_probability(get(espn.summary_url(event.event_id)).data)


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
        if home_wp is not None and not 0 <= home_wp <= 1:
            home_wp = None
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


def _mark_missing_live_games(session: Session, raw_event_ids: set[str], now: datetime) -> int:
    missing_ids = store.in_progress_game_ids(session)
    newest = store.live_states_for(session, missing_ids)
    lost = 0
    for game_id, previous in newest.items():
        if previous.espn_event_id in raw_event_ids:
            continue
        if store.add_live_state(
            session,
            game_id=game_id,
            event_id=previous.espn_event_id,
            fetched_at=now,
            state="lost",
            home_score=previous.home_score,
            away_score=previous.away_score,
            period=previous.period,
            clock=previous.clock,
            home_wp=None,
            tie_wp=None,
            last_play_id=None,
        ):
            lost += 1
    if lost:
        log.warning("espn_live: %d in-progress games missing from the scoreboard", lost)
    return lost


def _espn_job(
    session: Session,
    get: Callable[[str], fetch.JsonResult],
    now: datetime,
) -> tuple[int, int, fetch.FetchError | None]:
    data = get(espn.SCOREBOARD_URL).data
    raw_events = data.get("events") if isinstance(data, dict) else None
    raw_event_ids = (
        {event.get("id") for event in raw_events if isinstance(event, dict)} if isinstance(raw_events, list) else set()
    )
    events, skipped = espn.parse_scoreboard(data)
    active = [event for event in events if event.state in ("in", "post")]
    if len(active) >= 3 and all(event.home_score is None and event.away_score is None for event in active):
        raise ValueError("shape")
    games = _candidate_games(session, events)
    newest = store.live_states_for(session, [game.game_id for game in games])
    inserted, summaries, summary_failures, matched = 0, 0, 0, 0
    blocking_error: fetch.FetchError | None = None
    for event in events:
        game = _matching_game(event, games)
        if game is None:
            skipped += 1
            log.debug("unmatched ESPN event %r", event.event_id[:64])
            continue
        matched += 1
        probability = None
        if _needs_summary(event, newest.get(game.game_id)) and blocking_error is None and summaries < MAX_SUMMARIES:
            summaries += 1
            try:
                probability = _summary(event, get)
            except fetch.Blocked as exc:
                blocking_error = exc
            except fetch.FetchError:
                summary_failures += 1
        if _save_event(session, event, game, probability, newest.get(game.game_id), now):
            inserted += 1
            session.flush()
            newest[game.game_id] = session.scalar(
                select(LiveState).where(LiveState.game_id == game.game_id).order_by(LiveState.id.desc()).limit(1)
            )
    if summary_failures:
        log.warning("espn_live: %d summaries failed", summary_failures)
    if len(events) >= 3 and matched == 0:
        raise ValueError("no match")
    if raw_event_ids and matched:
        inserted += _mark_missing_live_games(session, raw_event_ids, now)
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
        ingestion_source="espn",
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
    return value if value is not None and value <= now + timedelta(days=1) else None


def _save_kalshi(session: Session, markets: list[kalshi.Market], game: Game, now: datetime) -> bool:
    by_team = {kalshi.TEAM_CODES[market.team]: market for market in markets}
    home, away = by_team[game.home_team], by_team[game.away_team]
    home_mid, away_mid = (home.bid + home.ask) / 2, (away.bid + away.ask) / 2
    total = home_mid + away_mid
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
    seen_cursors: set[str] = set()
    for page in range(3):
        data = get(kalshi.markets_url(cursor)).data
        markets = kalshi.parse_markets(data)
        skipped += len(data["markets"]) - len(markets)
        for market in markets:
            grouped.setdefault(market.event_ticker, []).append(market)
        next_cursor = data.get("cursor")
        if (
            not isinstance(next_cursor, str)
            or kalshi.CURSOR.fullmatch(next_cursor) is None
            or next_cursor in seen_cursors
        ):
            break
        if page == 2:
            log.warning("kalshi: more pages than the 3 read")
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    games = _quote_candidates(session, now)
    inserted, usable, matched = 0, 0, 0
    for ticker, markets in grouped.items():
        parts = kalshi.event_parts(ticker)
        if parts is None:
            skipped += 1
            continue
        game_date, (away, home) = parts
        if len(markets) != 2 or {market.team for market in markets} != {away, home}:
            skipped += 1
            continue
        usable += 1
        game = _quote_game(games, {kalshi.TEAM_CODES[away], kalshi.TEAM_CODES[home]}, game_date)
        if game is None:
            skipped += 1
            log.debug("unmatched Kalshi event %r", ticker[:64])
        else:
            matched += 1
            if _save_kalshi(session, markets, game, now):
                inserted += 1
    if usable >= 3 and matched == 0:
        raise ValueError("no match")
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
        ingestion_source="kalshi",
        dataset="market_quotes",
        now=now,
        min_interval=KALSHI_MIN_INTERVAL,
        job=lambda: _kalshi_job(session, get, now),
    )


def _save_odds(session: Session, event: oddsapi.Event, book: oddsapi.Book, game: Game, now: datetime) -> bool:
    if book.home_ml is None or book.away_ml is None:
        return False  # no usable win-market price; the book's spread and total prices are saved apart
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


BOOK_CLOCK_SKEW = timedelta(minutes=2)  # a book clock further ahead would re-insert one price every poll
FLIP = {"home": "away", "away": "home", "over": "over", "under": "under"}


def _save_book_prices(session: Session, event: oddsapi.Event, book: oddsapi.Book, game: Game, now: datetime) -> int:
    """Every parsed price of one book into book_prices, sides as our game has them (insert-only).

    Each price keeps its own market's time (capped at now); a market whose clock is too far ahead is refused.
    """
    flip = oddsapi.TEAM_NAMES[event.home] != game.home_team
    by_time: dict[datetime, list[dict]] = {}
    for p in book.prices:
        if p.observed_at > now + BOOK_CLOCK_SKEW:
            raise ValueError("book clock ahead of ours")
        by_time.setdefault(min(p.observed_at, now), []).append(
            {
                "market_type": p.market_type,
                "selection": FLIP[p.selection] if flip else p.selection,
                "line": -p.line if flip and p.market_type == "spread" else p.line,
                "price": p.price,
            }
        )
    return sum(save_prices(session, game.game_id, book.key, seen, now, quotes) for seen, quotes in by_time.items())


def _credits_header(result: fetch.JsonResult) -> int | None:
    header = result.headers.get("x-requests-remaining")
    if isinstance(header, str) and oddsapi.CREDIT.fullmatch(header) is not None and int(header) <= 1_000_000:
        return int(header)
    return None


LOW_CREDITS = 50
CREDITS_RESET = timedelta(days=35)  # credits reset monthly: a skipped key is asked again after this
REFUSED = "refused (401)"


def _slot_source(slot: str) -> str:
    return f"oddsapi:{slot}"  # one source_status row per key slot: last count seen (credits_left) and when (last_ok_at)


def _slot_usable(session: Session, slot: str, now: datetime, legacy: SourceStatus | None) -> bool:
    """False while the slot's last remaining count was under 50 and seen less than 35 days ago."""
    row = session.get(SourceStatus, _slot_source(slot), populate_existing=True)
    if row is None and slot == "primary" and legacy is not None and legacy.credits_left is not None:
        # a count stored before per-slot counts existed was the first key's: keep it as the slot's own
        session.add(
            row := SourceStatus(
                source=_slot_source(slot),
                consecutive_failures=0,
                credits_left=legacy.credits_left,
                last_ok_at=legacy.last_ok_at,
                updated_at=now,
            )
        )
        session.commit()
    if row is None or row.credits_left is None or row.credits_left >= LOW_CREDITS:
        return True
    return row.last_ok_at is not None and now >= row.last_ok_at + CREDITS_RESET


def _stop_until(session: Session, keys: list[tuple[str, str]], now: datetime) -> datetime:
    """The earliest moment any low slot is due a retry (35 days after its own low count)."""
    due = [now + CREDITS_RESET]
    for slot, _ in keys:
        row = session.get(SourceStatus, _slot_source(slot), populate_existing=True)
        if row is not None and row.credits_left is not None and row.credits_left < LOW_CREDITS and row.last_ok_at:
            due.append(row.last_ok_at + CREDITS_RESET)
    return min(due)


def _record_slot(session: Session, slot: str, now: datetime, credits: int | None, error: str | None) -> None:
    source = _slot_source(slot)
    row = session.get(SourceStatus, source)
    if row is None:
        session.add(row := SourceStatus(source=source, consecutive_failures=0, updated_at=now))
    row.updated_at, row.last_error = now, error
    if error is None and credits is not None:  # a reply without a count leaves the last known count in place
        row.credits_left, row.last_ok_at = credits, now
    session.commit()  # a later failure in the run must not lose what this key said


@dataclass
class OddsOutcome:
    slot: str = ""
    credits: int | None = None
    refused: tuple[str, ...] = ()


def _get_odds(
    session: Session,
    get: Callable[[str], fetch.JsonResult],
    keys: list[tuple[str, str]],
    extra: bool,
    now: datetime,
    outcome: OddsOutcome,
) -> fetch.JsonResult:
    """Ask each usable key in turn; a 401 is a second signal that moves on to the next. Counts come from the header."""
    refused: list[str] = []
    for slot, key in keys:
        try:
            result = get(oddsapi.odds_url(key, extra_markets=extra))
        except fetch.Blocked as exc:
            if str(exc) != "status 401":  # a 429 is a burst limit that another key does not cure
                raise
            refused.append(slot)
            _record_slot(session, slot, now, None, REFUSED)
            log.warning("oddsapi key slot %s %s", slot, REFUSED)
            if len(refused) == len(keys) and len(keys) > 1:
                outcome.refused = tuple(refused)
                raise fetch.Blocked("both keys refused (401)") from exc
            if slot == keys[-1][0]:
                outcome.refused = tuple(refused)
                raise
            continue
        count = _credits_header(result)
        log.info("oddsapi key slot %s used, credits remaining: %s", slot, count)
        _record_slot(session, slot, now, count, None)
        outcome.slot, outcome.credits, outcome.refused = slot, count, tuple(refused)
        return result
    raise AssertionError("no key")  # pragma: no cover


def _odds_job(
    session: Session,
    get: Callable[[str], fetch.JsonResult],
    now: datetime,
    keys: list[tuple[str, str]],
    outcome: OddsOutcome,
    extra: bool,
) -> tuple[int, int, None]:
    result = _get_odds(session, get, keys, extra, now, outcome)
    events, skipped = oddsapi.parse_events(result.data)
    games = _quote_candidates(session, now)
    inserted, matched, saved, dropped = 0, 0, 0, 0
    for event in events:
        game = _quote_game(
            games,
            {oddsapi.TEAM_NAMES[event.home], oddsapi.TEAM_NAMES[event.away]},
            event.commence.astimezone(EASTERN).date(),
        )
        if game is None:
            skipped += 1
            continue
        matched += 1
        for book in event.books:
            if _save_odds(session, event, book, game, now):
                inserted += 1
            try:
                with session.begin_nested():
                    saved += _save_book_prices(session, event, book, game, now)
            except Exception as exc:  # never lose the win-market quotes over a book price
                dropped += len(book.prices)
                log.warning("oddsapi book prices skipped for %s: %s", book.key, safe_error(exc))
    log.info("oddsapi book prices: %d saved, %d dropped", saved, dropped)
    if len(events) >= 3 and matched == 0:
        raise ValueError("no match")
    return inserted, skipped, None


def _answer_note(outcome: OddsOutcome) -> str:
    left = f"{outcome.credits} credits left" if outcome.credits is not None else "credits left not given"
    if outcome.refused:
        return f"{' and '.join(outcome.refused)} refused (401), on {outcome.slot}; {left}"
    return f"{outcome.slot} answered; {left}"


def refresh_odds_quotes(
    session: Session,
    *,
    get: Callable[[str], fetch.JsonResult] = fetch.fetch_json,
    now: datetime | None = None,
    api_key: str | None = None,
    fallback_key: str | None = None,
) -> RefreshResult:
    settings = get_settings()
    key = api_key if api_key is not None else settings.odds_api_key
    if not isinstance(key, str) or oddsapi.KEY.fullmatch(key) is None:
        return RefreshResult("oddsapi", "skipped", detail="ODDS_API_KEY is not set")
    spare = fallback_key if fallback_key is not None else settings.odds_api_key_fallback
    keys = [("primary", key)]
    if isinstance(spare, str) and oddsapi.KEY.fullmatch(spare) is not None and spare != key:
        keys.append(("fallback", spare))
    now = datetime.now(UTC) if now is None else now.astimezone(UTC)
    status = session.get(SourceStatus, "oddsapi", populate_existing=True)
    usable = [(slot, k) for slot, k in keys if _slot_usable(session, slot, now, status)]
    if not usable:
        log.warning("oddsapi stopped: credits low")
        return RefreshResult("oddsapi", "skipped", detail="credits low")
    if status is not None and status.last_error == "credits low" and status.blocked_until is not None:
        status.blocked_until = None  # an earlier stop on a key that is usable again (a second key, or 35 days on)
        session.commit()
    outcome = OddsOutcome()
    result = run_source(
        session,
        status_key="oddsapi",
        ingestion_source="oddsapi",
        dataset="market_quotes",
        now=now,
        min_interval=ODDS_MIN_INTERVAL,
        floor=ODDS_MIN_INTERVAL,
        job=lambda: _odds_job(session, get, now, usable, outcome, settings.odds_extra_markets),
    )
    if result.status == "ok":
        note = _answer_note(outcome)
        store.mark_ok(
            session,
            "oddsapi",
            now,
            ODDS_MIN_INTERVAL,
            credits_left=outcome.credits if outcome.credits is not None else store.UNSET,
        )
        if outcome.refused:
            session.get(SourceStatus, "oddsapi").last_error = note.split(";")[0]
        spare = [slot for slot, _ in usable if slot != outcome.slot and slot not in outcome.refused]
        if outcome.credits is not None and outcome.credits < LOW_CREDITS and not spare:
            store.mark_stopped(session, "oddsapi", now, _stop_until(session, keys, now), outcome.credits)
            log.warning("oddsapi stopped: credits low")
        session.commit()
        result = replace(result, detail=note)
    return result
