"""Token-protected group file import and weekly group views."""

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from nflpi.db import get_session, session_factory
from nflpi.group import importer, queries
from nflpi.group.importer import GroupDatabaseError, GroupImportError, ImportResult, import_group_csv
from nflpi.models import Game

log = logging.getLogger(__name__)


def _token(authorization: Annotated[str | None, Header()] = None) -> None:
    from nflpi.api.main import require_token

    require_token(authorization)


router = APIRouter(prefix="/api/group", dependencies=[Depends(_token)])
DB = Annotated[Session, Depends(get_session)]


class ImportOut(BaseModel):
    season: int
    kind: Literal["picks", "standings"]
    rows: int


class StandingOut(BaseModel):
    member: str
    points: int
    total: int
    rank: int | None


class StandingsOut(BaseModel):
    season: int
    week: int
    weeks_counted: list[int]
    rows: list[StandingOut]


class SideOut(BaseModel):
    team: str
    picks: int
    share: float | None
    avg_confidence: float | None


class GameShareOut(BaseModel):
    game_id: str
    away_team: str
    home_team: str
    kickoff_utc: datetime
    members: int
    picked: int
    away: SideOut
    home: SideOut


class SharesOut(BaseModel):
    season: int
    week: int
    games: list[GameShareOut]


def _import_file(season: int, data: bytearray) -> ImportResult:
    with session_factory()() as session:
        if session.scalar(select(Game.game_id).where(Game.season == season).limit(1)) is None:
            raise GroupImportError("no games for this season")
        return import_group_csv(session, season, data)


@router.post("/import", response_model=ImportOut)
async def import_csv(request: Request, season: Annotated[int, Query(ge=2000, le=2100)]) -> ImportOut:
    cap = importer.MAX_BYTES
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            too_big = int(content_length) > cap
        except ValueError:
            raise HTTPException(400, "bad content-length") from None
        if too_big:
            raise HTTPException(413, "file is too large")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > cap:
            raise HTTPException(413, "file is too large")
        data.extend(chunk)
    try:
        result = await run_in_threadpool(_import_file, season, data)
    except GroupImportError as exc:
        raise HTTPException(422, str(exc)) from None
    except GroupDatabaseError as exc:
        log.warning("group import database error: %s", exc)
        raise HTTPException(500, "group import failed: database error") from None
    return ImportOut(season=season, kind=result.kind, rows=result.rows)


@router.get("/standings", response_model=StandingsOut)
def standings(season: Annotated[int, Query(ge=2000, le=2100)], week: Annotated[int, Query(ge=1, le=22)],
              session: DB) -> StandingsOut:
    return StandingsOut(season=season, week=week, weeks_counted=queries.standing_weeks(session, season, week),
                        rows=queries.standings(session, season, week))


@router.get("/shares", response_model=SharesOut)
def shares(season: Annotated[int, Query(ge=2000, le=2100)], week: Annotated[int, Query(ge=1, le=22)],
           session: DB) -> SharesOut:
    return SharesOut(season=season, week=week, games=queries.week_shares(session, season, week))
