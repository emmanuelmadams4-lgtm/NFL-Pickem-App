from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    # Model
    train_window_seasons: int = 10
    first_season: int = 2002

    # AI (keys stay on the server)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    openrouter_api_key: str = ""
    openrouter_model: str = "typesafe/jev-1.13"
    openrouter_url: str = "https://openrouter.ai/api/v1/chat/completions"
    ai_daily_call_limit: int = 60
    ai_max_retries: int = 2

    # Web Push (PWA). Make keys with: python -m nflpi.jobs vapid
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""  # "mailto:you@example.com" or an https URL; push services reject placeholders
    alert_move_threshold: float = 0.10


@lru_cache
def get_settings() -> Settings:
    return Settings()
