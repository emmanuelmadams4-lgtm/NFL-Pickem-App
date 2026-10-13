"""Add live state, market quotes, and source status tables."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
# Integrator will re-point this at landing; main has no 0004/0005 yet.
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("espn_event_id", sa.String(16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(4), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("clock", sa.String(8), nullable=True),
        sa.Column("home_wp", sa.Float(), nullable=True),
        sa.Column("tie_wp", sa.Float(), nullable=True),
        sa.Column("last_play_id", sa.String(24), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.game_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_game", "live_states", ["game_id", "id"])
    op.create_table(
        "market_quotes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("home_prob", sa.Float(), nullable=True),
        sa.Column("away_prob", sa.Float(), nullable=True),
        sa.Column("raw_yes_bid", sa.Float(), nullable=True),
        sa.Column("raw_yes_ask", sa.Float(), nullable=True),
        sa.Column("overround", sa.Float(), nullable=True),
        sa.Column("home_ml", sa.Float(), nullable=True),
        sa.Column("away_ml", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ts", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.game_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotes_game_source", "market_quotes", ["game_id", "source", "id"])
    op.create_table(
        "source_status",
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(200), nullable=True),
        sa.Column("credits_left", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source"),
    )


def downgrade() -> None:
    op.drop_index("ix_quotes_game_source", table_name="market_quotes")
    op.drop_index("ix_live_game", table_name="live_states")
    op.drop_table("source_status")
    op.drop_table("market_quotes")
    op.drop_table("live_states")
