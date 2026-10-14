"""Step 18i part 2 mutation sweep: one or more mutations per clause; each must make tests/test_value.py fail.

Run from backend/ with DATABASE_URL set to the lane database. Restores every file after each mutation.
"""

import subprocess
import sys
from pathlib import Path

M = [
    ("P1", "nflpi/models.py", '"observed_at",\n            "line",\n            "price",', '"observed_at",\n            "price",'),
    ("P1", "nflpi/models.py", '"observed_at",\n            "line",\n            "price",', '"observed_at",\n            "line",'),
    ("P1", "nflpi/models.py", "postgresql_nulls_not_distinct=True", "postgresql_nulls_not_distinct=False"),
    ("P1", "migrations/versions/0010_book_prices_key.py", 'down_revision = "0009"', 'down_revision = "0008"'),
    ("P1", "migrations/versions/0010_book_prices_key.py", "[*OLD, \"line\", \"price\"]", "[*OLD, \"line\"]"),
    ("P2", "nflpi/value/store.py", "if set(rows) != set(sides):", "if not rows:"),
    ("P2", "nflpi/value/store.py", "(r.sportsbook, r.observed_at, r.line)", "(r.sportsbook, r.observed_at, 0)"),
    ("P2", "nflpi/value/store.py", "(r.sportsbook, r.observed_at, r.line)", "(r.sportsbook, 0, r.line)"),
    ("P2", "nflpi/value/store.py", "rank = (observed_at, max(r.fetched_at", "rank = (-observed_at.timestamp(), max(r.fetched_at"),
    ("P2", "nflpi/value/store.py", "max(r.fetched_at for r in rows.values()), max(r.id", "-max(r.fetched_at.timestamp() for r in rows.values()), max(r.id"),
    ("P2", "nflpi/value/store.py", ".order_by(BookPrice.fetched_at.desc(), BookPrice.id.desc())", ".order_by(BookPrice.fetched_at.asc(), BookPrice.id.asc())"),
    ("P2", "nflpi/value/store.py", "BookPrice.observed_at <= as_of", "BookPrice.observed_at <= as_of + __import__('datetime').timedelta(hours=1)"),
    ("P2", "nflpi/value/store.py", '"total": ("over", "under")', '"total": ("over", "over")'),
    ("P3", "nflpi/ingestion/live/oddsapi.py", "prices += _spread_prices(market, home, away, seen)", "prices += _spread_prices(market, home, away, updated_book)"),
    ("P3", "nflpi/ingestion/live/oddsapi.py", "        elif seen is None:\n            continue\n", ""),
    ("P3", "nflpi/ingestion/live/oddsapi.py", "            if seen is not None:  # no market time", "            if True:  # no market time"),
    ("P3", "nflpi/ingestion/live/oddsapi.py", "if raw is None else _time(raw)", "if raw is None else (_time(raw) or max(seen_times, default=None))"),
    ("P3", "nflpi/ingestion/live/oddsapi.py", "updated = max(seen_times, default=None) if raw is None", "updated = None if raw is None"),
    ("P3", "nflpi/ingestion/live/run.py", "if p.observed_at > now + BOOK_CLOCK_SKEW:", "if False:"),
    ("P3", "nflpi/ingestion/live/run.py", "by_time.setdefault(min(p.observed_at, now), [])", "by_time.setdefault(p.observed_at, [])"),
    ("P4", "nflpi/ingestion/live/oddsapi.py", "if updated is None or (ml is None and not prices):", "if updated is None or ml is None:"),
    ("P4", "nflpi/ingestion/live/run.py", "if book.home_ml is None or book.away_ml is None:", "if False:"),
    ("P4", "nflpi/ingestion/live/oddsapi.py", "if found is None or ml is not None:", "if found is None:"),
    ("P5", "nflpi/config.py", "odds_extra_markets: bool = True", "odds_extra_markets: bool = False"),
    ("P5", "nflpi/ingestion/live/run.py", "settings.odds_extra_markets)", "True)"),
    ("P5", "nflpi/ingestion/live/run.py", "settings.odds_extra_markets)", "False)"),
    ("P6", "nflpi/config.py", '"odds_api_key_fallback",\n', ""),
    ("P6", "nflpi/config.py", 'odds_api_key_fallback: str = ""', 'odds_api_key_fallback: str = "x"'),
    ("P6", "nflpi/ingestion/live/run.py", 'str(exc) == "status 401"', 'str(exc) in ("status 401", "status 429")'),
    ("P6", "nflpi/ingestion/live/run.py", 'str(exc) == "status 401"', 'str(exc) == "status 403"'),
    ("P6", "nflpi/ingestion/live/run.py", "if not _out_of_credits(exc) or index + 1 == len(keys):", "if index + 1 == len(keys):"),
    ("P6", "nflpi/ingestion/live/run.py", "if not _out_of_credits(exc) or index + 1 == len(keys):", "if not _out_of_credits(exc):"),
    ("P6", "nflpi/ingestion/live/run.py", "and spare != key:", ":"),
    ("P6", "nflpi/ingestion/live/run.py", 'keys.append(("fallback", spare))', 'keys.append(("primary", spare))'),
    ("P6", "nflpi/ingestion/live/run.py", "if len(keys) == 1:\n            log.warning", "if True:\n            log.warning"),
    ("P6", "nflpi/ingestion/live/run.py", "< 50 and len(keys) == 1:", "< 50:"),
    ("P6", "nflpi/ingestion/live/run.py", 'log.info("oddsapi key slot %s used, credits remaining: %s", slot, result.headers.get("x-requests-remaining"))', 'log.info("oddsapi key slot %s used, credits remaining: %s", key, result.headers.get("x-requests-remaining"))'),
    ("P6", "nflpi/ingestion/live/run.py", "fallback_key if fallback_key is not None else settings.odds_api_key_fallback", "fallback_key or \"\""),
    ("P6", "nflpi/ingestion/live/run.py", "for index, (slot, key) in enumerate(keys):", "for index, (slot, key) in enumerate(keys[:1]):"),
]


def main() -> int:
    survived = []
    for clause, path, old, new in M:
        p = Path(path)
        src = p.read_text()
        if old not in src:
            print(f"{clause} NOT APPLIED: {old[:60]!r} missing in {path}")
            survived.append(clause)
            continue
        p.write_text(src.replace(old, new, 1))
        try:
            r = subprocess.run(
                ["uv", "run", "pytest", "tests/test_value.py", "-q", "-x", "-p", "no:cacheprovider"],
                capture_output=True,
                text=True,
            )
        finally:
            p.write_text(src)
        killed = r.returncode != 0
        print(f"{clause} {'killed' if killed else 'SURVIVED'}: {path}: {old[:50]!r}")
        if not killed:
            survived.append(clause)
    print(f"{len(M) - len(survived)}/{len(M)} killed")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
