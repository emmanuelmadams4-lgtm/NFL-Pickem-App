"""API contract. TypeScript types for web are generated from these."""

import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

Uncertainty = Literal["low", "moderate", "high"]
GameStatus = Literal["scheduled", "postponed", "in_progress", "final"]
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


class SimulationOut(BaseModel):
    source: str
    distribution: str
    n_simulations: int
    home_points: float
    away_points: float
    home_win: float
    away_win: float
    tie: float
    expected_margin: float
    expected_total: float
    margin_80: list[float]
    total_80: list[float]
    home_spread: float | None
    total: float | None
    home_cover: float | None
    away_cover: float | None
    spread_push: float | None
    over: float | None
    under: float | None
    total_push: float | None
    label: str


class SimulationCheckOut(BaseModel):
    status: Literal["failed", "no_verdict", "not_checked"]
    note: str
    cause: str | None = None  # why there was no verdict: cap, provider, unparsed or error


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
    simulation: SimulationOut | None = None
    simulation_check: SimulationCheckOut | None = None  # set when the run check blocked this run's simulation


class WeatherOut(BaseModel):
    kind: Literal["forecast", "observed"]
    observed_at: datetime | None
    temp_f: float | None
    wind_mph: float | None
    gust_mph: float | None = None
    precip_prob: float | None = None
    precip_in: float | None = None


class SheetOut(BaseModel):
    label: str | None
    label_hit_rate: float | None
    app_pick: str | None
    app_points: int | None
    my_pick: str | None
    my_points: int | None
    pick_by: Literal["app", "user", "auto", "csv"]
    points_by: Literal["app", "user"]
    differs: bool


class StarStatus(BaseModel):
    team: str
    player: str
    position: str | None
    slot: Literal["qb", "off", "def"]
    rank: int
    status: str | None
    listed: bool
    qb_alert: bool
    injury: str | None
    observed_at: datetime | None


class StarsOut(BaseModel):
    out: list[StarStatus]
    no_list: list[str]
    reports_seen: int
    checked_at: datetime | None


class TeamStars(BaseModel):
    team: str
    stars_week: int | None
    stars: list[StarStatus]


class GameSummary(BaseModel):
    game_id: str
    season: int
    week: int
    game_type: str
    kickoff_utc: datetime
    time_tbd: bool
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
    sheet: SheetOut
    my_pick: str | None
    my_pick_correct: bool | None
    model_correct: bool | None
    locked: bool = Field(description="Known kickoff has passed; picks can no longer change")
    qb_not_projected: bool
    qb_alerts: list[str]
    injury_count: int
    stars_out: StarsOut
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


class PickModeOut(BaseModel):
    mode: Literal["straight_up", "confidence_pool"]
    assumed: bool
    label: str


class WeekOut(BaseModel):
    season: int
    week: int
    pick_mode: PickModeOut
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


class ValueRatingOut(BaseModel):
    market_type: Literal["moneyline", "spread", "total"]
    selection: str
    sportsbook: str
    line: float | None
    price: float
    observed_at: datetime
    status: Literal["RATED", "UNRATED", "NO_BET"]
    stars: int | None
    expected_value: float = Field(allow_inf_nan=False)
    reasons: list[str]
    note: str


class GameDetail(GameSummary):
    home_form: TeamForm
    away_form: TeamForm
    injuries: list[InjuryOut]
    stars: list[TeamStars]
    market_history: list[MarketOut]
    value_ratings: list[ValueRatingOut] = []
    prediction_history: list[PredictionOut]
    meetings: list[MeetingOut]
    ai_report: AIReportOut | None
    coach_home: str | None
    coach_away: str | None
    surface: str | None
    weekday: str


class PickIn(BaseModel):
    game_id: str | None = Field(default=None, description="Optional. If sent, must match the game in the URL.")
    team: str
    source: Literal["manual", "auto"] = Field(default="auto", description="Who set this pick: manual or auto (app)")
    week: int | None = Field(default=None, ge=1, description="Optional. If sent, must match the game's week.")
    rank: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Confidence rank 1..N for the week (FR-007). When provided, must be unique among all picks "
            "for the same week. Omit to use the app's suggested confidence."
        ),
    )


class PointsIn(BaseModel):
    week: int | None = Field(default=None, ge=1, description="Optional. The game in the URL decides the week.")
    points: int = Field(ge=0, description="Total planned points for the week")


