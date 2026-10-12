"""Create the initial database schema, including the games.time_tbd flag."""

from alembic import op

from nflpi import models  # noqa: F401 - registers all mapped tables
from nflpi.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
