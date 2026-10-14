"""Betting advice: a price and settlement chances in, a status out. It never sees a pick."""

from datetime import datetime, timedelta

from nflpi.betting.edge import SettlementProbs, expected_value
from nflpi.betting.odds import BettingError
from nflpi.betting.snapshot import MarketSnapshot, ensure_fresh
from nflpi.picks.types import Advice, PicksError, Rubric


def betting_advice(
    snapshot: MarketSnapshot,
    probs: SettlementProbs,
    *,
    now: datetime,
    max_age: timedelta,
    rubric: Rubric | None = None,
    qb_missing: bool = False,
) -> Advice:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise PicksError("now must be a timezone-aware datetime")
    if not isinstance(max_age, timedelta) or max_age < timedelta(0):
        raise PicksError("max_age must be a non-negative timedelta")
    ev = expected_value(probs, snapshot.decimal_odds)
    reasons: list[str] = []
    try:
        ensure_fresh(snapshot, now, max_age)
    except BettingError:  # ponytail: now and max_age are checked above, so this means stale or future
        reasons.append("STALE_PRICE")
    if ev <= 0:
        reasons.append("NONPOSITIVE_EV")
    provisional = rubric.provisional if rubric else True
    if reasons:
        return Advice("NO_BET", None, ev, tuple(reasons), provisional)
    if qb_missing:
        reasons.append("QB_MISSING")
    if rubric is None or not rubric.validated:
        reasons.append("NO_VALIDATION_HISTORY")
    if reasons:
        return Advice("UNRATED", None, ev, tuple(reasons), provisional)
    stars = sum(ev >= t for t in rubric.ev_thresholds)
    if stars == 0:
        return Advice("UNRATED", None, ev, ("BELOW_FIRST_THRESHOLD",), provisional)
    return Advice("RATED", stars, ev, (), provisional)
