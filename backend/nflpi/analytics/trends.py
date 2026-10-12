"""Historical matchup and situation records for game context."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nflpi.analytics.play_callers import PLAY_CALLERS
from nflpi.models import Game

MIN_GAMES = 4
LAST_SEASONS = 5
type PlayCallers = tuple[tuple[str, int, str, str, int, str], ...]
type HomeSideMatchup = tuple[str, str, str | None]
type HomeSideContext = tuple[Game, PlayCallers, str | None, set[str]]


def _caller_on_file(play_callers: PlayCallers, team: str, season: int, week: int, side: str) -> str | None:
    row = max(
        (row for row in play_callers if row[0] == team and row[1] == season and row[2] == side and row[4] <= week),
        key=lambda row: row[4],
        default=None,
    )
    return row[3] if row else None


def _record(games: list[tuple[Game, bool]], row: tuple[str, str, str | None, str, str]) -> dict:
    wins = losses = ties = 0
    for g, home_side in games:
        own, other = (g.home_score, g.away_score) if home_side else (g.away_score, g.home_score)
        if own == other:
            ties += 1
        elif own > other:
            wins += 1
        else:
            losses += 1
    return {
        "kind": row[0], "team": row[1], "person": row[2], "context": row[3], "window": row[4],
        "wins": wins, "losses": losses, "ties": ties, "games": len(games),
        "first_season": min(g.season for g, _ in games), "last_season": max(g.season for g, _ in games),
    }


def _load_games(session: Session, target: Game, prefix: str | None) -> tuple[list[Game], set[str]]:
    historical = (
        Game.status == "final",
        Game.home_score.is_not(None),
        Game.away_score.is_not(None),
        Game.kickoff_utc < target.kickoff_utc,
    )
    teams = (target.home_team, target.away_team)
    games = session.scalars(
        select(Game).where(
            *historical,
            or_(Game.home_team.in_(teams), Game.away_team.in_(teams)),
        )
    ).all()
    sites: set[str] = set()
    if prefix:
        sites = set(session.scalars(
            select(Game.stadium).distinct().where(
                *historical,
                Game.neutral_site.is_(True),
                Game.stadium_id.startswith(prefix, autoescape=True),
                Game.stadium.is_not(None),
            )
        ).all())
    if target.stadium:
        sites.add(target.stadium)
    return games, sites


def _home_side(
    game: Game, kind: str, matchup: HomeSideMatchup, shared: HomeSideContext
) -> bool | None:
    team, opponent, person = matchup
    target, play_callers, prefix, sites = shared
    home = game.home_team == team
    away = game.away_team == team
    if kind == "team_vs_team":
        if home and game.away_team == opponent:
            return True
        if away and game.home_team == opponent:
            return False
        return None
    if kind in ("qb_vs_team", "coach_vs_team"):
        field = "qb" if kind == "qb_vs_team" else "coach"
        if game.away_team == opponent and getattr(game, f"home_{field}") == person:
            return True
        if game.home_team == opponent and getattr(game, f"away_{field}") == person:
            return False
        return None
    if kind in ("off_caller_vs_team", "def_caller_vs_team"):
        caller_side = "off" if kind == "off_caller_vs_team" else "def"
        if game.away_team == opponent and _caller_on_file(
            play_callers, game.home_team, game.season, game.week, caller_side
        ) == person:
            return True
        if game.home_team == opponent and _caller_on_file(
            play_callers, game.away_team, game.season, game.week, caller_side
        ) == person:
            return False
        return None
    if not (home or away):
        return None
    if kind == "team_at_stadium":
        if game.stadium_id != target.stadium_id:
            return None
        return home
    if kind == "team_at_site":
        qualifies = game.neutral_site and (
            (game.stadium_id and game.stadium_id.startswith(prefix or "")) or game.stadium in sites
        )
        if not qualifies:
            return None
        return home
    if game.weekday == target.weekday:
        return home
    return None


def _trend_rows(
    target: Game, games: list[Game], play_callers: PlayCallers, prefix: str | None, sites: set[str]
) -> list[dict]:
    rows = []
    shared: HomeSideContext = (target, play_callers, prefix, sites)
    for team, opponent, qb, coach in (
        (target.home_team, target.away_team, target.home_qb, target.home_coach),
        (target.away_team, target.home_team, target.away_qb, target.away_coach),
    ):
        kinds = [("team_vs_team", None, opponent), ("team_on_weekday", None, target.weekday)]
        if qb:
            kinds.append(("qb_vs_team", qb, opponent))
        if coach:
            kinds.append(("coach_vs_team", coach, opponent))
        for side in ("off", "def"):
            caller = _caller_on_file(play_callers, team, target.season, target.week, side)
            if caller:
                kinds.append((f"{side}_caller_vs_team", caller, opponent))
        if target.stadium_id:
            kinds.append(("team_at_stadium", None, target.stadium))
        if prefix:
            kinds.append(("team_at_site", None, ", ".join(sorted(sites))))
        for kind, person, context in kinds:
            matchup = (team, opponent, person)
            matched = [
                (game, side) for game in games
                if (side := _home_side(game, kind, matchup, shared)) is not None
            ]
            windows = (
                ("all", matched),
                (
                    "last_5_seasons",
                    [pair for pair in matched if target.season - LAST_SEASONS <= pair[0].season < target.season],
                ),
            )
            for window, selected in windows:
                if len(selected) >= MIN_GAMES:
                    rows.append(_record(selected, (kind, team, person, context, window)))
    return rows


def game_trends(session: Session, game_id: str, play_callers: PlayCallers = PLAY_CALLERS) -> list[dict]:
    """Return established records from final games before this kickoff."""
    target = session.get(Game, game_id)
    if target is None:
        raise LookupError(game_id)
    prefix = target.stadium_id[:3] if target.neutral_site and target.stadium_id else None
    games, sites = _load_games(session, target, prefix)
    return _trend_rows(target, games, play_callers, prefix, sites)
