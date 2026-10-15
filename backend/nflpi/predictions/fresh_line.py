"""Choose a recent pregame quote without changing historical market lines."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi.models import MarketQuote

FRESH_MAX_AGE = timedelta(minutes=30)
SANITY_GAP = 0.20
CHURN_GAP = 0.01
TARGETS = (timedelta(minutes=90), timedelta(minutes=20))
TARGET_SLACK = timedelta(minutes=1)


@dataclass(frozen=True)
class Line:
    prob: float | None
    source: str
    seen_at: datetime | None


@dataclass(frozen=True)
class Quote:
    source: str
    home_prob: float
    seen_at: datetime


def choose_line(
    nflverse: Line, quotes: list[Quote], previous: Line | None, *, now: datetime, kickoff: datetime,
) -> tuple[Line, Quote | None]:
    """Use the newest eligible quote, with sanity and small-move guards."""
    chosen = nflverse
    if now < kickoff:
        eligible = [
            quote for quote in quotes
            if quote.seen_at <= now
            and quote.seen_at < kickoff
            and now - quote.seen_at <= FRESH_MAX_AGE
            and math.isfinite(quote.home_prob)
            and 0 < quote.home_prob < 1
            and 0 < round(quote.home_prob, 4) < 1
            and (nflverse.seen_at is None or quote.seen_at > nflverse.seen_at)
        ]
        if eligible:
            quote = sorted(eligible, key=lambda item: (-item.seen_at.timestamp(), item.source))[0]
            quote_prob = round(quote.home_prob, 4)
            if nflverse.prob is not None and (
                abs(quote_prob - nflverse.prob) > SANITY_GAP
                or math.isclose(abs(quote_prob - nflverse.prob), SANITY_GAP, abs_tol=1e-12)
            ):
                return nflverse, quote
            chosen = Line(quote_prob, quote.source, quote.seen_at)
    if (
        previous is not None
        and previous.prob is not None
        and chosen.prob is not None
        and (chosen.source != "nflverse" or previous.source != "nflverse")
        and (previous.source == "nflverse" or (
            previous.seen_at is not None and now - previous.seen_at <= FRESH_MAX_AGE
        ))
        and abs(chosen.prob - previous.prob) < CHURN_GAP
    ):
        return previous, None
    return chosen, None


def fair_moneylines(p: float) -> tuple[float, float]:
    """Return American odds with no bookmaker margin."""
    def moneyline(prob: float) -> float:
        return -100 * prob / (1 - prob) if prob >= 0.5 else 100 * (1 - prob) / prob

    return moneyline(p), moneyline(1 - p)


def rank_changed(old: dict[str, float], new: dict[str, float], game_id: str) -> bool:
    def rank(probs: dict[str, float]) -> int:
        return sorted(probs, key=lambda gid: (-max(probs[gid], 1 - probs[gid]), gid)).index(game_id)

    return rank(old) != rank(new)


def until_next_target(kickoffs: list[datetime], now: datetime) -> timedelta | None:
    remaining = [kickoff - target - now for kickoff in kickoffs for target in TARGETS if kickoff - target > now]
    return min(remaining) + TARGET_SLACK if remaining else None


def pregame_quotes(session: Session, game_ids: list[str], now: datetime) -> dict[str, list[Quote]]:
    """Read all recent pregame quotes for the candidate games in one query."""
    if not game_ids:
        return {}
    rows = session.scalars(
        select(MarketQuote).where(
            MarketQuote.game_id.in_(game_ids),
            MarketQuote.kind == "pregame",
            MarketQuote.fetched_at >= now - FRESH_MAX_AGE,
            MarketQuote.fetched_at <= now,
        )
    )
    quotes: dict[str, list[Quote]] = {}
    for row in rows:
        if row.home_prob is not None:
            quotes.setdefault(row.game_id, []).append(Quote(row.source, row.home_prob, row.fetched_at))
    return quotes
