"""Historical matchup and situation records for game context."""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from nflpi.models import Game

MIN_GAMES = 8
LAST_SEASONS = 5


def _matches(g: Game, kind: str, team: str, opponent: str, person: str | None, target: Game, sites: set[str]) -> bool:
    team_home = g.home_team == team
    team_away = g.away_team == team
    if kind == "team_vs_team":
        return (team_home and g.away_team == opponent) or (team_away and g.home_team == opponent)
    if kind in ("qb_vs_team", "coach_vs_team"):
        field = "qb" if kind == "qb_vs_team" else "coach"
        return (g.away_team == opponent and getattr(g, f"home_{field}") == person) or (
            g.home_team == opponent and getattr(g, f"away_{field}") == person
        )
    if not (team_home or team_away):
        return False
    if kind == "team_at_stadium":
        return g.stadium_id == target.stadium_id
    if kind == "team_at_site":
        return (g.stadium_id is not None and g.stadium_id.startswith(target.stadium_id[:3])) or g.stadium in sites
    return g.weekday == target.weekday


def _record(games: list[Game], kind: str, team: str, person: str | None, context: str, window: str) -> dict:
    wins = losses = ties = 0
    for g in games:
        home_side = (g.home_qb if kind == "qb_vs_team" else g.home_coach) == person if kind in (
            "qb_vs_team", "coach_vs_team"
        ) else g.home_team == team
        own, other = (g.home_score, g.away_score) if home_side else (g.away_score, g.home_score)
        if own == other:
            ties += 1
        elif own > other:
            wins += 1
        else:
            losses += 1
    return {
        "kind": kind, "team": team, "person": person, "context": context, "window": window,
        "wins": wins, "losses": losses, "ties": ties, "games": len(games),
        "first_season": min(g.season for g in games), "last_season": max(g.season for g in games),
    }


def game_trends(session: Session, game_id: str) -> list[dict]:
    """Return established records from final games before this kickoff."""
    target = session.get(Game, game_id)
    if target is None:
        raise LookupError(game_id)
    historical = and_(Game.status == "final", Game.kickoff_utc < target.kickoff_utc)
    prefix = target.stadium_id[:3] if target.neutral_site and target.stadium_id else None
    condition = or_(historical, Game.stadium_id.startswith(prefix)) if prefix else historical
    candidates = session.scalars(select(Game).where(condition)).all()
    games = [g for g in candidates if g.status == "final" and g.kickoff_utc < target.kickoff_utc]
    sites = {g.stadium for g in candidates if prefix and g.stadium_id and g.stadium_id.startswith(prefix) and g.stadium}
    if target.stadium:
        sites.add(target.stadium)

    rows = []
    for team, opponent, qb, coach in (
        (target.home_team, target.away_team, target.home_qb, target.home_coach),
        (target.away_team, target.home_team, target.away_qb, target.away_coach),
    ):
        kinds = [("team_vs_team", None, opponent), ("team_on_weekday", None, target.weekday)]
        if qb is not None:
            kinds.append(("qb_vs_team", qb, opponent))
        if coach is not None:
            kinds.append(("coach_vs_team", coach, opponent))
        if target.stadium_id is not None:
            kinds.append(("team_at_stadium", None, target.stadium))
        if prefix:
            kinds.append(("team_at_site", None, ", ".join(sorted(sites))))
        for kind, person, context in kinds:
            matched = [g for g in games if _matches(g, kind, team, opponent, person, target, sites)]
            for window, selected in (
                ("all", matched),
                ("last_5_seasons", [g for g in matched if target.season - LAST_SEASONS <= g.season < target.season]),
            ):
                if len(selected) >= MIN_GAMES:
                    rows.append(_record(selected, kind, team, person, context, window))
    return rows
