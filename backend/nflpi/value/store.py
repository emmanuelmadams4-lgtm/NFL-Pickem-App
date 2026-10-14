"""Insert-only storage of book prices (table book_prices)."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.orm import Session

from nflpi.betting.odds import BettingError
from nflpi.betting.snapshot import MarketSnapshot
from nflpi.config import get_settings
from nflpi.models import BookPrice


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


def load_snapshots(session: Session, game_id: str, market_type: str, *, as_of: datetime) -> list[MarketSnapshot]:
    """Newest price per book and selection observed at or before as_of."""
    stmt = (
        select(BookPrice)
        .ext(distinct_on(BookPrice.sportsbook, BookPrice.selection))
        .where(BookPrice.game_id == game_id, BookPrice.market_type == market_type, BookPrice.observed_at <= as_of)
        .order_by(BookPrice.sportsbook, BookPrice.selection, BookPrice.observed_at.desc(), BookPrice.id.desc())
    )
    return [
        MarketSnapshot(r.game_id, r.sportsbook, r.observed_at, r.market_type, r.selection, r.line, "american", r.price)
        for r in session.scalars(stmt)
    ]
