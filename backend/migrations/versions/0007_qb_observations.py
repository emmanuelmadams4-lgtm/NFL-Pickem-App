"""Add the quarterback observation history table."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
# Numbers are taken at landing time: 0007 was the next free number on this branch (0006 = live state and quotes).
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qb_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("qb", sa.String(64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.game_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qb_obs_game", "qb_observations", ["game_id", "side", "id"])


def downgrade() -> None:
    op.drop_index("ix_qb_obs_game", table_name="qb_observations")
    op.drop_table("qb_observations")
