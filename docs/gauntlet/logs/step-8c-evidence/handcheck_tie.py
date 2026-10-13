"""Hand check for 8e: real teams and real 2026 star names (nflverse) against the recorded real headlines.
Needs DATABASE_URL pointing at an empty migrated scratch database. Prints one line per headline for a human to judge."""

from datetime import UTC, datetime
from pathlib import Path

from nflpi.db import session_factory
from nflpi.ingestion import service
from nflpi.ingestion.news import match, parse, sources

FIX = Path("tests/fixtures/news")
now = datetime(2026, 10, 13, 4, 0, tzinfo=UTC)
with session_factory()() as s:
    print("schedules", service.ingest_schedules(s).status, "teams", service.ingest_teams(s).status, "stars", service.ingest_stars(s, 2026).status)
    names = match.load_names(s)
    print("players with a unique name:", len(names.player_ids))
    total = tied = 0
    for src in sources.SOURCES:
        for it in parse.parse_feed((FIX / f"{src.id}.xml").read_bytes(), src, now):
            t = match.tie(it.title, it.extract, names)
            total += 1
            tied += bool(t.team_ids or t.player_ids)
            print(f"{src.id:4} | {it.title[:90]} | teams={t.team_ids} players={t.player_ids} tags={t.tags}")
    print(f"{total} headlines, {tied} tied to a team or player")
