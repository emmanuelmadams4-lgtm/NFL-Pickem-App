"""FastAPI app: JSON API under /api, plus the built web app at / when present."""

import csv
import io
import logging
import secrets
import threading
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from nflpi.ai import providers, research
from nflpi.ai.providers import AIError
from nflpi.api import schemas as s
from nflpi.api import views
from nflpi.config import get_settings
from nflpi.db import get_session, session_factory
from nflpi.ingestion.service import freshness
from nflpi.models import AppSetting, BacktestRun, Game, PushSubscription, UserPick
from nflpi.notify import push
from nflpi.predictions import engine

log = logging.getLogger(__name__)
DB = Annotated[Session, Depends(get_session)]


def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().app_access_token
    if not expected:
        raise HTTPException(503, "Server has no APP_ACCESS_TOKEN set")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Missing or wrong access token")


public = APIRouter(prefix="/api")
api = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


@public.get("/health", response_model=s.HealthOut)
def health(session: DB) -> s.HealthOut:
    try:
        session.execute(text("select 1"))
        db_ok = True
    except Exception:  # noqa: BLE001 - health reports, never raises
        return s.HealthOut(status="degraded", database=False, active_model=False, stale_datasets=[])
    stale = [f["dataset"] for f in freshness(session) if f["stale"]]
    has_model = engine.active_model(session) is not None
    return s.HealthOut(
        status="ok" if has_model and not stale else "degraded",
        database=db_ok,
        active_model=has_model,
        stale_datasets=stale,
    )


@api.get("/meta", response_model=s.MetaOut)
def meta(session: DB) -> s.MetaOut:
    season, week = engine.current_week(session)
    mv = engine.active_model(session)
    weeks = session.scalars(select(Game.week).where(Game.season == season).distinct().order_by(Game.week)).all()
    seasons = session.scalars(select(Game.season).distinct().order_by(Game.season.desc())).all()
    return s.MetaOut(
        current_season=season,
        current_week=week,
        seasons=list(seasons),
        weeks=list(weeks),
        model_name=mv.name if mv else None,
        model_trained_through=mv.trained_through_season if mv else None,
        ai_providers=providers.available(),
        push_public_key=get_settings().vapid_public_key if push.configured() else None,
        push_subscriptions=session.scalar(select(func.count()).select_from(PushSubscription)) or 0,
        reminder_minutes=views.get_setting(session, "reminder_minutes"),
        league_leader_accuracy=views.get_setting(session, "league_leader_accuracy"),
        server_time=datetime.now(UTC),
    )


@api.get("/weeks/{season}/{week}", response_model=s.WeekOut)
def week(season: int, week: int, session: DB) -> s.WeekOut:
    return views.week_view(session, season, week)


@api.get("/games/{game_id}", response_model=s.GameDetail)
def game(game_id: str, session: DB) -> s.GameDetail:
    detail = views.game_detail(session, game_id)
    if detail is None:
        raise HTTPException(404, "Game not found")
    return detail


@api.put("/picks/{game_id}", response_model=s.PickOut)
def set_pick(game_id: str, body: s.PickIn, session: DB) -> s.PickOut:
    g = session.get(Game, game_id)
    if g is None:
        raise HTTPException(404, "Game not found")
    if body.team not in (g.home_team, g.away_team):
        raise HTTPException(422, f"Pick must be {g.away_team} or {g.home_team}")
    if g.kickoff_utc <= datetime.now(UTC):
        raise HTTPException(409, "Game has kicked off; pick is locked")
    pick = session.get(UserPick, game_id) or UserPick(game_id=game_id)
    pick.picked_team, pick.picked_at, pick.source = body.team, datetime.now(UTC), "app"
    session.add(pick)
    session.commit()
    return s.PickOut.model_validate(pick, from_attributes=True)


@api.delete("/picks/{game_id}", status_code=204)
def clear_pick(game_id: str, session: DB) -> Response:
    g = session.get(Game, game_id)
    if g is not None and g.kickoff_utc <= datetime.now(UTC):
        raise HTTPException(409, "Game has kicked off; pick is locked")
    pick = session.get(UserPick, game_id)
    if pick:
        session.delete(pick)
        session.commit()
    return Response(status_code=204)


@api.get("/picks/export.csv")
def export_picks(season: int, session: DB) -> Response:
    games = session.scalars(select(Game).where(Game.season == season).order_by(Game.kickoff_utc)).all()
    summaries = {g.game_id: g for g in views.summaries(session, list(games), datetime.now(UTC))}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["game_id", "season", "week", "away", "home", "my_pick", "model_pick", "model_pick_prob", "winner"])
    for g in games:
        sm = summaries[g.game_id]
        p = sm.prediction
        w.writerow(
            [
                g.game_id,
                g.season,
                g.week,
                g.away_team,
                g.home_team,
                sm.my_pick or "",
                p.pick if p else "",
                f"{max(p.home_win_prob, p.away_win_prob):.3f}" if p else "",
                views.winner(g) or "",
            ]
        )
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="picks-{season}.csv"'},
    )


