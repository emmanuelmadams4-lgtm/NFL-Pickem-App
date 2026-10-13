"""Bound source timestamps to usable UTC dates."""

from datetime import UTC, datetime


def parse_utc(text: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return None
        utc = parsed.astimezone(UTC)
        return utc if 2000 <= utc.year <= 2100 else None
    except (ValueError, OverflowError):
        return None
