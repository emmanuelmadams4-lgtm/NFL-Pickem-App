import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nflpi.config import get_settings

REFRESH_LOCK_KEY: int = 0x4E464C5049
log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


def acquire_refresh_lock() -> Connection | None:
    conn = get_engine().connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        if conn.scalar(text("select pg_try_advisory_lock(:k)"), {"k": REFRESH_LOCK_KEY}):
            return conn
        log.info("refresh skipped: advisory lock is held")
        conn.close()
        return None
    except Exception:
        conn.close()
        raise


def release_refresh_lock(conn: Connection) -> None:
    try:
        conn.execute(text("select pg_advisory_unlock(:k)"), {"k": REFRESH_LOCK_KEY})
    except Exception:
        conn.invalidate()
        raise
    finally:
        conn.close()
