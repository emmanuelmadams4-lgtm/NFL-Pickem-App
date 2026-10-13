"""Add weekly team stars."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_stars",
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("week", sa.Integer(), primary_key=True),
        sa.Column("team", sa.String(4), primary_key=True),
        sa.Column("slot", sa.String(4), primary_key=True),
        sa.Column("rank", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.String(16), nullable=True),
        sa.Column("player", sa.String(64), nullable=False),
        sa.Column("position", sa.String(8), nullable=True),
        sa.Column("snaps", sa.Integer(), nullable=False),
        sa.Column("production", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("team_stars")
