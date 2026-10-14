"""Grow the book_prices unique key: line and price join it, so an alternate line or a changed price kept."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

OLD = ("game_id", "sportsbook", "market_type", "selection", "observed_at")


def upgrade() -> None:
    op.drop_constraint("uq_book_prices_key", "book_prices", type_="unique")
    op.create_unique_constraint(
        "uq_book_prices_key", "book_prices", [*OLD, "line", "price"], postgresql_nulls_not_distinct=True
    )


def downgrade() -> None:
    # rows that differ only in line or price would collide on the old key: keep the first stored of each
    op.execute(
        "DELETE FROM book_prices a USING book_prices b WHERE a.id > b.id AND a.game_id = b.game_id"
        " AND a.sportsbook = b.sportsbook AND a.market_type = b.market_type AND a.selection = b.selection"
        " AND a.observed_at = b.observed_at"
    )
    op.drop_constraint("uq_book_prices_key", "book_prices", type_="unique")
    op.create_unique_constraint("uq_book_prices_key", "book_prices", list(OLD))
