"""Data timing report: python -m nflpi.analytics.timing <season> <week>"""

import json
import statistics
import sys
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.db import session_factory
from nflpi.models import Game, InjuryReport, MarketSnapshot, QbObservation

SIDES = ("home", "away")


def game_timing(session: Session, game_id: str) -> dict:
    """When the line, each club's quarterback and each injury row were first seen and last changed."""
    game = session.get(Game, game_id)
    if game is None:
        raise LookupError(game_id)
    first, last = session.execute(
        select(func.min(MarketSnapshot.observed_at), func.max(MarketSnapshot.observed_at)).where(
            MarketSnapshot.game_id == game_id
        )
    ).one()
    out: dict = {"line": {"first_seen": first, "last_changed": last}}
    for side in SIDES:
        named, latest = session.execute(
            select(
                func.min(QbObservation.observed_at).filter(QbObservation.qb.is_not(None)),
                func.max(QbObservation.observed_at),
            ).where(QbObservation.game_id == game_id, QbObservation.side == side)
        ).one()
        out[f"{side}_qb"] = {"first_seen": named, "last_changed": latest}
    key = func.coalesce(InjuryReport.player_id, InjuryReport.player)
    rows = session.execute(
        select(
            InjuryReport.team,
            key,
            func.min(InjuryReport.observed_at),
            func.max(InjuryReport.observed_at),
        )
        .where(
            InjuryReport.season == game.season,
            InjuryReport.week == game.week,
            InjuryReport.team.in_([game.home_team, game.away_team]),
        )
        .group_by(InjuryReport.team, key)
    )
    out["injuries"] = {(team, who): {"first_seen": lo, "last_changed": hi} for team, who, lo, hi in rows}
    return out


def week_report(session: Session, season: int, week: int) -> dict:
    """Line age and quarterback gaps per game, counting only rows seen before kickoff (no hindsight)."""
    games = session.scalars(
        select(Game).where(Game.season == season, Game.week == week).order_by(Game.kickoff_utc, Game.game_id)
    ).all()
    ids = [g.game_id for g in games]
    kickoff = {g.game_id: g.kickoff_utc for g in games}
    last_snap: dict[str, datetime] = dict(
        session.execute(
            select(MarketSnapshot.game_id, func.max(MarketSnapshot.observed_at))
            .join(Game, Game.game_id == MarketSnapshot.game_id)
            .where(MarketSnapshot.game_id.in_(ids), MarketSnapshot.observed_at < Game.kickoff_utc)
            .group_by(MarketSnapshot.game_id)
        ).all()
    )
    pregame_qb: dict[tuple[str, str], str | None] = {}
    for obs in session.scalars(
        select(QbObservation)
        .join(Game, Game.game_id == QbObservation.game_id)
        .where(QbObservation.game_id.in_(ids), QbObservation.observed_at < Game.kickoff_utc)
        .order_by(QbObservation.id)
    ):
        pregame_qb[(obs.game_id, obs.side)] = obs.qb or None  # later ids overwrite earlier: newest pregame wins
    rows = []
    for g in games:
        seen = last_snap.get(g.game_id)
        age = round((kickoff[g.game_id] - seen).total_seconds() / 3600, 2) if seen else None
        home, away = pregame_qb.get((g.game_id, "home")), pregame_qb.get((g.game_id, "away"))
        rows.append(
            {
                "game_id": g.game_id,
                "kickoff_utc": g.kickoff_utc,
                "line_age_hours": age,
                "home_qb": home,
                "away_qb": away,
                "qb_blank": home is None or away is None,
            }
        )
    ages = [r["line_age_hours"] for r in rows if r["line_age_hours"] is not None]
    return {
        "season": season,
        "week": week,
        "games": rows,
        "median_line_age_hours": statistics.median(ages) if ages else None,
        "games_with_line": len(ages),
        "blank_qb_games": sum(r["qb_blank"] for r in rows),
        "blank_qb_slots": sum((r["home_qb"] is None) + (r["away_qb"] is None) for r in rows),
    }


if __name__ == "__main__":
    with session_factory()() as db:
        print(json.dumps(week_report(db, int(sys.argv[1]), int(sys.argv[2])), default=str, indent=2))
