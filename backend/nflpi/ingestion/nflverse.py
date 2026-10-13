"""nflverse adapter: download release CSVs and normalize them into plain dicts.

Docs: https://github.com/nflverse/nflverse-data (mostly CC-BY 4.0).
`gametime` in games.csv is US Eastern time.
"""

import csv
import io
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from nflpi.config import get_settings

SOURCE = "nflverse"
EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Old franchise codes -> current code, so ratings carry across relocations.
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}


def franchise(abbr: str) -> str:
    return FRANCHISE.get(abbr, abbr)


def fetch_csv(path: str) -> list[dict[str, str]]:
    """Download a release asset with retries. Raises on final failure."""
    settings = get_settings()
    url = f"{settings.nflverse_base}/{path}"
    last_error: Exception | None = None
    for attempt in range(settings.http_retries):
        try:
            resp = httpx.get(url, timeout=settings.http_timeout_s, follow_redirects=True)
            resp.raise_for_status()
            return list(csv.DictReader(io.StringIO(resp.text)))
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"nflverse download failed for {path}: {last_error}")


def _num(value: str) -> float | None:
    return float(value) if value not in ("", "NA", None) else None


def _int(value: str) -> int | None:
    return int(float(value)) if value not in ("", "NA", None) else None


def _no_clock_time(value: str | None) -> bool:
    return value in ("", "NA", None)


def kickoff_utc(gameday: str, gametime: str) -> datetime:
    # A missing clock time is represented by midnight at the start of the Eastern game day.
    hh, mm = ("00:00" if _no_clock_time(gametime) else gametime).split(":")[:2]
    local = datetime.fromisoformat(gameday).replace(hour=int(hh), minute=int(mm), tzinfo=EASTERN)
    return local.astimezone(UTC)


def parse_games(rows: list[dict[str, str]], min_season: int) -> list[dict]:
    games = []
    for r in rows:
        season = int(r["season"])
        if season < min_season:
            continue
        final = r["home_score"] not in ("", "NA")
        games.append(
            {
                "game_id": r["game_id"],
                "season": season,
                "week": int(r["week"]),
                "game_type": r["game_type"],
                "kickoff_utc": kickoff_utc(r["gameday"], r["gametime"]),
                "time_tbd": _no_clock_time(r["gametime"]),
                "weekday": r["weekday"],
                "away_team": franchise(r["away_team"]),
                "home_team": franchise(r["home_team"]),
                "away_score": _int(r["away_score"]),
                "home_score": _int(r["home_score"]),
                "status": "final" if final else "scheduled",
                "neutral_site": r["location"] == "Neutral",
                "div_game": r["div_game"] == "1",
                "roof": r["roof"] or None,
                "surface": r["surface"] or None,
                "stadium": r["stadium"] or None,
                "stadium_id": r["stadium_id"] or None,
                "away_rest": _int(r["away_rest"]),
                "home_rest": _int(r["home_rest"]),
                "away_qb": r["away_qb_name"] or None,
                "home_qb": r["home_qb_name"] or None,
                "away_coach": r["away_coach"] or None,
                "home_coach": r["home_coach"] or None,
                "temp_f": _num(r["temp"]),
                "wind_mph": _num(r["wind"]),
                "source": SOURCE,
                # market fields, split off by the caller
                "_home_ml": _num(r["home_moneyline"]),
                "_away_ml": _num(r["away_moneyline"]),
                "_spread": _num(r["spread_line"]),
                "_total": _num(r["total_line"]),
            }
        )
    return games


def parse_teams(rows: list[dict[str, str]], current: set[str]) -> list[dict]:
    return [
        {
            "abbr": r["team_abbr"],
            "name": r["team_name"],
            "nick": r["team_nick"],
            "conference": r["team_conf"],
            "division": r["team_division"],
            "color": r["team_color"],
            "color2": r["team_color2"],
            "logo_url": r["team_logo_espn"],
        }
        for r in rows
        if r["team_abbr"] in current
    ]


def parse_injuries(rows: list[dict[str, str]], observed_at: datetime) -> list[dict]:
    out = []
    for r in rows:
        if r.get("game_type", "REG") not in ("REG", "WC", "DIV", "CON", "SB"):
            continue
        status = r["report_status"] or None
        practice = r["practice_status"] or None
        if not status and not practice:
            continue
        out.append(
            {
                "season": int(r["season"]),
                "week": int(r["week"]),
                "team": franchise(r["team"]),
                "player_id": r["gsis_id"] or None,
                "player": r["full_name"],
                "position": r["position"] or None,
                "report_status": status,
                "practice_status": practice,
                "injury": r["report_primary_injury"] or r["practice_primary_injury"] or None,
                "source": SOURCE,
                "observed_at": observed_at,
            }
        )
    return out


