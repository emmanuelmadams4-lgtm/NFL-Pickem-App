"""Validate the small part of ESPN replies used by live ingestion."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event="
_ID = re.compile(r"[0-9]{1,12}")
_PLAY_ID = re.compile(r"[0-9]{1,20}")
_SCORE = re.compile(r"[0-9]{1,3}")
_CLOCK = re.compile(r"[0-9]{1,2}:[0-9]{2}")
# Three unusable items suggest the whole reply changed format.
SHAPE_FAILURE_THRESHOLD = 3
TEAM_CODES = {
    code: code
    for code in (
        "ARI",
        "ATL",
        "BAL",
        "BUF",
        "CAR",
        "CHI",
        "CIN",
        "CLE",
        "DAL",
        "DEN",
        "DET",
        "GB",
        "HOU",
        "IND",
        "JAX",
        "KC",
        "LV",
        "LAC",
        "MIA",
        "MIN",
        "NE",
        "NO",
        "NYG",
        "NYJ",
        "PHI",
        "PIT",
        "SF",
        "SEA",
        "TB",
        "TEN",
        "LAR",
        "WSH",
    )
}
TEAM_CODES.update({"LAR": "LA", "WSH": "WAS"})


@dataclass(frozen=True)
class Event:
    event_id: str
    start: datetime
    state: str
    home_code: str
    away_code: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None


@dataclass(frozen=True)
class WinProb:
    home: float | None
    tie: float | None
    play_id: str | None


def summary_url(event_id: str) -> str:
    if not isinstance(event_id, str) or _ID.fullmatch(event_id) is None:
        raise ValueError("event id")
    return _SUMMARY_URL + event_id


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _score(value: Any) -> int | None:
    if not isinstance(value, str) or _SCORE.fullmatch(value) is None:
        return None
    number = int(value)
    return number if number <= 200 else None


def _competitors(value: Any) -> tuple[dict, dict] | None:
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, dict) for item in value):
        return None
    home = next((item for item in value if item.get("homeAway") == "home"), None)
    away = next((item for item in value if item.get("homeAway") == "away"), None)
    if home is None or away is None:
        return None
    for item in (home, away):
        team = item.get("team")
        if not isinstance(team, dict) or not isinstance(team.get("abbreviation"), str):
            return None
        if team["abbreviation"] not in TEAM_CODES:
            return None
    return home, away


def _event(item: Any) -> Event | None:
    if not isinstance(item, dict):
        return None
    event_id, start = item.get("id"), _date(item.get("date"))
    status = item.get("status")
    competitions = item.get("competitions")
    if not isinstance(status, dict) or not isinstance(competitions, list) or not competitions:
        return None
    competition = competitions[0]
    if not isinstance(competition, dict):
        return None
    pair = _competitors(competition.get("competitors"))
    status_type = status.get("type")
    state = status_type.get("state") if isinstance(status_type, dict) else None
    if not isinstance(event_id, str) or _ID.fullmatch(event_id) is None or start is None or pair is None:
        return None
    if state not in ("pre", "in", "post"):
        return None
    home, away = pair
    period, clock = status.get("period"), status.get("displayClock")
    period = period if type(period) is int and 1 <= period <= 10 else None
    clock = clock if isinstance(clock, str) and _CLOCK.fullmatch(clock) else None
    return Event(
        event_id,
        start,
        state,
        TEAM_CODES[home["team"]["abbreviation"]],
        TEAM_CODES[away["team"]["abbreviation"]],
        _score(home.get("score")),
        _score(away.get("score")),
        period,
        clock,
    )


def parse_scoreboard(data: Any) -> tuple[list[Event], int]:
    if not isinstance(data, dict) or not isinstance(data.get("events"), list) or len(data["events"]) > 40:
        raise ValueError("shape")
    items = data["events"]
    events = [_event(item) for item in items]
    usable = [event for event in events if event is not None]
    if len(items) >= SHAPE_FAILURE_THRESHOLD and not usable:
        raise ValueError("shape")
    return usable, sum(event is None for event in events)


def _probability(value: Any) -> float | None:
    if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
        return None
    return float(value)


def parse_win_probability(data: Any) -> WinProb | None:
    if not isinstance(data, dict):
        return None
    entries = data.get("winprobability")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 2000 or not isinstance(entries[-1], dict):
        return None
    last = entries[-1]
    play_id = last.get("playId")
    if not isinstance(play_id, str) or _PLAY_ID.fullmatch(play_id) is None:
        play_id = None
    return WinProb(_probability(last.get("homeWinPercentage")), _probability(last.get("tiePercentage")), play_id)
