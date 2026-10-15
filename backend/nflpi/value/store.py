"""Insert-only storage of book prices (table book_prices)."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nflpi.betting.odds import BettingError
from nflpi.betting.snapshot import MarketSnapshot
from nflpi.config import get_settings
from nflpi.models import BookPrice

SIDES = {"moneyline": ("home", "away"), "spread": ("home", "away"), "total": ("over", "under")}


def max_price_age() -> timedelta:
    return timedelta(minutes=get_settings().value_max_price_age_minutes)


def _build(game_id: str, sportsbook: str, observed_at: datetime, quote: Mapping) -> MarketSnapshot:
    try:
        return MarketSnapshot(
            game_id,
            sportsbook,
            observed_at,
            quote["market_type"],
            quote["selection"],
            quote["line"],
            "american",
            quote["price"],
        )
    except (KeyError, TypeError) as exc:
        raise BettingError(f"malformed quote: {exc!r}") from exc


def save_prices(
    session: Session,
    game_id: str,
    sportsbook: str,
    observed_at: datetime,
    fetched_at: datetime,
    quotes: Iterable[Mapping],
) -> int:
    """Insert validated quotes; a key already stored is skipped, never updated. Returns rows inserted."""
    snaps = [_build(game_id, sportsbook, observed_at, quote) for quote in quotes]
    if not isinstance(fetched_at, datetime) or fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise BettingError("fetched_at must be a timezone-aware datetime")
    if observed_at > fetched_at:
        raise BettingError("observed_at is later than fetched_at")
    if not snaps:
        return 0
    values = [
        {
            "game_id": s.game_id,
            "sportsbook": s.sportsbook,
            "market_type": s.market_type,
            "selection": s.selection,
            "line": s.line,
            "price": s.price,
            "observed_at": s.observed_at,
            "fetched_at": fetched_at,
        }
        for s in snaps
    ]
    stmt = insert(BookPrice).values(values).on_conflict_do_nothing(constraint="uq_book_prices_key")
    inserted = session.execute(stmt.returning(BookPrice.id)).all()
    session.flush()
    return len(inserted)


def _snapshot(r: BookPrice) -> MarketSnapshot:
    return MarketSnapshot(
        r.game_id, r.sportsbook, r.observed_at, r.market_type, r.selection, r.line, "american", r.price
    )


def load_snapshots(session: Session, game_id: str, market_type: str, *, as_of: datetime) -> list[MarketSnapshot]:
    """Per book, the newest complete pair (both sides, one observed time, one line) at or before as_of.

    A side seen at a different time or line than its partner is never paired, and a lone side is never returned.
    Among pairs at the newest time (alternate lines) the most recently fetched one wins.
    """
    sides = SIDES[market_type] if market_type in SIDES else ()
    if not sides:
        return []
    newest_side = select(
        BookPrice.id, BookPrice.sportsbook, BookPrice.observed_at, BookPrice.line,
        BookPrice.selection, BookPrice.fetched_at,
        func.row_number().over(
            partition_by=(BookPrice.sportsbook, BookPrice.observed_at, BookPrice.line, BookPrice.selection),
            order_by=(BookPrice.fetched_at.desc(), BookPrice.id.desc()),
        ).label("side_rank"),
    ).where(
        BookPrice.game_id == game_id, BookPrice.market_type == market_type, BookPrice.observed_at <= as_of,
    ).subquery()
    complete = select(
        newest_side.c.sportsbook, newest_side.c.observed_at, newest_side.c.line,
        func.array_agg(newest_side.c.id).label("ids"),
        func.max(newest_side.c.fetched_at).label("last_fetched"),
        func.max(newest_side.c.id).label("last_id"),
    ).where(newest_side.c.side_rank == 1).group_by(
        newest_side.c.sportsbook, newest_side.c.observed_at, newest_side.c.line,
    ).having(func.count(newest_side.c.selection) == len(sides)).subquery()
    best = select(
        complete.c.sportsbook, complete.c.ids,
        func.row_number().over(
            partition_by=complete.c.sportsbook,
            order_by=(complete.c.observed_at.desc(), complete.c.last_fetched.desc(), complete.c.last_id.desc()),
        ).label("pair_rank"),
    ).subquery()
    chosen = session.execute(select(best.c.sportsbook, best.c.ids).where(best.c.pair_rank == 1)).all()
    if not chosen:
        return []
    ids = [id_ for _, pair_ids in chosen for id_ in pair_ids]
    rows = {row.id: row for row in session.scalars(select(BookPrice).where(BookPrice.id.in_(ids)))}
    pairs = {book: {rows[id_].selection: rows[id_] for id_ in pair_ids} for book, pair_ids in chosen}
    return [_snapshot(pairs[book][side]) for book in sorted(pairs) for side in sides]
