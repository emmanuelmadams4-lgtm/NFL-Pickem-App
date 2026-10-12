"""Read models: turn database rows into API responses."""

from collections import defaultdict
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nflpi.analytics.metrics import calibration, wilson_ci
from nflpi.api import schemas as s
from nflpi.ingestion.service import freshness
from nflpi.models import (
    AIReport,
    AppSetting,
    Game,
    InjuryReport,
    MarketSnapshot,
    ModelVersion,
    Prediction,
    Team,
    UserPick,
    WeatherForecast,
)

ALERT_STATUSES = ("Out", "Doubtful", "Questionable")


def now_utc() -> datetime:
    return datetime.now(UTC)


def status_of(g: Game, now: datetime) -> str:
    if g.status in ("final", "postponed"):
        return g.status
    if g.time_tbd:
        return "scheduled"
    return "in_progress" if g.kickoff_utc <= now else "scheduled"


def winner(g: Game) -> str | None:
    if g.status != "final" or g.home_score is None or g.home_score == g.away_score:
        return None
    return g.home_team if g.home_score > g.away_score else g.away_team


def get_setting(session: Session, key: str):
    row = session.get(AppSetting, key)
    return row.value.get("v") if row else None


def team_out(t: Team | None, abbr: str) -> s.TeamOut:
    if t is None:
        return s.TeamOut(
            abbr=abbr, name=abbr, nick=abbr, conference="", division="", color="#555555", color2="#999999", logo_url=""
        )
    return s.TeamOut.model_validate(t, from_attributes=True)


def prediction_out(p: Prediction, names: dict[int, str]) -> s.PredictionOut:
    return s.PredictionOut(
        id=p.id,
        created_at=p.created_at,
        kind=p.kind,
        model_version=names.get(p.model_version_id, "?"),
        home_win_prob=p.home_win_prob,
        away_win_prob=round(1 - p.home_win_prob, 4),
        pick=p.pick,
        uncertainty=p.uncertainty,
        uncertainty_reasons=p.uncertainty_reasons,
        factors=p.factors,
        market_home_prob=p.market_home_prob,
        stats_only_home_prob=p.features.get("stats_only_prob"),
        upset_flags=p.features.get("upset_flags", []),
        change_note=p.change_note,
        data_freshness=p.data_freshness,
    )


def _records(session: Session, season: int, teams: set[str]) -> dict[str, list[Game]]:
    finals = session.scalars(
        select(Game)
        .where(Game.season == season, Game.status == "final", or_(Game.home_team.in_(teams), Game.away_team.in_(teams)))
        .order_by(Game.kickoff_utc)
    ).all()
    by_team: dict[str, list[Game]] = defaultdict(list)
    for g in finals:
        by_team[g.home_team].append(g)
        by_team[g.away_team].append(g)
    return by_team


def record_before(games: list[Game], team: str, before: datetime, where: str | None = None) -> str:
    wins = losses = ties = 0
    for g in games:
        if g.kickoff_utc >= before:
            continue
        if where == "home" and g.home_team != team or where == "away" and g.away_team != team:
            continue
        win = winner(g)
        if win is None:
            ties += 1
        elif win == team:
            wins += 1
        else:
            losses += 1
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _latest_by_game(session: Session, model, game_ids: list[str]) -> dict:
    rows = session.scalars(select(model).where(model.game_id.in_(game_ids)).order_by(model.id)).all()
    return {r.game_id: r for r in rows}


def _week_injuries(session: Session, season: int, week: int, teams: set[str]) -> dict[str, list[InjuryReport]]:
    latest: dict[tuple, InjuryReport] = {}
    for r in session.scalars(
        select(InjuryReport)
        .where(InjuryReport.season == season, InjuryReport.week == week, InjuryReport.team.in_(teams))
        .order_by(InjuryReport.id)
    ):
        latest[(r.team, r.player_id or r.player)] = r
    by_team: dict[str, list[InjuryReport]] = defaultdict(list)
    for (team, _), r in latest.items():
        by_team[team].append(r)
    return by_team


