"""Tie news items to teams and players in step 8e."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.ingestion.news.parse import clean_text
from nflpi.models import Team, TeamStar


@dataclass(frozen=True)
class Tie:
    team_ids: list[str]
    player_ids: list[str]
    tags: list[str]


@dataclass(frozen=True)
class Names:
    teams: re.Pattern[str] | None
    team_ids: dict[str, set[str]]
    players: re.Pattern[str] | None
    player_ids: dict[str, str]
    clubs: dict[str, str]


def _pattern(phrases: Mapping[str, object]) -> re.Pattern[str] | None:
    if not phrases:
        return None
    choices = sorted(phrases, key=lambda phrase: (-len(phrase), phrase))
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(phrase) for phrase in choices) + r")(?!\w)", re.I)


def load_names(session: Session) -> Names:
    team_ids: dict[str, set[str]] = {}
    for abbr, name, nick in session.execute(select(Team.abbr, Team.name, Team.nick)):
        for phrase in (name, nick):
            if phrase:
                team_ids.setdefault(phrase.casefold(), set()).add(abbr)

    season = session.scalar(select(func.max(TeamStar.season)))
    player_ids: dict[str, set[str]] = {}
    latest_clubs: dict[str, tuple[int, str]] = {}
    if season is not None:
        stars = session.execute(
            select(TeamStar.player_id, TeamStar.player, TeamStar.team, TeamStar.week)
            .where(TeamStar.season == season, TeamStar.player_id.is_not(None))
        )
        for player_id, player, team, week in stars:
            phrase = clean_text(player, 64).casefold()
            if phrase:
                player_ids.setdefault(phrase, set()).add(player_id)
            if player_id not in latest_clubs or week > latest_clubs[player_id][0]:
                latest_clubs[player_id] = (week, team)

    unique_players = {phrase: next(iter(ids)) for phrase, ids in player_ids.items() if len(ids) == 1}
    return Names(
        teams=_pattern(team_ids),
        team_ids=team_ids,
        players=_pattern(unique_players),
        player_ids=unique_players,
        clubs={player_id: team for player_id, (_, team) in latest_clubs.items()},
    )


_TAGS = {
    "injury": re.compile(r"\binjur(?:y|ies|ed)\b|\bruled out\b|\bquestionable\b|\bdoubtful\b", re.I),
    "trade": re.compile(r"\btrad(?:e|es|ed|ing)\b", re.I),
    "coach": re.compile(r"\b(?:coach|coaches|coaching|coordinator|fired|fires|firing|hired|hires|hiring)\b", re.I),
    "playcaller": re.compile(r"\bplay[- ]?call(?:er|ers|ing)\b|\bcalling (?:the )?plays\b", re.I),
}


def tie(title: str, extract: str, names: Names) -> Tie:
    text = f"{title} {extract}"
    teams: set[str] = set()
    players: set[str] = set()
    if names.teams:
        for hit in names.teams.finditer(text):
            teams.update(names.team_ids[hit.group().casefold()])
    if names.players:
        for hit in names.players.finditer(text):
            player_id = names.player_ids[hit.group().casefold()]
            players.add(player_id)
            teams.add(names.clubs[player_id])
    return Tie(sorted(teams), sorted(players), sorted(tag for tag, pattern in _TAGS.items() if pattern.search(text)))