STAR_STATS = (
    "attempts",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "def_tackles_solo",
    "def_tackles_with_assist",
    "def_tackle_assists",
    "def_tackles_for_loss",
    "def_fumbles_forced",
    "def_sacks",
    "def_qb_hits",
    "def_interceptions",
    "def_pass_defended",
    "def_tds",
    "def_safeties",
)
MIN_STAR_WEEK = 1
MAX_STAR_WEEK = 22
MAX_STAR_CLUB_LENGTH = 4
MAX_STAR_SNAP_COUNT = 300
MAX_STAR_STAT_ABS = 1000
MAX_STAR_ERROR_VALUE_LENGTH = 40


def _star_int(value: str, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {label}: {str(value)[:MAX_STAR_ERROR_VALUE_LENGTH]}") from exc


def _star_week(value: str) -> int:
    week = _star_int(value, "week")
    if not MIN_STAR_WEEK <= week <= MAX_STAR_WEEK:
        raise ValueError(f"week outside {MIN_STAR_WEEK}..{MAX_STAR_WEEK}: {str(value)[:MAX_STAR_ERROR_VALUE_LENGTH]}")
    return week


def _star_club(value: str) -> str:
    team = franchise(value.strip())
    if not team or len(team) > MAX_STAR_CLUB_LENGTH:
        raise ValueError(f"invalid club: {str(value)[:MAX_STAR_ERROR_VALUE_LENGTH]}")
    return team


def _star_number(value: str) -> float:
    try:
        number = 0.0 if value in ("", "NA") else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid star statistic: {str(value)[:MAX_STAR_ERROR_VALUE_LENGTH]}") from exc
    if not math.isfinite(number) or abs(number) > MAX_STAR_STAT_ABS:
        raise ValueError(f"invalid star statistic: {str(value)[:MAX_STAR_ERROR_VALUE_LENGTH]}")
    return number


def _star_id(value: str) -> str | None:
    value = value.strip()
    if len(value) > 16:
        raise ValueError("league id is longer than 16 characters")
    return value or None


def parse_star_snaps(rows: list[dict[str, str]], season: int) -> list[dict]:
    out = []
    seen = set()
    for row in rows:
        if _star_int(row["season"], "season") != season:
            continue
        week, team = _star_week(row["week"]), _star_club(row["team"])
        pfr_id = row["pfr_player_id"].strip()
        if not pfr_id:
            raise ValueError("blank pfr_player_id")
        key = (pfr_id, week, team)
        if key in seen:
            raise ValueError("duplicate snap row")
        seen.add(key)
        off = _star_int(row["offense_snaps"], "offense_snaps")
        de = _star_int(row["defense_snaps"], "defense_snaps")
        if not 0 <= off <= MAX_STAR_SNAP_COUNT or not 0 <= de <= MAX_STAR_SNAP_COUNT:
            raise ValueError("snap count outside allowed range")
        out.append(
            {
                "week": week,
                "team": team,
                "pfr_id": pfr_id,
                "player": row["player"].strip()[:64],
                "position": row["position"].strip()[:8] or None,
                "offense_snaps": off,
                "defense_snaps": de,
            }
        )
    return out


def parse_star_stats(rows: list[dict[str, str]], season: int) -> list[dict]:
    out = []
    seen = set()
    for row in rows:
        if _star_int(row["season"], "season") != season:
            continue
        week, team = _star_week(row["week"]), _star_club(row["team"])
        player_id = _star_id(row["player_id"])
        if not player_id:
            continue
        key = (player_id, week, team)
        if key in seen:
            raise ValueError("duplicate stat row")
        seen.add(key)
        record = {
            "week": week,
            "team": team,
            "player_id": player_id,
            "player": row["player_display_name"].strip()[:64],
            "position": row["position"].strip()[:8] or None,
        }
        record.update({name: _star_number(row[name]) for name in STAR_STATS})
        out.append(record)
    return out


def parse_star_players(rows: list[dict[str, str]]) -> dict[str, str]:
    ids = {}
    for row in rows:
        pfr = row["pfr_id"].strip()
        gsis = _star_id(row["gsis_id"])
        if pfr and gsis:
            ids[pfr] = gsis
    return ids