def _weather(g: Game, wx: WeatherForecast | None) -> s.WeatherOut | None:
    if g.status == "final" and (g.temp_f is not None or g.wind_mph is not None):
        return s.WeatherOut(kind="observed", observed_at=None, temp_f=g.temp_f, wind_mph=g.wind_mph)
    if wx is not None:
        return s.WeatherOut(
            kind="forecast",
            observed_at=wx.observed_at,
            temp_f=wx.temp_f,
            wind_mph=wx.wind_mph,
            gust_mph=wx.gust_mph,
            precip_prob=wx.precip_prob,
            precip_in=wx.precip_in,
        )
    return None


def summaries(session: Session, games: list[Game], now: datetime) -> list[s.GameSummary]:
    if not games:
        return []
    ids = [g.game_id for g in games]
    teams = {t.abbr: t for t in session.scalars(select(Team))}
    names = dict(session.execute(select(ModelVersion.id, ModelVersion.name)).all())
    picks = {p.game_id: p for p in session.scalars(select(UserPick).where(UserPick.game_id.in_(ids)))}
    preds_all = session.scalars(select(Prediction).where(Prediction.game_id.in_(ids)).order_by(Prediction.id)).all()
    wx = _latest_by_game(session, WeatherForecast, ids)
    season = games[0].season
    involved = {g.home_team for g in games} | {g.away_team for g in games}
    recs = _records(session, season, involved)
    weeks = {g.week for g in games}
    injuries = {w: _week_injuries(session, season, w, involved) for w in weeks}

    out = []
    for g in games:
        # The recommendation for a game is the last snapshot made before kickoff.
        pre = [
            p for p in preds_all if p.game_id == g.game_id and (p.created_at < g.kickoff_utc or p.kind == "backfill")
        ]
        pred = pre[-1] if pre else None
        win = winner(g)
        pick = picks.get(g.game_id)
        inj = injuries[g.week]
        qb_alerts = [
            f"{r.team} QB {r.player}: {r.report_status}"
            for team in (g.away_team, g.home_team)
            for r in inj.get(team, [])
            if r.position == "QB" and r.report_status in ALERT_STATUSES
        ]
        out.append(
            s.GameSummary(
                game_id=g.game_id,
                season=g.season,
                week=g.week,
                game_type=g.game_type,
                kickoff_utc=g.kickoff_utc,
                status=status_of(g, now),
                away=team_out(teams.get(g.away_team), g.away_team),
                home=team_out(teams.get(g.home_team), g.home_team),
                away_score=g.away_score,
                home_score=g.home_score,
                away_record=record_before(recs[g.away_team], g.away_team, g.kickoff_utc),
                home_record=record_before(recs[g.home_team], g.home_team, g.kickoff_utc),
                stadium=g.stadium,
                roof=g.roof,
                neutral_site=g.neutral_site,
                div_game=g.div_game,
                prediction=prediction_out(pred, names) if pred else None,
                my_pick=pick.picked_team if pick else None,
                my_pick_correct=(pick.picked_team == win) if pick and win else None,
                model_correct=(pred.pick == win) if pred and win else None,
                locked=g.status != "postponed" and not g.time_tbd and g.kickoff_utc <= now,
                qb_not_projected=g.status != "final" and (not g.home_qb or not g.away_qb),
                qb_alerts=qb_alerts,
                injury_count=sum(
                    1
                    for team in (g.away_team, g.home_team)
                    for r in inj.get(team, [])
                    if r.report_status in ALERT_STATUSES
                ),
                weather=_weather(g, wx.get(g.game_id)),
            )
        )
    return out


def week_view(session: Session, season: int, week: int) -> s.WeekOut:
    now = now_utc()
    games = session.scalars(
        select(Game).where(Game.season == season, Game.week == week).order_by(Game.kickoff_utc, Game.game_id)
    ).all()
    items = summaries(session, games, now)
    perf = performance(session, season)
    graded = [g for g in items if g.my_pick_correct is not None]
    mgraded = [g for g in items if g.model_correct is not None]
    attention = sum(
        1
        for g in items
        if g.status == "scheduled" and g.prediction and (g.prediction.uncertainty == "high" or g.prediction.upset_flags)
    )
    summary = s.WeekSummary(
        games_total=len(items),
        games_final=sum(g.status == "final" for g in items),
        games_remaining=sum(g.status != "final" for g in items),
        picks_made=sum(g.my_pick is not None for g in items),
        picks_correct=sum(bool(g.my_pick_correct) for g in graded),
        picks_incorrect=sum(not g.my_pick_correct for g in graded),
        my_accuracy=(sum(bool(g.my_pick_correct) for g in graded) / len(graded)) if graded else None,
        model_correct=sum(bool(g.model_correct) for g in mgraded),
        model_graded=len(mgraded),
        model_accuracy=(sum(bool(g.model_correct) for g in mgraded) / len(mgraded)) if mgraded else None,
        season_my_accuracy=perf.me.accuracy,
        season_model_accuracy=perf.model.accuracy,
        league_leader_accuracy=get_setting(session, "league_leader_accuracy"),
        attention=attention,
    )
    return s.WeekOut(
        season=season,
        week=week,
        summary=summary,
        games=items,
        freshness=[s.DatasetFreshness(**f) for f in freshness(session, now)],
        generated_at=now,
    )


