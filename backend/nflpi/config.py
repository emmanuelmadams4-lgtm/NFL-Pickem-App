from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_HIDDEN_REPR_FIELDS = frozenset({"anthropic_api_key", "openrouter_api_key", "app_access_token", "vapid_private_key"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    odds_api_key: str = ""  # The Odds API key (server .env only)
    database_url: str = "postgresql+psycopg://nflpi:nflpi@localhost:5432/nflpi"
    # Single-user access token. Every /api route except /api/health requires it.
    app_access_token: str = ""
    cors_origins: str = "http://localhost:3000"
    web_dist_dir: Path = Path(__file__).resolve().parents[2] / "apps" / "web" / "out"

    # Data sources
    nflverse_base: str = "https://github.com/nflverse/nflverse-data/releases/download"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    http_timeout_s: float = 30.0
    http_retries: int = 3

    # Hours after which a dataset is shown as stale
    stale_hours_schedules: float = 12
    stale_hours_injuries: float = 24
    stale_hours_weather: float = 6
    stale_hours_stars: float = 24 * 8
    stale_hours_head_coaches: float = 24 * 30
    # Value ratings: a book price older than this is stale (NO_BET).
    value_max_price_age_minutes: int = Field(default=30, gt=0)

    # Model
    train_window_seasons: int = 10
    first_season: int = 2002

    # AI (keys stay on the server)
    anthropic_api_key: str = ""
    claude_code_oauth_token: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-5-5"
    openrouter_api_key: str = ""
    openrouter_model: str = "typesafe/jev-1.13"
    openrouter_url: str = "https://openrouter.ai/api/v1/chat/completions"
    openrouter_decisions_url: str = "https://openrouter.ai/api/alpha/decisions"
    ai_daily_call_limit: int = 60
    ai_max_retries: int = 2

    # Web Push (PWA). Make keys with: python -m nflpi.jobs vapid
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""  # "mailto:you@example.com" or an https URL; push services reject placeholders
    alert_move_threshold: float = 0.07
    star_summary_hour: int = Field(default=8, ge=0, le=20)  # daily star summary, 8 AM Eastern

    # Passkey sign-in (both empty = off). rp id is the host name; origins are comma-separated https://host[:port].
    passkey_rp_id: str = ""
    passkey_origins: str = ""

    # News
    news_contact: str = ""

    def __repr_args__(self) -> list[tuple[str | None, object]]:
        return [(name, value) for name, value in super().__repr_args__() if name not in _HIDDEN_REPR_FIELDS]


@lru_cache
def get_settings() -> Settings:
    return Settings()
