"""Hand check: each allowlisted feed fetched ONCE through the landed guarded fetch (robots included), 10 s apart,
stored by news_worker.news_step into a scratch database, then read back through GET /api/news.
Run: DATABASE_URL=.../nflpi_hand8g uv run python ../docs/gauntlet/logs/step-8g-server-evidence/handcheck_8g.py"""

import os
import time
from collections import Counter
from datetime import UTC, datetime

os.environ["APP_ACCESS_TOKEN"] = "hand-token"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from nflpi import news_worker  # noqa: E402
from nflpi.api.main import app  # noqa: E402
from nflpi.db import Base, get_engine, session_factory  # noqa: E402
from nflpi.ingestion.news import sources  # noqa: E402
from nflpi.models import Game, IngestionRun, NewsItem, Team  # noqa: E402

TEAMS = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders", "LAC": "Los Angeles Chargers", "LA": "Los Angeles Rams", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}  # fmt: skip

Base.metadata.drop_all(get_engine())
Base.metadata.create_all(get_engine())
with session_factory()() as session:
    session.add_all(
        Team(abbr=a, name=n, nick=n.split()[-1], conference="X", division="d", color="#000", color2="#000", logo_url="x")
        for a, n in TEAMS.items()
    )
    session.commit()
    for i, src in enumerate(sources.SOURCES):
        if i:
            time.sleep(10)
        made = news_worker.news_step(session, datetime.now(UTC), sources=(src,))
        print(src.id, [(r.status, r.rows, r.error) for r in made])
    counts = Counter(t for ids in session.scalars(select(NewsItem.team_ids)) for t in ids)
    print("stored:", session.query(NewsItem).count(), "tied teams:", counts.most_common(3))
    top = [t for t, _ in counts.most_common(2)] or ["BUF", "MIA"]
    session.add(
        Game(game_id="2026_06_X_Y", season=2026, week=6, game_type="REG", kickoff_utc=datetime.now(UTC), weekday="Sun",
             away_team=top[0], home_team=top[-1], status="scheduled", source="hand")
    )  # fmt: skip
    session.commit()
    print("runs:", [(r.dataset, r.status) for r in session.scalars(select(IngestionRun))])
client = TestClient(app)
reply = client.get("/api/news", params={"game_id": "2026_06_X_Y"}, headers={"Authorization": "Bearer hand-token"})
print("GET /api/news", reply.status_code)
for item in reply.json()["items"]:
    print(" -", item["source"], "|", item["published_at"], "|", item["title"][:70], "|", item["url"], "|", item["tags"])
