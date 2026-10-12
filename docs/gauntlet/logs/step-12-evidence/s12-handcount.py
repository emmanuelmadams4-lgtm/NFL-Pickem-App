"""Step 12 gate T9: the app's trend counts against an independent count on the real nflverse schedule file.

Run from backend/ (throwaway database only, never the live one):
  DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15437/nflpi_evidence \
    uv run python ../docs/gauntlet/logs/step-12-evidence/s12-handcount.py <games.csv>

The independent count below reads the CSV directly and shares no code with nflpi.analytics.trends.
"""

import csv
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nflpi.analytics.trends import MIN_GAMES, game_trends
from nflpi.config import get_settings
from nflpi.db import Base, get_engine, session_factory
from nflpi.ingestion import service

OLD_CODES = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}


def load(path: str) -> list[dict]:
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if int(r["season"]) >= get_settings().first_season]
    for r in rows:
        for side in ("home_team", "away_team"):
            r[side] = OLD_CODES.get(r[side], r[side])
        r["when"] = (r["gameday"], r["gametime"])
        r["final"] = r["home_score"] not in ("", "NA")
    return rows


def hand(rows: list[dict], target: dict, side_of, last5: bool) -> tuple | None:
    """side_of(row) -> 'home' | 'away' | None: which side of that game the record belongs to."""
    w = l = t = 0
    seasons = []
    for r in rows:
        if not r["final"] or r["when"] >= target["when"]:
            continue
        season = int(r["season"])
        if last5 and not (int(target["season"]) - 5 <= season <= int(target["season"]) - 1):
            continue
        side = side_of(r)
        if side is None:
            continue
        margin = (int(r["home_score"]) - int(r["away_score"])) * (1 if side == "home" else -1)
        w, l, t = w + (margin > 0), l + (margin < 0), t + (margin == 0)
        seasons.append(season)
    n = w + l + t
    return (w, l, t, n, min(seasons), max(seasons)) if n >= MIN_GAMES else None


def team_side(team: str, keep):
    def side_of(r: dict) -> str | None:
        if not keep(r):
            return None
        return "home" if r["home_team"] == team else "away" if r["away_team"] == team else None

    return side_of


def person_side(field: str, name: str, opponent: str):
    def side_of(r: dict) -> str | None:
        if r[f"home_{field}"] == name and r["away_team"] == opponent:
            return "home"
        if r[f"away_{field}"] == name and r["home_team"] == opponent:
            return "away"
        return None

    return side_of


def latest(rows: list[dict], keep) -> dict:
    return max((r for r in rows if keep(r)), key=lambda r: r["when"])


def main(path: str) -> int:
    url = make_url(get_settings().database_url)
    assert url.port != 5432 and url.database == "nflpi_evidence", "throwaway database only"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text('drop database if exists "nflpi_evidence"'))
        c.execute(text('create database "nflpi_evidence"'))
    Base.metadata.create_all(get_engine())
    with open(path, newline="") as f:
        raw = list(csv.DictReader(f))
    rows = load(path)
    london = {"Wembley Stadium", "Twickenham Stadium", "Tottenham Stadium", "Tottenham Hotspur Stadium"}
    plays = lambda r, a, b: {r["home_team"], r["away_team"]} == {a, b}  # noqa: E731

    jax = latest(rows, lambda r: "JAX" in (r["home_team"], r["away_team"]) and r["stadium"] in london)
    kc_lv = latest(rows, lambda r: plays(r, "KC", "LV"))
    kc_den = latest(rows, lambda r: plays(r, "KC", "DEN") and "Patrick Mahomes" in (r["home_qb_name"], r["away_qb_name"]))
    dal = latest(rows, lambda r: "DAL" in (r["home_team"], r["away_team"]) and r["weekday"] == "Thursday")
    gb = latest(rows, lambda r: r["home_team"] == "GB" and r["stadium_id"] == "GNB00")
    examples = [
        ("Jaguars in London", jax, "team_at_site", "JAX", None, team_side("JAX", lambda r: r["stadium"] in london)),
        ("Chiefs vs Raiders", kc_lv, "team_vs_team", "KC", None, team_side("KC", lambda r: plays(r, "KC", "LV"))),
        (
            "Mahomes vs Broncos", kc_den, "qb_vs_team", "KC", "Patrick Mahomes",
            person_side("qb_name", "Patrick Mahomes", "DEN"),
        ),
        ("Andy Reid vs Broncos", kc_den, "coach_vs_team", "KC", "Andy Reid", person_side("coach", "Andy Reid", "DEN")),
        ("Cowboys on Thursday", dal, "team_on_weekday", "DAL", None, team_side("DAL", lambda r: r["weekday"] == "Thursday")),
        ("Packers at Lambeau", gb, "team_at_stadium", "GB", None, team_side("GB", lambda r: r["stadium_id"] == "GNB00")),
    ]
    bad = 0
    with session_factory()() as session:
        service.ingest_schedules(session, raw)
        print(f"finished games in file from {get_settings().first_season}: {sum(r['final'] for r in rows)}")
        for label, target, kind, team, person, side_of in examples:
            app_rows = game_trends(session, target["game_id"])
            for window, last5 in (("all", False), ("last_5_seasons", True)):
                got = [r for r in app_rows if (r["kind"], r["team"], r["person"], r["window"]) == (kind, team, person, window)]
                app = None if not got else tuple(got[0][k] for k in ("wins", "losses", "ties", "games", "first_season", "last_season"))
                mine = hand(rows, target, side_of, last5)
                ok = app == mine and len(got) <= 1
                bad += not ok
                print(f"{'MATCH' if ok else 'DIFF '} {label} [{target['game_id']}] {window}: app={app} hand={mine}")
        tuesday = [r for r in rows if r["final"] and r["weekday"] == "Tuesday"]
        cle = [r for r in tuesday if "CLE" in (r["home_team"], r["away_team"])]
        print(f"Browns on Tuesday: {len(cle)} games in the file ({len(tuesday)} Tuesday games in all): no record to show")
        bad += len(cle) != 0
    print("RESULT:", "PASS" if not bad else f"FAIL ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
