"""Validate Kalshi NFL game YES markets."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from nflpi.ingestion.live.times import parse_utc

MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets?series_ticker=KXNFLGAME&status=open&limit=200"
CURSOR = re.compile(r"[A-Za-z0-9_=-]{1,200}")
TICKER = re.compile(r"KXNFLGAME-([0-9]{2})([A-Z]{3})([0-9]{2})([A-Z]{4,6})-([A-Z]{2,3})")
PRICE = re.compile(r"[01]\.[0-9]{1,4}")
# Three unusable items suggest the whole reply changed format.
SHAPE_FAILURE_THRESHOLD = 3
MONTHS = {
    month: number
    for number, month in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
    )
}
TEAM_CODES = {
    code: code
    for code in (
        "ARI",
        "ATL",
        "BAL",
        "BUF",
        "CAR",
        "CHI",
        "CIN",
        "CLE",
        "DAL",
        "DEN",
        "DET",
        "GB",
        "HOU",
        "IND",
        "KC",
        "LAC",
        "LV",
        "MIA",
        "MIN",
        "NE",
        "NO",
        "NYG",
        "NYJ",
        "PHI",
        "PIT",
        "SEA",
        "SF",
        "TB",
        "TEN",
        "WAS",
    )
}
TEAM_CODES.update({"JAC": "JAX", "LAR": "LA"})


@dataclass(frozen=True)
class Market:
    event_ticker: str
    team: str
    bid: float
    ask: float
    updated_time: datetime | None


def markets_url(cursor: str | None = None) -> str:
    if cursor is None:
        return MARKETS_URL
    if not isinstance(cursor, str) or CURSOR.fullmatch(cursor) is None:
        raise ValueError("cursor")
    return MARKETS_URL + "&cursor=" + quote(cursor, safe="")


def _time(value: Any) -> datetime | None:
    return parse_utc(value) if isinstance(value, str) else None


def _market(item: dict) -> Market | None:
    ticker = item.get("ticker")
    match = TICKER.fullmatch(ticker) if isinstance(ticker, str) else None
    if match is None or item.get("status") != "active" or match[5] not in TEAM_CODES:
        return None
    if item.get("event_ticker") != ticker.rsplit("-", 1)[0]:
        return None
    bid, ask = item.get("yes_bid_dollars"), item.get("yes_ask_dollars")
    if not isinstance(bid, str) or not isinstance(ask, str):
        return None
    if PRICE.fullmatch(bid) is None or PRICE.fullmatch(ask) is None:
        return None
    bid_value, ask_value = float(bid), float(ask)
    if not 0 < bid_value <= ask_value < 1:
        return None
    return Market(item["event_ticker"], match[5], bid_value, ask_value, _time(item.get("updated_time")))


def parse_markets(data: Any) -> list[Market]:
    if not isinstance(data, dict) or not isinstance(data.get("markets"), list) or len(data["markets"]) > 500:
        raise ValueError("shape")
    items = data["markets"]
    if items and not any(isinstance(item, dict) for item in items):
        raise ValueError("shape")
    markets = [_market(item) for item in items if isinstance(item, dict)]
    usable = [market for market in markets if market is not None]
    if len(items) >= SHAPE_FAILURE_THRESHOLD and not usable:
        raise ValueError("shape")
    return usable


def event_parts(event_ticker: str) -> tuple[date, tuple[str, str]] | None:
    match = TICKER.fullmatch(event_ticker + "-ARI")
    if match is None or match[2] not in MONTHS:
        return None
    try:
        game_date = date(2000 + int(match[1]), MONTHS[match[2]], int(match[3]))
    except ValueError:
        return None
    middle = match[4]
    splits = [
        (middle[:n], middle[n:])
        for n in (2, 3)
        if middle[:n] in TEAM_CODES and middle[n:] in TEAM_CODES and middle[:n] != middle[n:]
    ]
    return (game_date, splits[0]) if len(splits) == 1 else None
