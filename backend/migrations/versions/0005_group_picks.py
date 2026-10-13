"""Add group picks and weekly standings."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_picks",
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.game_id"), primary_key=True),
        sa.Column("member", sa.String(64), primary_key=True),
        sa.Column("picked_team", sa.String(4), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "group_standings",
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("week", sa.Integer(), primary_key=True),
        sa.Column("member", sa.String(64), primary_key=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("group_standings")
    op.drop_table("group_picks")
