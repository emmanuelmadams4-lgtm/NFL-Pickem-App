"""API contract. TypeScript types for web and mobile are generated from these."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Uncertainty = Literal["low", "moderate", "high"]
GameStatus = Literal["scheduled", "in_progress", "final"]
Provider = Literal["claude", "jev"]


class TeamOut(BaseModel):
    abbr: str
    name: str
    nick: str
    conference: str
    division: str
    color: str
    color2: str
    logo_url: str


class Factor(BaseModel):
    key: str
    label: str
    detail: str
    favors: str
    weight: float = Field(description="Push on the home team's log-odds; sign shows direction")


class PredictionOut(BaseModel):
    id: int
    created_at: datetime
    kind: Literal["live", "backfill"]
    model_version: str
    home_win_prob: float
    away_win_prob: float
    pick: str
    uncertainty: Uncertainty
    uncertainty_reasons: list[str]
    factors: list[Factor]
    market_home_prob: float | None
    stats_only_home_prob: float | None
    upset_flags: list[str]
    change_note: str | None
    data_freshness: dict[str, str | None]


class WeatherOut(BaseModel):
    kind: Literal["forecast", "observed"]
    observed_at: datetime | None
    temp_f: float | None
    wind_mph: float | None
    gust_mph: float | None = None
    precip_prob: float | None = None
    precip_in: float | None = None


class GameSummary(BaseModel):
    game_id: str
    season: int
    week: int
    game_type: str
    kickoff_utc: datetime
    status: GameStatus
    away: TeamOut
    home: TeamOut
    away_score: int | None
    home_score: int | None
    away_record: str
    home_record: str
    stadium: str | None
    roof: str | None
    neutral_site: bool
    div_game: bool
    prediction: PredictionOut | None
    my_pick: str | None
    my_pick_correct: bool | None
    model_correct: bool | None
    locked: bool = Field(description="Kickoff has passed; picks can no longer change")
    qb_alerts: list[str]
    injury_count: int
    weather: WeatherOut | None


class DatasetFreshness(BaseModel):
    dataset: str
    last_success: datetime | None
    age_hours: float | None
    stale: bool
    last_error: str | None


class WeekSummary(BaseModel):
    games_total: int
    games_final: int
    games_remaining: int
    picks_made: int
    picks_correct: int
    picks_incorrect: int
    my_accuracy: float | None
    model_correct: int
    model_graded: int
    model_accuracy: float | None
    season_my_accuracy: float | None
    season_model_accuracy: float | None
    league_leader_accuracy: float | None
    attention: int = Field(description="Games with high uncertainty or an upset flag still to play")


class WeekOut(BaseModel):
    season: int
    week: int
    summary: WeekSummary
    games: list[GameSummary]
    freshness: list[DatasetFreshness]
    generated_at: datetime


class InjuryOut(BaseModel):
    team: str
    player: str
    position: str | None
    report_status: str | None
    practice_status: str | None
    injury: str | None
    observed_at: datetime


class MarketOut(BaseModel):
    observed_at: datetime
    kind: str
    source: str
    home_moneyline: float | None
    away_moneyline: float | None
    spread_line: float | None
    total_line: float | None
    home_prob: float | None


class TeamForm(BaseModel):
    team: str
    record: str
    home_record: str
    away_record: str
    points_for_pg: float | None
    points_against_pg: float | None
    last3_margin: float | None
    last5_margin: float | None
    elo: float | None
    qb: str | None
    prev_qb: str | None
    rest_days: int | None
    coach: str | None


class MeetingOut(BaseModel):
    game_id: str
    season: int
    week: int
    away_team: str
    home_team: str
    away_score: int | None
    home_score: int | None


class MatchupReport(BaseModel):
    """Validated AI output. The AI explains; it never sets the probability."""

    game_id: str
    recommended_winner: str
    statistical_win_probability: float = Field(ge=0, le=1)
    headline: str
    supporting_factors: list[str] = Field(min_length=1, max_length=6)
    opposing_factors: list[str] = Field(max_length=6)
    injury_impact: str
    rest_and_schedule: str
    weather_impact: str
    market_view: str
    key_uncertainties: list[str] = Field(max_length=6)
    what_would_change_the_pick: list[str] = Field(max_length=4)
    data_quality_warnings: list[str]
    sources: list[str] = Field(min_length=1, description="Evidence-pack keys the report relied on")


class AIReportOut(BaseModel):
    id: int
    created_at: datetime
    provider: str
    model: str
    status: Literal["ok", "failed"]
    report: MatchupReport | None
    error: str | None
    prediction_id: int | None


class GameDetail(GameSummary):
    home_form: TeamForm
    away_form: TeamForm
    injuries: list[InjuryOut]
    market_history: list[MarketOut]
    prediction_history: list[PredictionOut]
    meetings: list[MeetingOut]
    ai_report: AIReportOut | None
    coach_home: str | None
    coach_away: str | None
    surface: str | None
    weekday: str


class PickIn(BaseModel):
    team: str


class PickOut(BaseModel):
    game_id: str
    picked_team: str
    picked_at: datetime
    source: str


class ImportResult(BaseModel):
    imported: int
    skipped: list[str]


class WeekPerformance(BaseModel):
    week: int
    games_final: int
    my_correct: int
    my_total: int
    model_correct: int
    model_total: int
    model_first_correct: int
    model_first_total: int
    market_correct: int
    market_total: int
    home_correct: int
    home_total: int


class Tally(BaseModel):
    correct: int
    total: int
    accuracy: float | None
    ci_low: float | None
    ci_high: float | None


class CalibrationBucket(BaseModel):
    bucket: str
    n: int
    predicted: float | None
    observed: float | None


class PerformanceOut(BaseModel):
    season: int
    weeks: list[WeekPerformance]
    me: Tally
    model: Tally
    model_first: Tally
    market: Tally
    home: Tally
    model_live_games: int
    model_backfill_games: int
    calibration: list[CalibrationBucket]
    league_leader_accuracy: float | None


class BacktestModel(BaseModel):
    model: str
    label: str
    n: int
    accuracy: float
    accuracy_ci: list[float]
    brier: float
    log_loss: float


class BacktestOut(BaseModel):
    created_at: datetime
    seasons: list[int]
    games: int
    models: list[BacktestModel]
    comparisons: list[dict]
    ablations: list[dict]
    by_season: list[dict]
    calibration: dict[str, list[CalibrationBucket]]
    favorite_split: list[dict]


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    provider: Provider = "claude"


class AskOut(BaseModel):
    answer: str
    provider: str
    model: str
    created_at: datetime


class DeviceIn(BaseModel):
    token: str = Field(min_length=10, max_length=255)
    platform: Literal["ios", "android", "web"]


class SettingsIn(BaseModel):
    league_leader_accuracy: float | None = Field(default=None, ge=0, le=1)


class MetaOut(BaseModel):
    current_season: int
    current_week: int
    seasons: list[int]
    weeks: list[int]
    model_name: str | None
    model_trained_through: int | None
    ai_providers: dict[str, bool]
    push_devices: int
    league_leader_accuracy: float | None
    server_time: datetime


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    active_model: bool
    stale_datasets: list[str]
