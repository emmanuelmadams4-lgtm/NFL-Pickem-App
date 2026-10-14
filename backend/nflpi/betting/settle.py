"""Settlement of moneyline, spread and total bets. Result is win, loss or push (refund)."""

from nflpi.betting.odds import BettingError, finite_number
from nflpi.betting.snapshot import MarketSnapshot


def _score(value: object) -> int:
    n = finite_number(value, "score")
    if n < 0 or not n.is_integer():
        raise BettingError(f"score must be a non-negative integer, got {value!r}")
    return int(n)


def _sign(margin: float) -> str:
    return "win" if margin > 0 else "push" if margin == 0 else "loss"


def _side(margin: float, first: bool) -> str:
    """Result for the first side (margin > 0 wins), or its opposite."""
    result = _sign(margin)
    return result if first else {"win": "loss", "loss": "win", "push": "push"}[result]


def _check(selection: str, allowed: tuple[str, ...]) -> None:
    if selection not in allowed:
        raise BettingError(f"selection must be one of {allowed}, got {selection!r}")


def settle_moneyline(selection: str, home_score: int, away_score: int, *, three_way: bool = False) -> str:
    _check(selection, ("home", "away", "draw") if three_way else ("home", "away"))
    margin = _score(home_score) - _score(away_score)
    if margin == 0:
        return ("win" if selection == "draw" else "loss") if three_way else "push"
    if selection == "draw":
        return "loss"
    return "win" if (margin > 0) == (selection == "home") else "loss"


def settle_spread(selection: str, home_line: float, home_score: int, away_score: int) -> str:
    """Home covers when (home - away) + home_line > 0; push at 0."""
    _check(selection, ("home", "away"))
    line = finite_number(home_line, "line")
    return _side(_score(home_score) - _score(away_score) + line, selection == "home")


def settle_total(selection: str, line: float, home_score: int, away_score: int) -> str:
    _check(selection, ("over", "under"))
    ln = finite_number(line, "line")
    return _side(_score(home_score) + _score(away_score) - ln, selection == "over")


def settle(snapshot: MarketSnapshot, home_score: int, away_score: int, *, three_way: bool = False) -> str:
    if snapshot.market_type == "moneyline":
        return settle_moneyline(snapshot.selection, home_score, away_score, three_way=three_way)
    if snapshot.market_type == "spread":
        return settle_spread(snapshot.selection, snapshot.line, home_score, away_score)
    return settle_total(snapshot.selection, snapshot.line, home_score, away_score)
