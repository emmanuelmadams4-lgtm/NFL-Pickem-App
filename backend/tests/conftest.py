"""Tests run against a real Postgres database (nflpi_test) with realistic, made-up fixture games.

Start one with: docker compose up -d db  (the test DB is created automatically)
"""

import os
import random
from datetime import UTC, datetime, timedelta

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://nflpi:nflpi@localhost:5432/nflpi_test")
os.environ["APP_ACCESS_TOKEN"] = "test-token"
os.environ["FIRST_SEASON"] = "2018"
os.environ["TRAIN_WINDOW_SEASONS"] = "3"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from nflpi.db import Base, get_engine, session_factory  # noqa: E402

TEAMS = ["BUF", "MIA", "NE", "NYJ", "KC", "LV"]
STRENGTH = {"BUF": 6, "KC": 5, "MIA": 1, "NE": -2, "NYJ": -3, "LV": -5}
NOW = datetime.now(UTC).replace(microsecond=0)
CURRENT = 2023


def _ensure_db() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.scalar(text("select 1 from pg_database where datname = :n"), {"n": url.database}):
            c.execute(text(f'create database "{url.database}"'))
    admin.dispose()


def _row(season: int, week: int, kickoff: datetime, away: str, home: str, rng: random.Random, final: bool) -> dict:
    et = kickoff - timedelta(hours=4)  # fixtures are in EDT
    margin = STRENGTH[home] - STRENGTH[away] + 2 + rng.gauss(0, 10)
    hs, as_ = (24 + round(margin / 2), 24 - round(margin / 2)) if final else ("", "")
    if final and hs == as_:
        hs += 3
    hml, aml = (-150, 130) if STRENGTH[home] + 2 >= STRENGTH[away] else (130, -150)
    return {
        "game_id": f"{season}_{week:02d}_{away}_{home}",
        "season": str(season),
        "game_type": "REG",
        "week": str(week),
        "gameday": et.date().isoformat(),
        "weekday": et.strftime("%A"),
        "gametime": et.strftime("%H:%M"),
        "away_team": away,
        "away_score": str(as_),
        "home_team": home,
        "home_score": str(hs),
        "location": "Home",
        "away_rest": "7",
        "home_rest": "7",
        "away_moneyline": str(aml),
        "home_moneyline": str(hml),
        "spread_line": "3",
        "total_line": "45.5",
        "div_game": "1",
        "roof": "outdoors",
        "surface": "grass",
        "temp": "60" if final else "",
        "wind": "5" if final else "",
        "away_qb_name": f"{away} QB1",
        "home_qb_name": f"{home} QB1",
        "away_coach": f"{away} Coach",
        "home_coach": f"{home} Coach",
        "stadium_id": "BUF00",
        "stadium": f"{home} Stadium",
    }


def schedule_rows() -> list[dict]:
    """Seasons 2018-2023. 2023: weeks 1-3 final, weeks 4-5 in the future."""
    rng = random.Random(11)
    rows = []
    for season in range(2018, CURRENT + 1):
        pairs = [(a, h) for a in TEAMS for h in TEAMS if a != h]
        rng.shuffle(pairs)
        for i, (away, home) in enumerate(pairs[:15]):
            week = i // 3 + 1
            if season == CURRENT:
                kickoff = NOW + timedelta(days=7 * (week - 4) + 2, hours=i % 3)
                final = week <= 3
            else:
                kickoff = datetime(season, 9, 10, 17, tzinfo=UTC) + timedelta(days=7 * (week - 1), hours=i % 3)
                final = True
            rows.append(_row(season, week, kickoff, away, home, rng, final))
    return rows


def team_rows() -> list[dict]:
    return [
        {
            "team_abbr": t,
            "team_name": f"{t} Team",
            "team_nick": t.title(),
            "team_conf": "AFC",
            "team_division": "AFC East",
            "team_color": "#112233",
            "team_color2": "#445566",
            "team_logo_espn": f"https://example.test/{t}.png",
        }
        for t in TEAMS
    ]


@pytest.fixture(scope="session", autouse=True)
def database():
    _ensure_db()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine


@pytest.fixture
def session(database):
    with database.begin() as c:
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        c.execute(text(f"truncate {names} restart identity cascade"))
    with session_factory()() as s:
        yield s


@pytest.fixture
def loaded(session):
    """Schedules + teams ingested, model trained, predictions made."""
    from nflpi.ingestion import service
    from nflpi.predictions import engine

    service.ingest_schedules(session, schedule_rows())
    service.ingest_teams(session, team_rows())
    engine.train(session, through_season=CURRENT - 1)
    engine.refresh_predictions(session)
    return session


@pytest.fixture
def client():
    from nflpi.api.main import app

    c = TestClient(app)
    c.headers["Authorization"] = "Bearer test-token"
    return c
