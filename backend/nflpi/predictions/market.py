"""Moneyline math. Implied probabilities are normalized to remove the bookmaker margin."""


def implied_prob(moneyline: float) -> float:
    if moneyline < 0:
        return -moneyline / (-moneyline + 100)
    return 100 / (moneyline + 100)


def novig_home_prob(home_ml: float | None, away_ml: float | None) -> float | None:
    if home_ml is None or away_ml is None:
        return None
    h, a = implied_prob(home_ml), implied_prob(away_ml)
    return h / (h + a)
