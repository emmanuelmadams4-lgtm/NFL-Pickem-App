"""Step 18i mutation sweep: one or more mutations per clause; each must make tests/test_value.py fail.

Run from backend/ with DATABASE_URL set to the lane database. Restores every file after each mutation.
"""

import subprocess
import sys
from pathlib import Path

M = [
    ("V1", "nflpi/models.py", '"selection", "observed_at", name="uq_book_prices_key"', '"selection", name="uq_book_prices_key"'),
    ("V1", "migrations/versions/0009_book_prices.py", 'down_revision = "0008"', 'down_revision = "0007"'),
    ("V2", "nflpi/value/store.py", "if observed_at > fetched_at:", "if observed_at > fetched_at + fetched_at.utcoffset() * 0 + (fetched_at - fetched_at) * 0 + __import__('datetime').timedelta(seconds=5):"),
    ("V2", "nflpi/value/store.py", ".on_conflict_do_nothing(constraint=\"uq_book_prices_key\")", ".on_conflict_do_update(constraint=\"uq_book_prices_key\", set_={\"price\": insert(BookPrice).excluded.price})"),
    ("V2", "nflpi/value/store.py", 'quote["line"],', 'None if quote["market_type"] == "moneyline" else quote["line"],'),
    ("V2", "nflpi/value/store.py", "fetched_at.tzinfo is None or", "False and"),
    ("V3", "nflpi/value/store.py", "BookPrice.observed_at <= as_of", "BookPrice.observed_at <= as_of + __import__('datetime').timedelta(hours=1)"),
    ("V3", "nflpi/value/store.py", "BookPrice.observed_at.desc()", "BookPrice.observed_at.asc()"),
    ("V3", "nflpi/value/store.py", "BookPrice.market_type == market_type,", ""),
    ("V4", "nflpi/ingestion/live/oddsapi.py", '"h2h,spreads,totals" if extra_markets else "h2h"', '"h2h,spreads,totals"'),
    ("V4", "nflpi/ingestion/live/oddsapi.py", '"h2h,spreads,totals" if extra_markets else "h2h"', '"h2h,spreads" if extra_markets else "h2h"'),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "or hp != -ap or", "or"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "abs(hp) > MAX_SPREAD", "abs(hp) >= MAX_SPREAD"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "not 0 < point <= MAX_TOTAL", "not 0 <= point <= MAX_TOTAL"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "not 0 < point <= MAX_TOTAL", "not 0 < point < MAX_TOTAL"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "or under.get(\"point\") != point", ""),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "def _point(value: Any) -> bool:\n    if type(value) not in (int, float):", "def _point(value: Any) -> bool:\n    if type(value) not in (int, float, bool):"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "    except OverflowError:\n        return False\n\n\ndef _pair", "    except ZeroDivisionError:\n        return False\n\n\ndef _pair"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "(_point(point) and _point(under.get(\"point\")))", "_point(point)"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "return [first, second] if _price(first.get(\"price\")) and _price(second.get(\"price\")) else None", "return [first, second]"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "Price(\"spread\", \"away\", ap, a[\"price\"])", "Price(\"spread\", \"away\", hp, a[\"price\"])"),
    ("V5", "nflpi/ingestion/live/oddsapi.py", "elif market.get(\"key\") == \"totals\":", "elif market.get(\"key\") == \"total\":"),
    ("V6", "nflpi/config.py", "Field(default=30, gt=0)", "Field(default=30, ge=0)"),
    ("V6", "nflpi/value/store.py", "timedelta(minutes=get_settings()", "timedelta(seconds=get_settings()"),
    ("V7", "nflpi/value/rate.py", "max_age=max_price_age() if max_age is None else max_age", "max_age=max_price_age()"),
    ("V7", "nflpi/value/rate.py", "qb_missing=qb_missing", "qb_missing=False"),
    ("V8", "nflpi/value/rate.py", "snapshot, probs, now=now,", "snapshot, probs, rubric=__import__('nflpi.picks').picks.Rubric((0.01, 0.02, 0.03, 0.04, 0.05), validated=True), now=now,"),
    ("V9", "nflpi/value/rate.py", "it may no longer be offered.", "still available now."),
    ("V9", "nflpi/value/rate.py", "        now - snapshot.observed_at,", "        timedelta(0),"),
    ("V9", "nflpi/value/rate.py", "seen = snapshot.observed_at.astimezone(UTC)", "seen = snapshot.observed_at"),
    ("V11", "nflpi/ingestion/live/run.py", '"line": -p.line if flip', '"line": p.line if flip'),
    ("V11", "nflpi/ingestion/live/run.py", "FLIP[p.selection] if flip else p.selection", "p.selection"),
    ("V11", "nflpi/ingestion/live/run.py", "min(book.updated, now)", "book.updated"),
    ("V11", "nflpi/ingestion/live/run.py", "            _save_book_prices(session, event, book, game, now)\n", ""),
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
