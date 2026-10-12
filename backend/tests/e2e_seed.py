"""Seed the browser-test database: the pytest fixture league, one game with no kickoff time and a weather outage.

Run by scripts/e2e-server.sh with DATABASE_URL pointing at a throwaway database (nflpi_e2e).
"""

from nflpi.db import Base, get_engine, session_factory
from nflpi.ingestion import service
from nflpi.predictions import engine
from tests.conftest import CURRENT, TEAMS, _ensure_db, schedule_rows, team_rows


def _weather_outage() -> int:
    raise RuntimeError("Open-Meteo unreachable (e2e fixture)")


def main() -> None:
    _ensure_db()
    db = get_engine()
    Base.metadata.drop_all(db)
    Base.metadata.create_all(db)

    rows = schedule_rows()
    ids = {r["game_id"] for r in rows}
    week4 = next(r for r in rows if r["week"] == "4")
    away, home = next((a, h) for a in TEAMS for h in TEAMS if a != h and f"{CURRENT}_04_{a}_{h}" not in ids)
    tbd = f"{CURRENT}_04_{away}_{home}"
    rows.append(week4 | {"game_id": tbd, "away_team": away, "home_team": home, "gametime": ""})

    with session_factory()() as s:
        service.ingest_schedules(s, rows)
        service.ingest_teams(s, team_rows())
        service.ingest_injuries(s, CURRENT, [])
        service.run_logged(s, "open-meteo", "weather", _weather_outage)
        engine.train(s, through_season=CURRENT - 1)
        engine.backfill_season(s, CURRENT)
        engine.refresh_predictions(s)
    print(f"e2e seed ready: TBD game {tbd}")


if __name__ == "__main__":
    main()
