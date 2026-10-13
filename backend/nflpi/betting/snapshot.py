"""Market snapshots and no-vig inside one complete, consistent set."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from nflpi.betting.odds import BettingError, finite_number, no_vig, raw_implied_prob, to_decimal

SELECTIONS = {
    "moneyline": ("home", "away", "draw"),
    "spread": ("home", "away"),
    "total": ("over", "under"),
}


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise BettingError(f"{name} must be a timezone-aware datetime")
    return value


@dataclass(frozen=True)
class MarketSnapshot:
    """One price for one selection, as one book showed it at one time. Spread line is the HOME spread."""

    game_id: str
    sportsbook: str
    observed_at: datetime
    market_type: str
    selection: str
    line: float | None
    odds_format: str
    price: float

    def __post_init__(self) -> None:
        for name in ("game_id", "sportsbook"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BettingError(f"{name} must be a non-empty string")
        _aware(self.observed_at, "observed_at")
        if self.market_type not in SELECTIONS:
            raise BettingError(f"unknown market type: {self.market_type!r}")
        if self.selection not in SELECTIONS[self.market_type]:
            raise BettingError(f"{self.selection!r} is not a {self.market_type} selection")
        if self.market_type == "moneyline":
            if self.line is not None:
                raise BettingError("a moneyline carries no line")
        else:
            finite_number(self.line, "line")
        to_decimal(self.price, self.odds_format)

    @property
    def decimal_odds(self) -> float:
        return to_decimal(self.price, self.odds_format)

    @property
    def implied_prob(self) -> float:
        return raw_implied_prob(self.price, self.odds_format)


def ensure_fresh(snapshot: MarketSnapshot, now: datetime, max_age: timedelta) -> None:
    """Reject odds older than max_age (strictly) or observed in the future."""
    _aware(now, "now")
    if not isinstance(max_age, timedelta) or max_age < timedelta(0):
        raise BettingError("max_age must be a non-negative timedelta")
    age = now - snapshot.observed_at
    if age < timedelta(0):
        raise BettingError("odds were observed in the future")
    if age > max_age:
        raise BettingError(f"odds are stale: age {age} exceeds {max_age}")


def no_vig_probabilities(snaps: Sequence[MarketSnapshot], *, three_way: bool = False) -> dict[str, float] | None:
    """Proportional no-vig across one set; None when the set is consistent but incomplete."""
    if not snaps or not all(isinstance(s, MarketSnapshot) for s in snaps):
        raise BettingError("need a non-empty list of MarketSnapshot")
    first = snaps[0]
    for s in snaps[1:]:
        if (s.game_id, s.sportsbook, s.observed_at, s.market_type, s.line) != (
            first.game_id, first.sportsbook, first.observed_at, first.market_type, first.line
        ):
            raise BettingError("snapshots differ in game, book, time, market type or line")
    if three_way and first.market_type != "moneyline":
        raise BettingError("only a moneyline can be three-way")
    allowed = SELECTIONS[first.market_type] if three_way or first.market_type != "moneyline" else ("home", "away")
    chosen = [s.selection for s in snaps]
    if len(set(chosen)) != len(chosen):
        raise BettingError("duplicate selection in set")
    if not set(chosen) <= set(allowed):
        raise BettingError(f"selections {chosen} do not belong in this set")
    if len(chosen) < len(allowed):
        return None
    by_selection = {s.selection: s.implied_prob for s in snaps}
    return dict(zip(allowed, no_vig([by_selection[k] for k in allowed]), strict=True))


def no_vig_probability(
    snapshot: MarketSnapshot, others: Sequence[MarketSnapshot] | None, *, three_way: bool = False
) -> float | None:
    probs = no_vig_probabilities([snapshot, *(others or [])], three_way=three_way)
    return None if probs is None else probs[snapshot.selection]
