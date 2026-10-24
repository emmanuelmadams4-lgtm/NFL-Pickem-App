"""App Store settings.

Independent of the Pick'em app. SQLite database, VAPID keys for push, passkey support
for the admin UI, and a separate private access token for the app store API.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Hidden fields never shown in repr/json
_HIDDEN = frozenset(
    {
        "database_url",
        "app_access_token",
        "vapid_private_key",
        "passkey_rp_id",
        "passkey_origins",
        "admin_password",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database (SQLite for single-user; path is auto-resolved) ---
    database_url: str = "sqlite:///app_store.db"

    # --- Private API access token (server .env only) ---
    app_access_token: str = ""

    # --- Web Push (PWA) ---
    vapid_public_key: str = ""
    vapid_private_key: SecretStr = SecretStr("")
    vapid_subject: str = ""

    # --- Passkey sign-in (admin UI) ---
    passkey_rp_id: str = "localhost"  # or tailscale ip / tailnet host
    passkey_origins: str = "https://localhost,http://localhost"

    # --- Admin UI (passkey fallback) ---
    admin_password: SecretStr = SecretStr("")

    # --- Docker / container runtime ---
    docker_socket: str = "/var/run/docker.sock"
    docker_host: str = "unix:///var/run/docker.sock"
    default_network: str = "none"  # containers default to no network
    default_cap_drop: str = "ALL"

    # --- Backward compatible: pick'em api access token (unchanged) ---
    pickem_app_access_token: str = ""

    def __repr_args__(self) -> list[tuple[str | None, object]]:
        return [(n, v) for n, v in super().__repr_args__() if n not in _HIDDEN]


@lru_cache
def get_settings() -> Settings:
    return Settings()
