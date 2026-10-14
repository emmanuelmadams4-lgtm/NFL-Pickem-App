"""Step 10 web half, granted seam: the public /api/health says whether passkey sign-in is configured.

The sign-in card shows its passkey button only when this is true. It reveals nothing new: a stranger can already
learn it from the 503 of the public sign-in route (step 10 server design, section 8).
"""

import os

import pytest
from fastapi.testclient import TestClient

from nflpi.api.main import app
from nflpi.config import get_settings


@pytest.fixture
def env():
    saved: dict[str, str | None] = {}

    def set_(**values: str | None) -> None:
        for name, value in values.items():
            saved.setdefault(name, os.environ.get(name))
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()

    yield set_
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    get_settings.cache_clear()


def health(client: TestClient) -> dict:
    res = client.get("/api/health")  # no Authorization header: the route stays public
    assert res.status_code == 200
    return res.json()


@pytest.mark.parametrize(
    ("rp_id", "origins", "on"),
    [
        ("mac.example.ts.net", "https://mac.example.ts.net", True),
        ("localhost", "http://localhost:8123", True),
        ("", "", False),
        ("mac.example.ts.net", "", False),
        ("mac.example.ts.net", "http://mac.example.ts.net", False),  # not https, not localhost
        ("mac.example.ts.net", "https://other.example.ts.net", False),  # origin outside the relying party
    ],
)
def test_health_says_whether_passkeys_are_configured(session, env, rp_id, origins, on):
    env(PASSKEY_RP_ID=rp_id, PASSKEY_ORIGINS=origins)
    body = health(TestClient(app))
    assert body["passkeys"] is on


def test_health_passkeys_flag_is_a_plain_boolean_and_nothing_else_leaks(session, env):
    env(PASSKEY_RP_ID="mac.example.ts.net", PASSKEY_ORIGINS="https://mac.example.ts.net")
    body = health(TestClient(app))
    assert isinstance(body["passkeys"], bool)
    assert "mac.example.ts.net" not in str(body)
