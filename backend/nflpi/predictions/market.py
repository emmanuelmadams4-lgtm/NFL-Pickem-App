"""Moneyline math. Implied probabilities are normalized to remove the bookmaker margin."""

import math

DEVIG_METHODS = ("multiplicative", "additive", "shin", "power", "odds_ratio")


def implied_prob(moneyline: float) -> float:
    if moneyline < 0:
        return -moneyline / (-moneyline + 100)
    return 100 / (moneyline + 100)


def novig_home_prob(home_ml: float | None, away_ml: float | None) -> float | None:
    if home_ml is None or away_ml is None:
        return None
    h, a = implied_prob(home_ml), implied_prob(away_ml)
    return h / (h + a)


def devig_home_prob(home_ml: float | None, away_ml: float | None, method: str = "multiplicative") -> float | None:
    """Remove the bookmaker margin with the chosen two-outcome method."""
    if method not in DEVIG_METHODS:
        raise ValueError(f"unknown devig method: {method}")
    if home_ml is None or away_ml is None:
        return None
    h, a = implied_prob(home_ml), implied_prob(away_ml)
    if h + a == 1:
        return h
    if method == "multiplicative":
        return novig_home_prob(home_ml, away_ml)
    if method == "additive":
        return h - (h + a - 1) / 2
    if method == "power":
        low, high = 0.0, 100.0
        while high - low > 1e-12:
            mid = (low + high) / 2
            if h**mid + a**mid > 1:
                low = mid
            else:
                high = mid
        return h ** ((low + high) / 2)
    if method == "odds_ratio":
        c = math.sqrt(h / (1 - h) * a / (1 - a))
        return h / (c + h - c * h)
    b, d = h + a, h - a
    z = ((b - 1) * (d * d - b)) / (b * (d * d - 1))
    return (math.sqrt(z * z + 4 * (1 - z) * h * h / b) - z) / (2 * (1 - z))
