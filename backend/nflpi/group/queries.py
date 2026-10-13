"""Read group pick shares and weekly standings."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi.models import Game, GroupPick, GroupStanding


def _side_share(team: str, picks: list[tuple[str | None, int | None]], picked: int) -> dict:
    confidence = [value for chosen, value in picks if chosen == team and value is not None]
    count = sum(chosen == team for chosen, _ in picks)
    return {"team": team, "picks": count, "share": count / picked if picked else None,
            "avg_confidence": sum(confidence) / len(confidence) if confidence else None}


def game_shares(session: Session, game_id: str) -> dict:
    """Count picks and confidence for each side of one game."""
    game = session.get(Game, game_id)
    if game is None:
        raise LookupError("game not found")
    picks = [tuple(row) for row in session.execute(
        select(GroupPick.picked_team, GroupPick.confidence).where(GroupPick.game_id == game_id)
    )]
    picked = sum(team is not None for team, _ in picks)
    sides = {}
    for side, team in (("away", game.away_team), ("home", game.home_team)):
        sides[side] = _side_share(team, picks, picked)
    return {"game_id": game_id, "members": len(picks), "picked": picked, **sides}


def week_shares(session: Session, season: int, week: int) -> list[dict]:
    """Show every game of a week with its group pick shares."""
    games = list(session.scalars(select(Game).where(
        Game.season == season, Game.week == week
    ).order_by(Game.kickoff_utc, Game.game_id)))
    game_ids = [game.game_id for game in games]
    if not game_ids:
        return []
    picks_by_game: dict[str, list[tuple[str | None, int | None]]] = {game_id: [] for game_id in game_ids}
    for game_id, team, confidence in session.execute(select(
        GroupPick.game_id, GroupPick.picked_team, GroupPick.confidence
    ).where(GroupPick.game_id.in_(game_ids))):
        picks_by_game[game_id].append((team, confidence))
    rows = []
    for game in games:
        picks = picks_by_game[game.game_id]
        picked = sum(team is not None for team, _ in picks)
        rows.append({"game_id": game.game_id, "away_team": game.away_team, "home_team": game.home_team,
                     "kickoff_utc": game.kickoff_utc, "members": len(picks), "picked": picked,
                     "away": _side_share(game.away_team, picks, picked),
                     "home": _side_share(game.home_team, picks, picked)})
    return rows


def standings(session: Session, season: int, week: int) -> list[dict]:
    """Show that week's points with each member's running total."""
    rows = session.scalars(select(GroupStanding).where(
        GroupStanding.season == season, GroupStanding.week <= week
    ))
    by_member: dict[str, dict] = {}
    for row in rows:
        entry = by_member.setdefault(row.member, {"member": row.member, "points": None, "total": 0, "rank": None})
        entry["total"] += row.points
        if row.week == week:
            entry["points"] = row.points
            entry["rank"] = row.rank
    current = [entry for entry in by_member.values() if entry["points"] is not None]
    return sorted(current, key=lambda entry: (-entry["total"], entry["rank"] if entry["rank"] is not None
                                              else float("inf"), entry["member"].casefold(), entry["member"]))


def standing_weeks(session: Session, season: int, week: int) -> list[int]:
    """Weeks up to this one that have standings rows."""
    return list(session.scalars(select(GroupStanding.week).where(
        GroupStanding.season == season, GroupStanding.week <= week
    ).distinct().order_by(GroupStanding.week)))