class RankIn(BaseModel):
    rank: int = Field(ge=1, description="Rank of this game within the week's slack/favorite ranking")
    leader_points: int | None = Field(
        default=None, ge=0, description="Points needed to lead the league (must be <= max league points)"
    )
    week: int | None = Field(default=None, ge=1, description="Optional. The week in the URL is the one used.")


class PickOut(BaseModel):
    game_id: str
    picked_team: str
    confidence: int | None = Field(
        default=None,
        description=(
            "Confidence rank 1..N for the week (FR-007). Null when the user has not set a rank, "
            "and the app's suggestion is shown separately."
        ),
    )
    picked_at: datetime
    source: str = "app"
    rank: int | None = Field(default=None, description="Confidence rank 1..N for the week")


class ImportResult(BaseModel):
    imported: int
    skipped: list[str]


class WeekPerformance(BaseModel):
    week: int
    games_final: int
    my_correct: int
    my_total: int
    auto_correct: int
    auto_total: int
    model_live_correct: int
    model_live_total: int
    model_backfill_correct: int
    model_backfill_total: int
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
    auto: Tally
    model: Tally = Field(description="Live predictions only: the final snapshot was made before kickoff")
    model_backfill: Tally = Field(description="Backfill predictions only: computed after the fact, labeled")
    market: Tally
    home: Tally
    model_live_games: int
    model_backfill_games: int
    calibration: list[CalibrationBucket] = Field(description="Live predictions only")
    calibration_backfill: list[CalibrationBucket] = Field(description="Backfill predictions only: labeled")
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
    labels: list[dict] = []


class ScorecardWeek(BaseModel):
    week: int
    games: int
    max_points: int
    my_points: int
    app_points: int
    my_correct: int
    app_correct: int
    changed: int
    changed_right: int
    changed_wrong: int
    auto: int
    rank: int | None
    leader_points: int | None


class ScorecardOut(BaseModel):
    season: int
    weeks: list[ScorecardWeek]
    totals: ScorecardWeek
    by_label: list[dict]


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    provider: Provider = "claude"


class AskOut(BaseModel):
    answer: str
    provider: str
    model: str
    created_at: datetime


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=255)
    auth: str = Field(min_length=8, max_length=255)


PUSH_SERVICE_HOSTS = ("push.apple.com", "fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com")
PUSH_ENDPOINT_PATTERN = r"https://[a-z0-9.-]+(?:/[\x21-\x5b\x5d-\x7e]*)?"


class PushSubscriptionIn(BaseModel):
    """Exactly what the browser's PushSubscription.toJSON() returns."""

    endpoint: str = Field(min_length=10, max_length=2048, pattern=r"^https://")
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def valid_push_service(cls, endpoint: str) -> str:
        if re.fullmatch(PUSH_ENDPOINT_PATTERN, endpoint) is None:
            raise ValueError("Endpoint must belong to a supported push service")
        try:
            address = urlsplit(endpoint)
            host = address.hostname
            valid = (
                address.scheme == "https"
                and address.username is None
                and address.password is None
                and address.port is None
                and ":" not in address.netloc
                and host is not None
                and any(host == service or host.endswith(f".{service}") for service in PUSH_SERVICE_HOSTS)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Endpoint must belong to a supported push service")
        return endpoint


class PushTestResult(BaseModel):
    host: str
    ok: bool
    status: int | None
    error: str | None


class PushTestOut(BaseModel):
    configured: bool
    devices: int
    delivered: int
    results: list[PushTestResult]


class SettingsIn(BaseModel):
    league_leader_accuracy: float | None = Field(default=None, ge=0, le=1)
    reminder_minutes: int | None = Field(default=None, ge=0, le=1440, description="0 turns reminders off")


class MetaOut(BaseModel):
    current_season: int
    current_week: int
    seasons: list[int]
    weeks: list[int]
    model_name: str | None
    model_trained_through: int | None
    ai_providers: dict[str, bool]
    push_public_key: str | None = Field(description="VAPID public key for PushManager.subscribe; null = push off")
    push_subscriptions: int
    reminder_minutes: int | None
    league_leader_accuracy: float | None
    server_time: datetime


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    active_model: bool
    stale_datasets: list[str]
    worker_heartbeat: datetime | None = None
    passkeys: bool
