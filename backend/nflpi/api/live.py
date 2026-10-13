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
from nflpi.models import Game, MarketQuote

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
    stale: bool = Field(description="True when the last good ESPN poll is missing or over 2 minutes old")
    last_confirmed_at: datetime | None = Field(description="Time of the last good ESPN live poll, if any")


def _now() -> datetime:
    return datetime.now(UTC)


@router.get("/live", response_model=LiveOut)
def live(session: Annotated[Session, Depends(get_session)]) -> LiveOut:
    now = _now()
    eastern = ZoneInfo("America/New_York")
    today = now.astimezone(eastern).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=eastern).astimezone(UTC)
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
            or (state.state == "post" and game.kickoff_utc.astimezone(eastern).date() == today)
        )
    ]
    kept.sort(key=lambda game: (game.kickoff_utc, game.game_id))
    kept = kept[:MAX_GAMES]

    in_ids = [game.game_id for game in kept if states[game.game_id].state == "in"]
    quotes: dict[str, MarketQuote] = {}
    if in_ids:
        kalshi_last = store.last_confirmed(session, "kalshi")
        if kalshi_last is not None and now - kalshi_last <= KALSHI_POLL_MAX_AGE:
            newest_ids = (
                select(func.max(MarketQuote.id))
                .where(MarketQuote.game_id.in_(in_ids), MarketQuote.source == "kalshi", MarketQuote.kind == "live")
                .group_by(MarketQuote.game_id)
            )
            quotes = {
                quote.game_id: quote
                for quote in session.scalars(select(MarketQuote).where(MarketQuote.id.in_(newest_ids)))
            }

    games = []
    for game in kept:
        state = states[game.game_id]
        quote = quotes.get(game.game_id)
        games.append(
            LiveGameOut(
                game_id=game.game_id,
                state=state.state,
                home_team=game.home_team,
                away_team=game.away_team,
                home_score=state.home_score,
                away_score=state.away_score,
                period=state.period,
                clock=state.clock,
                home_win_prob=state.home_wp,
                kalshi_home_prob=(
                    quote.home_prob if quote is not None and quote.fetched_at >= now - KALSHI_ROW_MAX_AGE else None
                ),
                updated_at=state.fetched_at,
            )
        )

    last = store.last_confirmed(session, "espn_live")
    return LiveOut(games=games, stale=last is None or now - last > STALE_AFTER, last_confirmed_at=last)
