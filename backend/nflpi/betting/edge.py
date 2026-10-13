"""The edge numbers: fair-probability edge, price edge, expected value and point difference."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from nflpi.betting.odds import BettingError, finite_number, to_decimal
from nflpi.betting.snapshot import SELECTIONS, MarketSnapshot, ensure_fresh, no_vig_probability

SUM_TOLERANCE = 1e-9


def _probability(value: object, name: str) -> float:
    p = finite_number(value, name)
    if not 0 <= p <= 1:
        raise BettingError(f"{name} must be in [0, 1], got {value!r}")
    return p


@dataclass(frozen=True)
class SettlementProbs:
    """Probability of a win, a refunded push and a loss; they sum to one."""

    win: float
    push: float
    loss: float

    def __post_init__(self) -> None:
        parts = [_probability(getattr(self, n), n) for n in ("win", "push", "loss")]
        if not math.isclose(sum(parts), 1.0, abs_tol=SUM_TOLERANCE):
            raise BettingError("win + push + loss must sum to 1")

    @property
    def conditional_win(self) -> float:
        """Win probability given the bet is not refunded."""
        if self.win + self.loss == 0:
            raise BettingError("conditional win is undefined when every outcome is a push")
        return self.win / (self.win + self.loss)


@dataclass(frozen=True)
class Edge:
    fair_probability_edge: float | None
    price_edge: float
    expected_value: float
    point_difference: float | None


def _decimal(decimal_odds: float) -> float:
    return to_decimal(decimal_odds, "decimal")


def _probs(probs: SettlementProbs) -> SettlementProbs:
    if not isinstance(probs, SettlementProbs):
        raise BettingError("probs must be SettlementProbs")
    return probs


def break_even_probability(decimal_odds: float) -> float:
    return 1 / _decimal(decimal_odds)


def expected_value(probs: SettlementProbs, decimal_odds: float) -> float:
    """EV per unit staked: win * (d - 1) - loss. A refunded push adds zero."""
    d = _decimal(decimal_odds)
    p = _probs(probs)
    return p.win * (d - 1) - p.loss


def fair_probability_edge(model_prob: float, market_prob: float | None) -> float | None:
    """Model minus no-vig market probability, signed; None when the market is unavailable."""
    model = _probability(model_prob, "model probability")
    if market_prob is None:
        return None
    return model - _probability(market_prob, "market probability")


def price_edge(probs: SettlementProbs, decimal_odds: float) -> float:
    """Conditional win probability minus the break-even probability of the price."""
    return _probs(probs).conditional_win - break_even_probability(decimal_odds)


def point_difference(market_type: str, selection: str, line: float, forecast: float) -> float:
    """Forecast margin (spread: home minus away; total: points) vs the line, from the selection's side."""
    if market_type not in ("spread", "total"):
        raise BettingError("point difference applies to spreads and totals only")
    if selection not in SELECTIONS[market_type]:
        raise BettingError(f"{selection!r} is not a {market_type} selection")
    ln = finite_number(line, "line")
    f = finite_number(forecast, "forecast")
    if market_type == "spread":
        diff = f + ln
        return diff if selection == "home" else -diff
    diff = f - ln
    return diff if selection == "over" else -diff


def evaluate(
    snapshot: MarketSnapshot,
    probs: SettlementProbs,
    *,
    now: datetime,
    max_age: timedelta,
    opposing: Sequence[MarketSnapshot] | None = None,
    forecast: float | None = None,
    three_way: bool = False,
) -> Edge:
    ensure_fresh(snapshot, now, max_age)
    for other in opposing or []:
        ensure_fresh(other, now, max_age)
    conditional = _probs(probs).conditional_win
    d = snapshot.decimal_odds
    diff = None
    if forecast is not None:
        diff = point_difference(snapshot.market_type, snapshot.selection, snapshot.line, forecast)
    return Edge(
        fair_probability_edge=fair_probability_edge(
            conditional, no_vig_probability(snapshot, opposing, three_way=three_way)
        ),
        price_edge=conditional - 1 / d,
        expected_value=expected_value(probs, d),
        point_difference=diff,
    )
