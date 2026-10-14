"""Validate The Odds API NFL head-to-head prices."""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple
from urllib.parse import urlencode

from nflpi.ingestion.live.times import parse_utc

ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?"
KEY = re.compile(r"[A-Za-z0-9]{16,64}")
BOOK_KEY = re.compile(r"[a-z0-9_]{1,24}")
CREDIT = re.compile(r"[0-9]{1,7}")
UTC_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
# Three unusable items suggest the whole reply changed format.
SHAPE_FAILURE_THRESHOLD = 3
MAX_SPREAD = 60
MAX_TOTAL = 150
TEAM_NAMES = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


class Price(NamedTuple):
    market_type: str
    selection: str
    line: float | None
    price: float


@dataclass(frozen=True)
class Book:
    key: str
    updated: datetime
    home_ml: float
    away_ml: float
    prices: tuple[Price, ...] = ()


@dataclass(frozen=True)
class Event:
    home: str
    away: str
    commence: datetime
    books: list[Book]


def odds_url(key: str, *, extra_markets: bool = False) -> str:
    if not isinstance(key, str) or KEY.fullmatch(key) is None:
        raise ValueError("key")
    markets = "h2h,spreads,totals" if extra_markets else "h2h"
    return ODDS_URL + urlencode({"regions": "us", "markets": markets, "oddsFormat": "american", "apiKey": key})


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or UTC_TIME.fullmatch(value) is None:
        return None
    return parse_utc(value)


def _price(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and 100 <= abs(value) <= 100_000
    except OverflowError:
        return False


def _point(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _pair(market: dict, names: tuple[str, str]) -> list[dict] | None:
    """The two outcomes of a market in the order of names, or None unless exactly those two names appear."""
    outcomes = market.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != 2 or not all(isinstance(o, dict) for o in outcomes):
        return None
    by_name = {o["name"]: o for o in outcomes if isinstance(o.get("name"), str)}
    if len(by_name) != 2 or set(by_name) != set(names):
        return None
    first, second = by_name[names[0]], by_name[names[1]]
    return [first, second] if _price(first.get("price")) and _price(second.get("price")) else None


def _spread_prices(market: dict, home: str, away: str) -> tuple[Price, ...]:
    pair = _pair(market, (home, away))
    if pair is None:
        return ()
    h, a = pair
    hp, ap = h.get("point"), a.get("point")
    if not (_point(hp) and _point(ap)) or hp != -ap or abs(hp) > MAX_SPREAD:
        return ()
    # the HOME spread on both selections, as betting.MarketSnapshot keeps it
    return (Price("spread", "home", hp, h["price"]), Price("spread", "away", hp, a["price"]))


def _total_prices(market: dict) -> tuple[Price, ...]:
    pair = _pair(market, ("Over", "Under"))
    if pair is None:
        return ()
    over, under = pair
    point = over.get("point")
    if not (_point(point) and _point(under.get("point"))) or under.get("point") != point or not 0 < point <= MAX_TOTAL:
        return ()
    return (Price("total", "over", point, over["price"]), Price("total", "under", point, under["price"]))


def _extra_prices(markets: list, home: str, away: str) -> tuple[Price, ...]:
    found: list[Price] = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        if market.get("key") == "spreads":
            found.extend(_spread_prices(market, home, away))
        elif market.get("key") == "totals":
            found.extend(_total_prices(market))
    return tuple(found)


def _book(item: Any, home: str, away: str) -> Book | None:
    if not isinstance(item, dict):
        return None
    key, updated, markets = item.get("key"), _time(item.get("last_update")), item.get("markets")
    if not isinstance(key, str) or BOOK_KEY.fullmatch(key) is None or updated is None or not isinstance(markets, list):
        return None
    for market in markets:
        if not isinstance(market, dict) or market.get("key") != "h2h":
            continue
        outcomes = market.get("outcomes")
        if not isinstance(outcomes, list) or len(outcomes) != 2 or not all(isinstance(o, dict) for o in outcomes):
            continue
        prices = {o.get("name"): o.get("price") for o in outcomes if isinstance(o.get("name"), str)}
        if len(prices) == 2 and set(prices) == {home, away} and all(_price(p) for p in prices.values()):
            moneyline = (
                Price("moneyline", "home", None, float(prices[home])),
                Price("moneyline", "away", None, float(prices[away])),
            )
            return Book(
                key, updated, float(prices[home]), float(prices[away]), moneyline + _extra_prices(markets, home, away)
            )
    return None


def _event(item: Any) -> tuple[Event | None, int]:
    if not isinstance(item, dict):
        return None, 1
    home, away = item.get("home_team"), item.get("away_team")
    commence, books = _time(item.get("commence_time")), item.get("bookmakers")
    if (
        not isinstance(home, str)
        or not isinstance(away, str)
        or home not in TEAM_NAMES
        or away not in TEAM_NAMES
        or home == away
        or commence is None
        or not isinstance(books, list)
        or len(books) > 40
    ):
        return None, 1
    parsed = [_book(book, home, away) for book in books]
    event = Event(home, away, commence, [book for book in parsed if book is not None])
    return event, sum(book is None for book in parsed)


def parse_events(data: Any) -> tuple[list[Event], int]:
    if not isinstance(data, list) or len(data) > 100:
        raise ValueError("shape")
    if data and not any(isinstance(item, dict) for item in data):
        raise ValueError("shape")
    parsed = [_event(item) for item in data]
    usable = [event for event, _ in parsed if event is not None]
    if len(data) >= SHAPE_FAILURE_THRESHOLD and not usable:
        raise ValueError("shape")
    return usable, sum(skipped for _, skipped in parsed)
