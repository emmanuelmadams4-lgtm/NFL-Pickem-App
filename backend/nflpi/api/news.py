"""Latest news for one game: read-only, allowlisted sources, text and links re-sanitised on the way out."""

import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from nflpi.db import get_session
from nflpi.ingestion.news import parse, sources
from nflpi.models import Game, NewsItem

MAX_ITEMS = 5
TITLE_MAX = 200
KNOWN_TAGS = ("coach", "injury", "playcaller", "trade")
GAME_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,32}")
BAD_GAME_ID = "game_id must be 1 to 32 letters, digits, - or _"

router = APIRouter(prefix="/api")


class NewsItemOut(BaseModel):
    title: str = Field(description="Headline as plain text, at most 200 characters, no angle brackets")
    source: str = Field(description="Display name of the feed the item came from")
    published_at: datetime | None = Field(description="When the feed published it; null when the feed gave none")
    url: str | None = Field(description="Story link; null unless a safe https link on the item's own source host")
    tags: list[str] = Field(description="Any of coach, injury, playcaller, trade, sorted")


class NewsOut(BaseModel):
    game_id: str
    items: list[NewsItemOut] = Field(description="Up to 5 newest items that mention either team of the game")


def _plain_title(raw: str) -> str:
    """Clean first, then drop angle brackets last so nothing can decode into markup afterwards."""
    cleaned = parse.clean_text(raw, TITLE_MAX).replace("<", "").replace(">", "")
    return " ".join(cleaned.split())


def _item(row: NewsItem, by_id: dict[str, sources.Source]) -> NewsItemOut | None:
    title = _plain_title(row.title)
    src = by_id.get(row.source)
    if not title or src is None:
        return None
    return NewsItemOut(
        title=title,
        source=src.name or src.id,
        published_at=row.published_at,
        url=parse.canonical_url(row.url_canonical, src.link_suffixes),
        tags=sorted(tag for tag in set(row.tags) if tag in KNOWN_TAGS),
    )


def latest_news_rows(session: Session, game: Game, limit: int = MAX_ITEMS) -> list[NewsItem]:
    by_id = {src.id: src for src in sources.SOURCES}
    teams = cast(NewsItem.team_ids, JSONB)
    return list(
        session.scalars(
            select(NewsItem)
            .where(
                NewsItem.source.in_(list(by_id)),
                or_(teams.contains([game.home_team]), teams.contains([game.away_team])),
            )
            .order_by(NewsItem.published_at.desc().nulls_last(), NewsItem.fetched_at.desc(), NewsItem.id.desc())
            .limit(limit)
        ).all()
    )


@router.get("/news", response_model=NewsOut)
def news(session: Annotated[Session, Depends(get_session)], game_id: str | None = None) -> NewsOut:
    if game_id is None or not GAME_ID_PATTERN.fullmatch(game_id):
        raise HTTPException(422, BAD_GAME_ID)
    game = session.get(Game, game_id)
    if game is None:
        raise HTTPException(404, "Game not found")
    by_id = {src.id: src for src in sources.SOURCES}
    items = [item for row in latest_news_rows(session, game) if (item := _item(row, by_id)) is not None]
    return NewsOut(game_id=game.game_id, items=items)
