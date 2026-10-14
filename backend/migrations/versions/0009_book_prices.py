"""Add book_prices: insert-only prices per book, market and selection with the book's own time."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "book_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("sportsbook", sa.String(24), nullable=False),
        sa.Column("market_type", sa.String(9), nullable=False),
        sa.Column("selection", sa.String(5), nullable=False),
        sa.Column("line", sa.Float(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.game_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id", "sportsbook", "market_type", "selection", "observed_at", name="uq_book_prices_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("book_prices")
