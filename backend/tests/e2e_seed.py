"""Seed the browser-test database: the pytest fixture league, one game with no kickoff time, a weather outage,
and star players with this week's injury report (step 8a2).

Run by scripts/e2e-server.sh with DATABASE_URL pointing at a throwaway database (nflpi_e2e).
"""

from datetime import UTC, datetime, timedelta

from nflpi.db import Base, get_engine, session_factory
from nflpi.ingestion import service
from nflpi.models import InjuryReport, TeamStar
from nflpi.predictions import engine
from tests.conftest import CURRENT, TEAMS, _ensure_db, schedule_rows, team_rows


def _weather_outage() -> int:
    raise RuntimeError("Open-Meteo unreachable (e2e fixture)")


# club, list week, then (slot, rank, id, name, position, this week's status or None)
STAR_LISTS = [
    ("KC", 4, [
        ("qb", 1, "00-101", "Pat Passer", "QB", None),
        ("off", 1, "00-102", "Ron Runner", "RB", "Questionable"),
        ("off", 2, "00-103", "Cal Catch", "WR", "Doubtful"),
        ("def", 1, "00-104", "Cory Corner", "CB", "Out"),
        ("def", 2, "00-105", "Russ Rush", "DE", None),
    ]),
    ("NE", 3, [  # a list one week older than the game
        ("qb", 1, "00-201", "Quin Backer", "QB", None),
        ("off", 1, "00-202", "Wes Wideout", "WR", None),
        ("off", 2, "00-203", "Ty End", "TE", None),
        ("def", 1, "00-204", "Lyle Backer", "LB", None),
        ("def", 2, "00-205", "Sam Safety", "S", None),
    ]),
    ("BUF", 4, [  # all five out: the QB is already in the row's QB alert, the row names one more and says "+3 more"
        ("qb", 1, "00-301", "Jo Thrower", "QB", "Out"),
        ("off", 1, "00-302", "Maximilian Featherstonehaugh-Smythe III", "WR", "Out"),  # a very long name
        ("off", 2, "00-303", "Dee Deep", "WR", "Doubtful"),
        ("def", 1, "00-304", "Ed Edge", "DE", "Out"),
        ("def", 2, "00-305", "Nick Nickel", "CB", "Doubtful"),
    ]),
]  # MIA and LV have no list: their game shows "no star list yet"  # fmt: skip


def _stars(s, now: datetime) -> None:
    for team, week, players in STAR_LISTS:
        for slot, rank, pid, name, position, status in players:
            s.add(TeamStar(
                season=CURRENT, week=week, team=team, slot=slot, rank=rank, player_id=pid, player=name,
                position=position, snaps=1, production=1.0, score=1.0, source="e2e", computed_at=now,
            ))  # fmt: skip
            if status:
                s.add(InjuryReport(
                    season=CURRENT, week=4, team=team, player_id=pid, player=name, position=position,
                    report_status=status, practice_status=None, injury="Knee", source="nflverse",
                    observed_at=now - timedelta(hours=3),
                ))  # fmt: skip
    s.add(InjuryReport(
        season=CURRENT, week=4, team="KC", player_id="00-199", player="Not A Star", position="G",
        report_status="Out", practice_status=None, injury="Ankle", source="nflverse",
        observed_at=now - timedelta(hours=3),
    ))  # fmt: skip
    s.add(InjuryReport(  # a star with a practice note and no game status: on the report, status not known
        season=CURRENT, week=4, team="KC", player_id="00-105", player="Russ Rush", position="DE",
        report_status=None, practice_status="Limited", injury="Rest", source="nflverse",
        observed_at=now - timedelta(hours=3),
    ))  # fmt: skip
    s.commit()
    service.run_logged(s, "nflverse", "stars", lambda: 15)
    service.run_logged(s, "espn", "head_coaches", lambda: 6)


def main() -> None:
    _ensure_db()
    db = get_engine()
    Base.metadata.drop_all(db)
    Base.metadata.create_all(db)

    rows = schedule_rows()
    ids = {r["game_id"] for r in rows}
    week4 = next(r for r in rows if r["season"] == str(CURRENT) and r["week"] == "4")
    away, home = next((a, h) for a in TEAMS for h in TEAMS if a != h and f"{CURRENT}_04_{a}_{h}" not in ids)
    tbd = f"{CURRENT}_04_{away}_{home}"
    rows.append(week4 | {"game_id": tbd, "away_team": away, "home_team": home, "gametime": ""})

    with session_factory()() as s:
        service.ingest_schedules(s, rows)
        service.ingest_teams(s, team_rows())
        service.ingest_injuries(s, CURRENT, [])
        service.run_logged(s, "open-meteo", "weather", _weather_outage)
        _stars(s, datetime.now(UTC))
        engine.train(s, through_season=CURRENT - 1)
        engine.backfill_season(s, CURRENT)
        engine.refresh_predictions(s)
    print(f"e2e seed ready: TBD game {tbd}")


if __name__ == "__main__":
    main()
