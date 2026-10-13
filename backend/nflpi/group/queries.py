"""Read group pick shares and weekly standings."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi.models import Game, GroupPick, GroupStanding


def game_shares(session: Session, game_id: str) -> dict:
    """Count picks and confidence for each side of one game."""
    game = session.get(Game, game_id)
    if game is None:
        raise LookupError("game not found")
    picks = list(session.execute(
        select(GroupPick.picked_team, GroupPick.confidence).where(GroupPick.game_id == game_id)
    ))
    picked = sum(team is not None for team, _ in picks)
    sides = {}
    for side, team in (("away", game.away_team), ("home", game.home_team)):
        confidence = [value for chosen, value in picks if chosen == team and value is not None]
        count = sum(chosen == team for chosen, _ in picks)
        sides[side] = {"team": team, "picks": count, "share": count / picked if picked else None,
                       "avg_confidence": sum(confidence) / len(confidence) if confidence else None}
    return {"game_id": game_id, "members": len(picks), "picked": picked, **sides}


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
                                              else float("inf"), entry["member"]))
