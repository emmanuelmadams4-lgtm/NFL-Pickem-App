"""Database tables. Predictions are insert-only snapshots; results live on games."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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
    time_tbd: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    weekday: Mapped[str] = mapped_column(String(10))
    away_team: Mapped[str] = mapped_column(String(4))
    home_team: Mapped[str] = mapped_column(String(4))
    away_score: Mapped[int | None] = mapped_column(Integer)
    home_score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))  # scheduled | postponed | final
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


class TeamStar(Base):
    """The five stars of a club for one week, ranked from that season's earlier weeks only."""

    __tablename__ = "team_stars"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, primary_key=True)
    team: Mapped[str] = mapped_column(String(4), primary_key=True)
    slot: Mapped[str] = mapped_column(String(4), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str | None] = mapped_column(String(16))
    player: Mapped[str] = mapped_column(String(64))
    position: Mapped[str | None] = mapped_column(String(8))
    snaps: Mapped[int] = mapped_column(Integer)
    production: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    source: Mapped[str] = mapped_column(String(8), default="app")  # app | csv | auto


class PickPoint(Base):
    __tablename__ = "pick_points"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    points: Mapped[int] = mapped_column(Integer)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SheetEntry(Base):
    __tablename__ = "sheet_entries"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    app_pick: Mapped[str] = mapped_column(String(4))
    app_prob: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(16))
    app_points: Mapped[int | None] = mapped_column(Integer)
    my_pick: Mapped[str] = mapped_column(String(4))
    my_points: Mapped[int | None] = mapped_column(Integer)
    pick_by: Mapped[str] = mapped_column(String(8))
    points_by: Mapped[str] = mapped_column(String(8))
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WeeklyRank(Base):
    __tablename__ = "weekly_ranks"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)
    leader_points: Mapped[int | None] = mapped_column(Integer)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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


class GroupPick(Base):
    __tablename__ = "group_picks"
    game_id: Mapped[str] = mapped_column(String(32), ForeignKey("games.game_id"), primary_key=True)
    member: Mapped[str] = mapped_column(String(64), primary_key=True)
    picked_team: Mapped[str | None] = mapped_column(String(4))
    confidence: Mapped[int | None] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupStanding(Base):
    __tablename__ = "group_standings"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, primary_key=True)
    member: Mapped[str] = mapped_column(String(64), primary_key=True)
    points: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    title_sha256: Mapped[str] = mapped_column(String(64))
    url_canonical: Mapped[str] = mapped_column(String(2048))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extract: Mapped[str] = mapped_column(String(300))
    team_ids: Mapped[list[str]] = mapped_column(JSON)
    player_ids: Mapped[list[str]] = mapped_column(JSON)
    tags: Mapped[list[str]] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("url_canonical", name="uq_news_url"),
        UniqueConstraint("source", "title_sha256", name="uq_news_source_title"),
        Index("ix_news_fetched", "fetched_at"),
    )


class LiveState(Base):
    """Insert-only live game state snapshots."""

    __tablename__ = "live_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), nullable=False)
    espn_event_id: Mapped[str] = mapped_column(String(16), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(4), nullable=False)  # pre | in | post | lost (left the scoreboard)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    period: Mapped[int | None] = mapped_column(Integer)
    clock: Mapped[str | None] = mapped_column(String(8))
    home_wp: Mapped[float | None] = mapped_column(Float)
    tie_wp: Mapped[float | None] = mapped_column(Float)
    last_play_id: Mapped[str | None] = mapped_column(String(24))

    __table_args__ = (Index("ix_live_game", "game_id", "id"),)


class MarketQuote(Base):
    """Insert-only market quote snapshots."""

    __tablename__ = "market_quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # pregame | live
    home_prob: Mapped[float | None] = mapped_column(Float)
    away_prob: Mapped[float | None] = mapped_column(Float)
    raw_yes_bid: Mapped[float | None] = mapped_column(Float)
    raw_yes_ask: Mapped[float | None] = mapped_column(Float)
    overround: Mapped[float | None] = mapped_column(Float)
    home_ml: Mapped[float | None] = mapped_column(Float)
    away_ml: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_quotes_game_source", "game_id", "source", "id"),)


class SourceStatus(Base):
    """One mutable row per source (back-off and credit memory)."""

    __tablename__ = "source_status"
    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(200))
    credits_left: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QbObservation(Base):
    """A club's projected starting quarterback as our ingestion saw it.

    A row is appended only when the name changes (games.home_qb/away_qb are overwritten each run, so the history
    lives here).
    """

    __tablename__ = "qb_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"))
    side: Mapped[str] = mapped_column(String(4))  # home | away
    qb: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_qb_obs_game", "game_id", "side", "id"),)


class PasskeyCredential(Base):
    """A WebAuthn passkey the owner registered (public key only)."""

    __tablename__ = "passkey_credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_id: Mapped[str] = mapped_column(String(1400), unique=True)  # base64url, unpadded
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    sign_count: Mapped[int] = mapped_column(BigInteger)
    label: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasskeyChallenge(Base):
    """A live, single-use WebAuthn challenge (only the sha256 of its raw bytes is kept)."""

    __tablename__ = "passkey_challenges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_hash: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(8))  # register | signin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PasskeySession(Base):
    """A sign-in made with a passkey (only the sha256 of the session value is kept)."""

    __tablename__ = "passkey_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    credential_id: Mapped[int] = mapped_column(ForeignKey("passkey_credentials.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
