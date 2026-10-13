"""Real-data check for step 8a (criterion S16), written by the coordinator.

Loads the full nflverse files into a throwaway database through the app's own ingest functions, then compares
  1. the app's stars with s8a-handcount.py, an independent count that reads the CSV files directly, and
  2. the app's "who's out" for every 2026 week 5 game with a direct read of the injury file.
Usage (from backend/): DATABASE_URL=...15438/nflpi_handcheck FIRST_SEASON=2025 \
  uv run python ../docs/gauntlet/logs/step-8a-evidence/s8a-realcheck.py <folder with the downloaded files>
File names in the folder: <release>__<file>.csv, e.g. snap_counts__snap_counts_2026.csv.
"""

import csv
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

assert "15438" in os.environ["DATABASE_URL"], "the lane's own database only"

from sqlalchemy import select  # noqa: E402

from nflpi.analytics.stars import stars_out  # noqa: E402
from nflpi.db import Base, get_engine, session_factory  # noqa: E402
from nflpi.ingestion import service  # noqa: E402
from nflpi.models import Game, TeamStar  # noqa: E402

data, here = Path(sys.argv[1]), Path(__file__).parent
ORDER = {"qb": 0, "off": 1, "def": 2}
CHECKS = [(2026, 6, "KC,BUF,DET,PHI,DAL,SF,BAL,PIT"), (2025, 19, "KC,PHI,PIT,DEN,CLE,LV,HOU,DET")]


def rows(name: str) -> list[dict]:
    with open(data / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def files(season: int) -> tuple[str, str, str]:
    return f"snap_counts__snap_counts_{season}.csv", f"stats_player__stats_player_week_{season}.csv", "players__players.csv"


def independent(season: int, week: int, teams: str) -> list[str]:
    cmd = [sys.executable, "-I", str(here / "s8a-handcount.py"), *(str(data / f) for f in files(season)), str(week), teams]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()


engine = get_engine()
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
bad = 0
with session_factory()() as session:
    for season in (2025, 2026):
        snaps, stats, players = (rows(f) for f in files(season))
        run = service.ingest_stars(session, season, snaps=snaps, stats=stats, players=players)
        print(f"ingest_stars {season}: {run.status}, {run.rows} rows {run.error or ''}")
        bad += run.status != "ok"

    print("\n== 1. Stars: app against the independent count")
    for season, week, teams in CHECKS:
        want = independent(season, week, teams)
        got = []
        for team in teams.split(","):
            found = session.scalars(
                select(TeamStar).where(TeamStar.season == season, TeamStar.week == week, TeamStar.team == team)
            ).all()
            for r in sorted(found, key=lambda r: (ORDER[r.slot], r.rank)):
                got.append(
                    f"{team}|{r.slot}|{r.rank}|{r.player}|{r.player_id}|{r.position}|{r.snaps}|{r.production:.2f}|{r.score:.2f}"
                )
        same = sum(1 for line in got if line in want)
        verdict = "MATCH" if got == want else "DIFF"
        bad += verdict != "MATCH"
        print(f"-- {season} stars for week {week}: {verdict} ({same} of {len(want)} rows)")
        for line in got:
            print("   " + line + ("" if line in want else "   <-- not in the independent count"))

    print("\n== 2. Who's out: app against a direct read of injuries_2026.csv, every week 5 game")
    print(service.ingest_schedules(session, rows("schedules__games.csv")).status, "schedules")
    inj = rows("injuries__injuries_2026.csv")
    run, _ = service.ingest_injuries(session, 2026, inj)
    print(run.status, "injuries", run.rows, "rows")
    games = session.scalars(select(Game).where(Game.season == 2026, Game.week == 5).order_by(Game.game_id)).all()
    clubs = ",".join(sorted({t for g in games for t in (g.away_team, g.home_team)}))
    star_ids = {(line.split("|")[0], line.split("|")[4]): line.split("|")[3] for line in independent(2026, 5, clubs)}
    hurt = {
        (r["team"], r["gsis_id"]): r["report_status"]
        for r in inj
        if r["week"] == "5" and r["report_status"] in ("Out", "Doubtful")
    }
    want_out = sorted((team, name, hurt[(team, pid)]) for (team, pid), name in star_ids.items() if (team, pid) in hurt)
    got_out = []
    for g in games:
        result = stars_out(session, g.game_id, now=datetime.now(UTC))
        assert result["stars_week"] == 5, result
        for r in result["out"]:
            got_out.append((r["team"], r["player"], r["status"]))
            print(f"   {g.game_id}: {r['team']} {r['player']} ({r['slot']} {r['rank']}) {r['status']}, {r['injury']}")
    verdict = "MATCH" if sorted(got_out) == want_out else "DIFF"
    bad += verdict != "MATCH"
    print(f"-- {len(games)} games, {len(got_out)} stars out or doubtful: {verdict} (independent read: {len(want_out)})")
sys.exit(1 if bad else 0)
