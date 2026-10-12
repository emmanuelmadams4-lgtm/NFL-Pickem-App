"""Add pick sheet and weekly ranks."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pick_points",
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.game_id"), primary_key=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sheet_entries",
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.game_id"), primary_key=True),
        sa.Column("app_pick", sa.String(4), nullable=False),
        sa.Column("app_prob", sa.Float(), nullable=False),
        sa.Column("label", sa.String(16), nullable=False),
        sa.Column("app_points", sa.Integer(), nullable=True),
        sa.Column("my_pick", sa.String(4), nullable=False),
        sa.Column("my_points", sa.Integer(), nullable=True),
        sa.Column("pick_by", sa.String(8), nullable=False),
        sa.Column("points_by", sa.String(8), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "weekly_ranks",
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("week", sa.Integer(), primary_key=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("leader_points", sa.Integer(), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("weekly_ranks")
    op.drop_table("sheet_entries")
    op.drop_table("pick_points")
