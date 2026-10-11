"""nflverse adapter: download release CSVs and normalize them into plain dicts.

Docs: https://github.com/nflverse/nflverse-data (mostly CC-BY 4.0).
`gametime` in games.csv is US Eastern time.
"""

import csv
import io
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


def kickoff_utc(gameday: str, gametime: str) -> datetime:
    # A few 1999-era rows have no time; 13:00 ET is the safe default for those.
    hh, mm = (gametime or "13:00").split(":")[:2]
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
