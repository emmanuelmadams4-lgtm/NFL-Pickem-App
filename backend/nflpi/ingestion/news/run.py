"""Poll each news source and record its outcome."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi.ingestion.news import fetch, match, parse, sources, store
from nflpi.models import AppSetting, IngestionRun

log = logging.getLogger(__name__)

POLL_MINUTES = 30
BLOCK_HOURS = 24


def run_news(
    session: Session,
    *,
    now: datetime | None = None,
    resolver=None,
    transport=None,
    sources=sources.SOURCES,
) -> list[IngestionRun]:
    now = now if now is not None else datetime.now(UTC)
    resolver = resolver if resolver is not None else fetch.default_resolver
    names = match.load_names(session)
    made: list[IngestionRun] = []
    for src in sources:
        dataset = f"news:{src.id}"
        latest = session.scalars(
            select(IngestionRun)
            .where(IngestionRun.dataset == dataset)
            .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
            .limit(1)
        ).first()
        if latest and (
            latest.started_at > now - timedelta(minutes=POLL_MINUTES)
            or (
                (latest.error or "").startswith("blocked:")
                and latest.started_at > now - timedelta(hours=BLOCK_HOURS)
            )
        ):
            continue

        run = IngestionRun(source=src.id, dataset=dataset, started_at=now, status="running")
        session.add(run)
        session.commit()
        try:
            setting = session.get(AppSetting, f"{dataset}:validators")
            validators = setting.value if setting else None
            result = fetch.fetch_feed(src, resolver=resolver, transport=transport, validators=validators)
            if result.status == 304:
                run.rows = 0
                store.prune(session, now)
            else:
                items = parse.parse_feed(result.body, src, now)
                run.rows = store.store_items(session, src.id, items, names, now)
                if result.etag is not None or result.last_modified is not None:
                    session.merge(
                        AppSetting(
                            key=f"{dataset}:validators",
                            value={"etag": result.etag, "last_modified": result.last_modified},
                        )
                    )
                elif setting is not None:
                    session.delete(setting)
                store.prune(session, now)
            run.status = "ok"
        except fetch.Blocked as exc:
            session.rollback()
            run.status = "failed"
            run.error = parse.clean_text(f"blocked: {exc}", 100)
        except (fetch.FetchError, parse.FeedError) as exc:
            session.rollback()
            log.warning("news %s: %s", src.id, exc)
            run.status = "failed"
            run.error = parse.clean_text(str(exc), 100)
        except Exception as exc:  # noqa: BLE001 - log and continue to the next source
            session.rollback()
            log.exception("news ingestion failed for %s", src.id)
            run.status = "failed"
            run.error = parse.clean_text(f"unexpected: {type(exc).__name__}", 100)
        run.finished_at = datetime.now(UTC)
        session.add(run)
        session.commit()
        made.append(run)
    return made
