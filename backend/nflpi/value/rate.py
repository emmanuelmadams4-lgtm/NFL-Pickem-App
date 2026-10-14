"""Rate one book price. It is shown as seen at a time, never as still offered."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from nflpi.betting.edge import SettlementProbs
from nflpi.betting.snapshot import MarketSnapshot
from nflpi.picks import Advice, betting_advice
from nflpi.value.store import max_price_age


@dataclass(frozen=True)
class ValueRating:
    advice: Advice
    sportsbook: str
    market_type: str
    selection: str
    line: float | None
    price: float
    observed_at: datetime
    age: timedelta
    note: str


def _note(snapshot: MarketSnapshot) -> str:
    seen = snapshot.observed_at.astimezone(UTC)
    return f"Price seen at {seen:%Y-%m-%d %H:%M} UTC by {snapshot.sportsbook}; it may no longer be offered."


def rate_price(
    snapshot: MarketSnapshot,
    probs: SettlementProbs,
    *,
    now: datetime,
    max_age: timedelta | None = None,
    qb_missing: bool = False,
) -> ValueRating:
    # ponytail: no rubric is passed, so positive value stays UNRATED until PLAN 3.4 (validation history) is met.
    advice = betting_advice(
        snapshot, probs, now=now, max_age=max_price_age() if max_age is None else max_age, qb_missing=qb_missing
    )
    return ValueRating(
        advice,
        snapshot.sportsbook,
        snapshot.market_type,
        snapshot.selection,
        snapshot.line,
        snapshot.price,
        snapshot.observed_at,
        now - snapshot.observed_at,
        _note(snapshot),
    )
