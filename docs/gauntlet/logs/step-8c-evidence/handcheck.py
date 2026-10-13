"""Hand check: fetch each allowlisted feed LIVE through the guarded fetcher (robots included) and parse it.
No database. Run: backend/.venv/bin/python docs/gauntlet/logs/step-8c-evidence/handcheck.py"""

from datetime import UTC, datetime

from nflpi.ingestion.news import fetch, parse, sources

now = datetime.now(UTC)
for src in sources.SOURCES:
    try:
        res = fetch.fetch_feed(src)
        items = parse.parse_feed(res.body, src, now)
    except fetch.FetchError as exc:
        print(f"{src.id}: {type(exc).__name__}: {exc}")
        continue
    print(f"{src.id}: status {res.status}, {len(res.body)} bytes, etag {res.etag!r}, {len(items)} items")
    for it in items[:3]:
        print(f"   {it.published_at} | {it.title[:70]} | {it.url[:70]}")
