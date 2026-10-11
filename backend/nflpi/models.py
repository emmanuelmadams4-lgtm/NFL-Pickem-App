"""Database tables. Predictions are insert-only snapshots; results live on games."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from nflpi.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Team(Base):
    __tablename__ = "teams"
    abbr: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    nick: Mapped[str] = mapped_column(String(32))
    conference: Mapped[str] = mapped_column(String(3))
    division: Mapped[str] = mapped_column(String(16))
    color: Mapped[str] = mapped_column(String(9))
    color2: Mapped[str] = mapped_column(String(9))
    logo_url: Mapped[str] = mapped_column(String(255))


class Game(Base):
    __tablename__ = "games"
    game_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    game_type: Mapped[str] = mapped_column(String(4))
    kickoff_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    weekday: Mapped[str] = mapped_column(String(10))
    away_team: Mapped[str] = mapped_column(String(4))
    home_team: Mapped[str] = mapped_column(String(4))
    away_score: Mapped[int | None] = mapped_column(Integer)
    home_score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))  # scheduled | final
    neutral_site: Mapped[bool] = mapped_column(Boolean, default=False)
    div_game: Mapped[bool] = mapped_column(Boolean, default=False)
    roof: Mapped[str | None] = mapped_column(String(12))
    surface: Mapped[str | None] = mapped_column(String(24))
    stadium: Mapped[str | None] = mapped_column(String(64))
    stadium_id: Mapped[str | None] = mapped_column(String(8))
    away_rest: Mapped[int | None] = mapped_column(Integer)
    home_rest: Mapped[int | None] = mapped_column(Integer)
    away_qb: Mapped[str | None] = mapped_column(String(64))
    home_qb: Mapped[str | None] = mapped_column(String(64))
    away_coach: Mapped[str | None] = mapped_column(String(64))
    home_coach: Mapped[str | None] = mapped_column(String(64))
    temp_f: Mapped[float | None] = mapped_column(Float)
    wind_mph: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_games_season_week", "season", "week"),
        Index("ix_games_kickoff", "kickoff_utc"),
    )


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(8))  # latest | closing
    home_moneyline: Mapped[float | None] = mapped_column(Float)
    away_moneyline: Mapped[float | None] = mapped_column(Float)
    spread_line: Mapped[float | None] = mapped_column(Float)
    total_line: Mapped[float | None] = mapped_column(Float)
    home_prob_novig: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("game_id", "source", "observed_at", name="uq_market_obs"),
        Index("ix_market_game", "game_id", "observed_at"),
    )


class InjuryReport(Base):
    __tablename__ = "injury_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    team: Mapped[str] = mapped_column(String(4))
    player_id: Mapped[str | None] = mapped_column(String(16))
    player: Mapped[str] = mapped_column(String(64))
    position: Mapped[str | None] = mapped_column(String(8))
    report_status: Mapped[str | None] = mapped_column(String(16))
    practice_status: Mapped[str | None] = mapped_column(String(48))
    injury: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_injury_week_team", "season", "week", "team"),)


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temp_f: Mapped[float | None] = mapped_column(Float)
    wind_mph: Mapped[float | None] = mapped_column(Float)
    gust_mph: Mapped[float | None] = mapped_column(Float)
    precip_prob: Mapped[float | None] = mapped_column(Float)
    precip_in: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))

    __table_args__ = (Index("ix_weather_game", "game_id", "observed_at"),)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSON)
    trained_through_season: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(10), default="live")  # live | backfill
    home_win_prob: Mapped[float] = mapped_column(Float)
    pick: Mapped[str] = mapped_column(String(4))
    features: Mapped[dict] = mapped_column(JSON)
    factors: Mapped[list] = mapped_column(JSON)
    uncertainty: Mapped[str] = mapped_column(String(10))
    uncertainty_reasons: Mapped[list] = mapped_column(JSON, default=list)
    market_home_prob: Mapped[float | None] = mapped_column(Float)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    data_freshness: Mapped[dict] = mapped_column(JSON, default=dict)
    change_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_pred_game_created", "game_id", "created_at"),)


class UserPick(Base):
    __tablename__ = "user_picks"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    picked_team: Mapped[str] = mapped_column(String(4))
    picked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(8), default="app")  # app | csv


class AIReport(Base):
    __tablename__ = "ai_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"))
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"))
    kind: Mapped[str] = mapped_column(String(8), default="report")  # report | answer
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(10))  # ok | failed
    question: Mapped[str | None] = mapped_column(Text)
    report: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_ai_game_created", "game_id", "created_at"),)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))
    dataset: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10))  # running | ok | failed
    rows: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_ingest_dataset", "dataset", "started_at"),)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    config: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)


class PushSubscription(Base):
    """A browser/PWA Web Push subscription (iPhone Home Screen app, desktop browser)."""

    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16))
    game_id: Mapped[str | None] = mapped_column(String(32))
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
