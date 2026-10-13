"""Add guarded news feed items."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("title_sha256", sa.String(64), nullable=False),
        sa.Column("url_canonical", sa.String(2048), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extract", sa.String(300), nullable=False),
        sa.Column("team_ids", sa.JSON(), nullable=False),
        sa.Column("player_ids", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.UniqueConstraint("url_canonical", name="uq_news_url"),
        sa.UniqueConstraint("source", "title_sha256", name="uq_news_source_title"),
    )
    op.create_index("ix_news_fetched", "news_items", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_news_fetched", table_name="news_items")
    op.drop_table("news_items")
