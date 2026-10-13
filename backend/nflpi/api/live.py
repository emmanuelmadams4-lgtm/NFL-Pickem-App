"""Current game scores and live market prices for the web app."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.db import get_session
from nflpi.ingestion.live import store
from nflpi.models import Game, LiveState, MarketQuote

MAX_GAMES = 20
LIVE_AGE = timedelta(hours=8)
STALE_AFTER = timedelta(seconds=120)
KALSHI_POLL_MAX_AGE = timedelta(minutes=5)
KALSHI_ROW_MAX_AGE = timedelta(minutes=15)

router = APIRouter(prefix="/api")


class LiveGameOut(BaseModel):
    game_id: str
    state: Literal["in", "post", "lost"]
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    home_win_prob: float | None = Field(description="ESPN's home win probability; null means none right now")
    kalshi_home_prob: float | None = Field(description="Kalshi's fresh live home price; null when unavailable")
    updated_at: datetime = Field(description="When this game's numbers last changed")


class LiveOut(BaseModel):
    games: list[LiveGameOut]
    stale: bool = Field(
        description="True when a game is in play or lost and the last good ESPN poll is missing or over 2 minutes old"
    )
    last_confirmed_at: datetime | None = Field(description="Time of the last good ESPN live poll, if any")


def _now() -> datetime:
    return datetime.now(UTC)


EASTERN = ZoneInfo("America/New_York")


def _visible(session: Session, now: datetime) -> tuple[list[Game], dict[str, LiveState]]:
    """Games to show, earliest kickoff first, with their newest live state."""
    today = now.astimezone(EASTERN).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=EASTERN).astimezone(UTC)
    lower = min(today_start, now - LIVE_AGE)
    candidates = session.scalars(
        select(Game).where(Game.kickoff_utc >= lower, Game.kickoff_utc <= now + timedelta(hours=1))
    ).all()
    states = store.live_states_for(session, [game.game_id for game in candidates])
    kept = [
        game
        for game in candidates
        if (state := states.get(game.game_id)) is not None
        and (
            (state.state in ("in", "lost") and game.kickoff_utc >= now - LIVE_AGE)
            or (state.state == "post" and game.kickoff_utc.astimezone(EASTERN).date() == today)
        )
    ]
    kept.sort(key=lambda game: (game.kickoff_utc, game.game_id))
    return kept[:MAX_GAMES], states


def _kalshi_prices(session: Session, game_ids: list[str], now: datetime) -> dict[str, float | None]:
    """Newest live Kalshi home price per game, only while Kalshi was heard from lately and the row is young."""
    last = store.last_confirmed(session, "kalshi")
    if not game_ids or last is None or now - last > KALSHI_POLL_MAX_AGE:
        return {}
    newest_ids = (
        select(func.max(MarketQuote.id))
        .where(MarketQuote.game_id.in_(game_ids), MarketQuote.source == "kalshi", MarketQuote.kind == "live")
        .group_by(MarketQuote.game_id)
    )
    return {
        quote.game_id: quote.home_prob
        for quote in session.scalars(select(MarketQuote).where(MarketQuote.id.in_(newest_ids)))
        if quote.fetched_at >= now - KALSHI_ROW_MAX_AGE
    }


@router.get("/live", response_model=LiveOut)
def live(session: Annotated[Session, Depends(get_session)]) -> LiveOut:
    now = _now()
    kept, states = _visible(session, now)
    prices = _kalshi_prices(session, [g.game_id for g in kept if states[g.game_id].state == "in"], now)
    games = [
        LiveGameOut(
            game_id=game.game_id,
            state=states[game.game_id].state,
            home_team=game.home_team,
            away_team=game.away_team,
            home_score=states[game.game_id].home_score,
            away_score=states[game.game_id].away_score,
            period=states[game.game_id].period,
            clock=states[game.game_id].clock,
            home_win_prob=states[game.game_id].home_wp,
            kalshi_home_prob=prices.get(game.game_id),
            updated_at=states[game.game_id].fetched_at,
        )
        for game in kept
    ]
    last = store.last_confirmed(session, "espn_live")
    playing = any(game.state in ("in", "lost") for game in games)
    return LiveOut(games=games, stale=playing and (last is None or now - last > STALE_AFTER), last_confirmed_at=last)