def _form(session: Session, g: Game, side: str, recs: list[Game], pred: Prediction | None) -> s.TeamForm:
    team = getattr(g, f"{side}_team")
    past = [x for x in recs if x.kickoff_utc < g.kickoff_utc]

    def margin(x: Game) -> int:
        return (x.home_score - x.away_score) * (1 if x.home_team == team else -1)

    def scored(x: Game) -> tuple[int, int]:
        return (x.home_score, x.away_score) if x.home_team == team else (x.away_score, x.home_score)

    pts = [scored(x) for x in past]
    feats = pred.features if pred else {}
    return s.TeamForm(
        team=team,
        record=record_before(recs, team, g.kickoff_utc),
        home_record=record_before(recs, team, g.kickoff_utc, "home"),
        away_record=record_before(recs, team, g.kickoff_utc, "away"),
        points_for_pg=round(sum(p[0] for p in pts) / len(pts), 1) if pts else None,
        points_against_pg=round(sum(p[1] for p in pts) / len(pts), 1) if pts else None,
        last3_margin=round(sum(margin(x) for x in past[-3:]) / len(past[-3:]), 1) if past else None,
        last5_margin=round(sum(margin(x) for x in past[-5:]) / len(past[-5:]), 1) if past else None,
        elo=feats.get(f"{side}_elo"),
        qb=getattr(g, f"{side}_qb"),
        prev_qb=None,
        rest_days=getattr(g, f"{side}_rest"),
        coach=getattr(g, f"{side}_coach"),
    )


def game_detail(session: Session, game_id: str) -> s.GameDetail | None:
    g = session.get(Game, game_id)
    if g is None:
        return None
    now = now_utc()
    base = summaries(session, [g], now)[0]
    names = dict(session.execute(select(ModelVersion.id, ModelVersion.name)).all())
    history = session.scalars(select(Prediction).where(Prediction.game_id == game_id).order_by(Prediction.id)).all()
    last = history[-1] if history else None
    recs = _records(session, g.season, {g.home_team, g.away_team})
    injuries = _week_injuries(session, g.season, g.week, {g.home_team, g.away_team})
    markets = session.scalars(
        select(MarketSnapshot).where(MarketSnapshot.game_id == game_id).order_by(MarketSnapshot.observed_at)
    ).all()
    meetings = session.scalars(
        select(Game)
        .where(
            Game.status == "final",
            Game.kickoff_utc < g.kickoff_utc,
            or_(
                (Game.home_team == g.home_team) & (Game.away_team == g.away_team),
                (Game.home_team == g.away_team) & (Game.away_team == g.home_team),
            ),
        )
        .order_by(Game.kickoff_utc.desc())
        .limit(5)
    ).all()
    report = session.scalars(
        select(AIReport)
        .where(AIReport.game_id == game_id, AIReport.kind == "report")
        .order_by(AIReport.id.desc())
        .limit(1)
    ).first()
    home_form = _form(session, g, "home", recs[g.home_team], last)
    away_form = _form(session, g, "away", recs[g.away_team], last)
    if last:
        home_form.prev_qb = last.features.get("home_prev_qb")
        away_form.prev_qb = last.features.get("away_prev_qb")
    rank = {"Out": 0, "Doubtful": 1, "Questionable": 2}
    inj_rows = sorted(
        (r for team in (g.away_team, g.home_team) for r in injuries.get(team, [])),
        key=lambda r: (r.team != g.away_team, rank.get(r.report_status or "", 3), r.position or ""),
    )
    return s.GameDetail(
        **base.model_dump(),
        home_form=home_form,
        away_form=away_form,
        injuries=[s.InjuryOut.model_validate(r, from_attributes=True) for r in inj_rows],
        market_history=[
            s.MarketOut(
                observed_at=m.observed_at,
                kind=m.kind,
                source=m.source,
                home_moneyline=m.home_moneyline,
                away_moneyline=m.away_moneyline,
                spread_line=m.spread_line,
                total_line=m.total_line,
                home_prob=m.home_prob_novig,
            )
            for m in markets
        ],
        prediction_history=[prediction_out(p, names) for p in history],
        meetings=[s.MeetingOut.model_validate(m, from_attributes=True) for m in meetings],
        ai_report=ai_report_out(report) if report else None,
        coach_home=g.home_coach,
        coach_away=g.away_coach,
        surface=g.surface,
        weekday=g.weekday,
    )