@api.post("/picks/import", response_model=s.ImportResult)
async def import_picks(request: Request, session: DB) -> s.ImportResult:
    """CSV with columns game_id and my_pick (or picked_team). Past games allowed, for Yahoo history."""
    body = (await request.body()).decode("utf-8-sig")
    imported, skipped = 0, []
    for row in csv.DictReader(io.StringIO(body)):
        gid = (row.get("game_id") or "").strip()
        team = (row.get("my_pick") or row.get("picked_team") or "").strip().upper()
        g = session.get(Game, gid)
        if not team:
            continue
        if g is None or team not in (g.home_team, g.away_team):
            skipped.append(gid or "?")
            continue
        pick = session.get(UserPick, gid) or UserPick(game_id=gid)
        pick.picked_team, pick.picked_at, pick.source = team, datetime.now(UTC), "csv"
        session.add(pick)
        imported += 1
    session.commit()
    return s.ImportResult(imported=imported, skipped=skipped)


@api.get("/performance/{season}", response_model=s.PerformanceOut)
def performance(season: int, session: DB) -> s.PerformanceOut:
    return views.performance(session, season)


@api.get("/backtest", response_model=s.BacktestOut)
def backtest(session: DB) -> s.BacktestOut:
    run = session.scalars(select(BacktestRun).order_by(BacktestRun.id.desc()).limit(1)).first()
    if run is None:
        raise HTTPException(404, "No backtest yet; run `python -m nflpi.jobs train`")
    return s.BacktestOut(created_at=run.created_at, **run.results)


@api.post("/games/{game_id}/report", response_model=s.AIReportOut)
def make_report(game_id: str, session: DB, provider: s.Provider = "claude") -> s.AIReportOut:
    try:
        return research.generate_report(session, game_id, provider)
    except AIError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.post("/games/{game_id}/ask", response_model=s.AskOut)
def ask(game_id: str, body: s.AskIn, session: DB) -> s.AskOut:
    try:
        return research.answer_question(session, game_id, body.question, body.provider)
    except AIError as exc:
        raise HTTPException(503, str(exc)) from exc


@api.post("/push/subscribe", status_code=204)
def push_subscribe(body: s.PushSubscriptionIn, session: DB) -> Response:
    sub = session.scalars(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)).first()
    sub = sub or PushSubscription(endpoint=body.endpoint)
    sub.p256dh, sub.auth, sub.last_seen = body.keys.p256dh, body.keys.auth, datetime.now(UTC)
    session.add(sub)
    session.commit()
    return Response(status_code=204)


@api.delete("/push/subscribe", status_code=204)
def push_unsubscribe(endpoint: str, session: DB) -> Response:
    sub = session.scalars(select(PushSubscription).where(PushSubscription.endpoint == endpoint)).first()
    if sub:
        session.delete(sub)
        session.commit()
    return Response(status_code=204)


@api.put("/settings", response_model=s.MetaOut)
def update_settings(body: s.SettingsIn, session: DB) -> s.MetaOut:
    for key in body.model_fields_set:
        row = session.get(AppSetting, key) or AppSetting(key=key)
        row.value = {"v": getattr(body, key)}
        session.add(row)
    session.commit()
    return meta(session)


_refresh_lock = threading.Lock()


def _refresh_job() -> None:
    from nflpi import jobs  # imported here: jobs pulls in the push module and CLI only when used

    try:
        with session_factory()() as session:
            jobs.ingest(session, weather=True)
            jobs.predict(session)
    except Exception:  # noqa: BLE001 - background job; failure is logged and visible in freshness
        log.exception("manual refresh failed")
    finally:
        _refresh_lock.release()


@api.post("/refresh", status_code=202)
def refresh() -> dict:
    """Start a data + prediction refresh in the background (one at a time)."""
    if not _refresh_lock.acquire(blocking=False):
        return {"started": False, "reason": "A refresh is already running"}
    threading.Thread(target=_refresh_job, daemon=True).start()
    return {"started": True}


@api.get("/freshness", response_model=list[s.DatasetFreshness])
def data_freshness(session: DB) -> list[s.DatasetFreshness]:
    return [s.DatasetFreshness(**f) for f in freshness(session)]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="NFL Pick'em Intelligence", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(public)
    app.include_router(api)
    if settings.web_dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dist_dir, html=True), name="web")
    return app


app = create_app()
