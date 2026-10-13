"""Odds conversion, raw implied probability and proportional no-vig."""

import math
from collections.abc import Sequence


class BettingError(ValueError):
    """Every invalid betting input raises this."""


def finite_number(value: object, name: str = "value") -> float:
    """Return value as a float; bool, non-numbers, NaN and infinity are rejected."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise BettingError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def american_to_decimal(price: float) -> float:
    a = finite_number(price, "american price")
    if abs(a) < 100:
        raise BettingError(f"american price must satisfy abs >= 100, got {price!r}")
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


def decimal_to_american(decimal_odds: float) -> float:
    d = finite_number(decimal_odds, "decimal price")
    if d <= 1:
        raise BettingError(f"decimal price must be > 1, got {decimal_odds!r}")
    return (d - 1) * 100 if d >= 2 else -100 / (d - 1)


def to_decimal(price: float, odds_format: str) -> float:
    if odds_format == "american":
        return american_to_decimal(price)
    if odds_format == "decimal":
        d = finite_number(price, "decimal price")
        if d <= 1:
            raise BettingError(f"decimal price must be > 1, got {price!r}")
        return d
    raise BettingError(f"unknown odds format: {odds_format!r}")


def raw_implied_prob(price: float, odds_format: str = "american") -> float:
    return 1 / to_decimal(price, odds_format)


def no_vig(raw_probs: Sequence[float]) -> list[float]:
    """Proportional no-vig over one complete 2- or 3-outcome set."""
    if isinstance(raw_probs, str) or len(raw_probs) not in (2, 3):
        raise BettingError("no-vig needs a complete set of 2 or 3 probabilities")
    q = [finite_number(p, "probability") for p in raw_probs]
    if any(p <= 0 for p in q):
        raise BettingError("probabilities must be positive")
    total = sum(q)
    return [p / total for p in q]
