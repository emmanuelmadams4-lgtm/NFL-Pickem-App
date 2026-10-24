"""Core database: declarative base, engine, and sessions for the App Store.

SQLite (single-user, PRD-approved). Separate from the Pick'em PostgreSQL instance.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app_store.config import get_settings

# SQLAlchemy declarative base for all App Store models
class Base(DeclarativeBase):
    pass

# SQLite settings: WAL for concurrent reads, check_same_thread=False for FastAPI
_SQLITE_ARGS = {"pool_pre_ping": True, "connect_args": {"check_same_thread": False}}

_engine: Engine


def _create_engine() -> Engine:
    url = get_settings().database_url
    return create_engine(url, **_SQLITE_ARGS)


@lru_cache
def get_engine() -> Engine:
    global _engine
    _engine = _create_engine()
    return _engine


def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


def init_db() -> None:
    """Create all tables."""
    from app_store.models import Base
    Base.metadata.create_all(bind=get_engine())
