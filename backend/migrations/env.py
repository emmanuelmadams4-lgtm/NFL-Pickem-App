from alembic import context

from nflpi import models  # noqa: F401 - registers tables
from nflpi.db import Base, get_engine

target_metadata = Base.metadata

with get_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
