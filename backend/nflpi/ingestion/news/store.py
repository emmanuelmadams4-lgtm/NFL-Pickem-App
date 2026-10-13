"""Store deduplicated news items in step 8f."""

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nflpi.ingestion.news import match, parse
from nflpi.models import NewsItem

KEEP_DAYS = 30


def store_items(
    session: Session, source_id: str, items: list[parse.Item], names: match.Names, fetched_at: datetime
) -> int:
    added = 0
    for item in items:
        tied = match.tie(item.title, item.extract, names)
        stmt = insert(NewsItem).values(
            source=source_id,
            title=item.title,
            title_sha256=hashlib.sha256(item.title.encode()).hexdigest(),
            url_canonical=item.url,
            published_at=item.published_at,
            fetched_at=fetched_at,
            extract=item.extract,
            team_ids=tied.team_ids,
            player_ids=tied.player_ids,
            tags=tied.tags,
        )
        added += session.execute(stmt.on_conflict_do_nothing()).rowcount
    session.commit()
    return added


def prune(session: Session, now: datetime) -> int:
    result = session.execute(delete(NewsItem).where(NewsItem.fetched_at < now - timedelta(days=KEEP_DAYS)))
    session.commit()
    return result.rowcount