def ai_report_out(r: AIReport) -> s.AIReportOut:
    return s.AIReportOut(
        id=r.id,
        created_at=r.created_at,
        provider=r.provider,
        model=r.model,
        status=r.status,
        report=s.MatchupReport.model_validate(r.report) if r.report else None,
        error=r.error,
        prediction_id=r.prediction_id,
    )


def _tally(correct: int, total: int) -> s.Tally:
    lo, hi = wilson_ci(correct, total)
    return s.Tally(correct=correct, total=total, accuracy=correct / total if total else None, ci_low=lo, ci_high=hi)


def performance(session: Session, season: int) -> s.PerformanceOut:
    games = session.scalars(
        select(Game)
        .where(Game.season == season, Game.game_type == "REG", Game.status == "final")
        .order_by(Game.kickoff_utc)
    ).all()
    ids = [g.game_id for g in games]
    picks = {p.game_id: p.picked_team for p in session.scalars(select(UserPick).where(UserPick.game_id.in_(ids)))}
    preds: dict[str, list[Prediction]] = defaultdict(list)
    for p in session.scalars(select(Prediction).where(Prediction.game_id.in_(ids)).order_by(Prediction.id)):
        preds[p.game_id].append(p)
    closing = _latest_by_game(session, MarketSnapshot, ids)

    weeks: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    probs, outcomes = [], []
    live = backfill = 0
    for g in games:
        win = winner(g)
        w = weeks[g.week]
        w["games_final"] += 1
        if win is None:
            continue
        if g.game_id in picks:
            w["my_total"] += 1
            w["my_correct"] += picks[g.game_id] == win
        valid = [p for p in preds[g.game_id] if p.created_at < g.kickoff_utc or p.kind == "backfill"]
        if valid:
            final, first = valid[-1], valid[0]
            w["model_total"] += 1
            w["model_correct"] += final.pick == win
            w["model_first_total"] += 1
            w["model_first_correct"] += first.pick == win
            probs.append(final.home_win_prob)
            outcomes.append(1.0 if win == g.home_team else 0.0)
            live += final.kind == "live"
            backfill += final.kind == "backfill"
        m = closing.get(g.game_id)
        if m and m.home_prob_novig is not None:
            w["market_total"] += 1
            w["market_correct"] += (g.home_team if m.home_prob_novig >= 0.5 else g.away_team) == win
        if not g.neutral_site:
            w["home_total"] += 1
            w["home_correct"] += g.home_team == win

    def total(key: str) -> s.Tally:
        return _tally(sum(w[f"{key}_correct"] for w in weeks.values()), sum(w[f"{key}_total"] for w in weeks.values()))

    keys = [
        "games_final",
        "my_correct",
        "my_total",
        "model_correct",
        "model_total",
        "model_first_correct",
        "model_first_total",
        "market_correct",
        "market_total",
        "home_correct",
        "home_total",
    ]
    return s.PerformanceOut(
        season=season,
        weeks=[s.WeekPerformance(week=wk, **{k: weeks[wk][k] for k in keys}) for wk in sorted(weeks)],
        me=total("my"),
        model=total("model"),
        model_first=total("model_first"),
        market=total("market"),
        home=total("home"),
        model_live_games=live,
        model_backfill_games=backfill,
        calibration=calibration(np.array(probs), np.array(outcomes)) if probs else [],
        league_leader_accuracy=get_setting(session, "league_leader_accuracy"),
    )
