"""Choose a recent pregame quote without changing historical market lines."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.config import get_settings
from nflpi.models import IngestionRun, MarketQuote

FRESH_MAX_AGE = timedelta(minutes=30)
SANITY_GAP = 0.20
CHURN_GAP = 0.01
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
    reference = nflverse if previous is not None and previous.source == "nflverse" else previous
    if (
        previous is not None
        and reference is not None and reference.prob is not None
        and chosen.prob is not None
        and (chosen.source != "nflverse" or previous.source != "nflverse")
        and (previous.source == "nflverse" or (
            previous.seen_at is not None and now - previous.seen_at <= FRESH_MAX_AGE
        ))
        and abs(chosen.prob - reference.prob) < CHURN_GAP
    ):
        return reference, None
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
    targets = (timedelta(minutes=90), timedelta(minutes=get_settings().pick_lock_minutes + 15))
    remaining = [kickoff - target - now for kickoff in kickoffs for target in targets if kickoff - target > now]
    return min(remaining) + TARGET_SLACK if remaining else None


def pregame_quotes(session: Session, game_ids: list[str], now: datetime) -> dict[str, list[Quote]]:
    """Read the latest pregame price per game and source, using successful polls to date a stable price."""
    if not game_ids:
        return {}
    latest = select(
        MarketQuote.id,
        func.row_number().over(
            partition_by=(MarketQuote.game_id, MarketQuote.source),
            order_by=(MarketQuote.fetched_at.desc(), MarketQuote.id.desc()),
        ).label("rank"),
    ).where(
        MarketQuote.game_id.in_(game_ids), MarketQuote.kind == "pregame", MarketQuote.fetched_at <= now,
    ).subquery()
    rows = session.scalars(
        select(MarketQuote).join(latest, MarketQuote.id == latest.c.id).where(latest.c.rank == 1)
    ).all()
    if not rows:
        return {}
    last_polls = dict(session.execute(
        select(IngestionRun.source, func.max(IngestionRun.finished_at)).where(
            IngestionRun.dataset == "market_quotes", IngestionRun.status == "ok",
            IngestionRun.source.in_({row.source for row in rows}),
            IngestionRun.finished_at <= now,
            IngestionRun.finished_at >= min(row.fetched_at for row in rows),
        ).group_by(IngestionRun.source)
    ))
    quotes: dict[str, list[Quote]] = {}
    for row in rows:
        poll = last_polls.get(row.source)
        seen_at = poll if poll is not None and poll >= row.fetched_at else row.fetched_at
        # ponytail: a vanished market can look current while polls succeed; upgrade with per-game confirmation.
        if row.home_prob is not None and now - seen_at <= FRESH_MAX_AGE:
            quotes.setdefault(row.game_id, []).append(Quote(row.source, row.home_prob, seen_at))
    return quotes
