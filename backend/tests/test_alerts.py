"""Step 7 criteria N1-N7 (docs/gauntlet/logs/step-7.md): game-day reminders, drastic changes, test alert."""

import base64
import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import http_ece
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from sqlalchemy import select

from nflpi.config import Settings, get_settings
from nflpi.ingestion import service
from nflpi.models import Game, Notification, Prediction, PushSubscription
from nflpi.notify import push
from nflpi.predictions import engine
from tests.conftest import CURRENT
from tests.test_hardening import (  # noqa: F401 - pushes is a fixture
    KICKOFF,
    game_row,
    http_error,
    pushes,
    subscribe,
    subscriptions,
)

SUNDAY_EARLY = KICKOFF  # Sunday 2026-10-18 13:00 EDT
SUNDAY_LATE = datetime(2026, 10, 18, 20, 25, tzinfo=UTC)  # 16:25 EDT
MONDAY_NIGHT = datetime(2026, 10, 20, 0, 15, tzinfo=UTC)  # Monday 20:15 EDT, already Tuesday in UTC


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@pytest.fixture
def game_days(session, client, pushes):  # noqa: F811
    """Two Sunday games and one Monday night game, one subscribed phone. Reminder setting untouched."""
    service.ingest_schedules(
        session,
        [
            game_row("2026-10-18", "13:00"),
            game_row("2026-10-18", "16:25", "2026_07_NE_KC", away_team="NE", home_team="KC"),
            game_row("2026-10-19", "20:15", "2026_07_NYJ_LV", away_team="NYJ", home_team="LV"),
        ],
    )
    subscribe(session)
    return session


def sent(pushes) -> list[dict]:  # noqa: F811
    return [json.loads(c["data"]) for c in pushes.calls]


# N1 ---------------------------------------------------------------------------------------------------------------


def test_n1_a_win_chance_move_of_seven_points_counts_as_drastic():
    assert Settings.model_fields["alert_move_threshold"].default == 0.07


# N2 ---------------------------------------------------------------------------------------------------------------


def test_n2_one_reminder_per_game_day_an_hour_before_its_first_kickoff(game_days, client, pushes):  # noqa: F811
    # He has already picked the first game: the reminder is sent anyway (D19).
    assert client.put("/api/picks/2026_07_MIA_BUF", json={"team": "BUF"}).status_code == 200

    assert push.send_kickoff_reminders(game_days, SUNDAY_EARLY - timedelta(minutes=61)) == 0  # too early
    assert push.send_kickoff_reminders(game_days, SUNDAY_EARLY - timedelta(minutes=50)) == 1
    assert push.send_kickoff_reminders(game_days, SUNDAY_EARLY - timedelta(minutes=45)) == 0  # once per day
    assert push.send_kickoff_reminders(game_days, SUNDAY_LATE - timedelta(minutes=30)) == 0  # not the day's first game
    assert push.send_kickoff_reminders(game_days, MONDAY_NIGHT - timedelta(minutes=30)) == 1  # its own Eastern day

    sunday, monday = sent(pushes)
    assert sunday["title"] == "Games today: first kickoff 1:00 PM ET"
    assert sunday["body"] == "2 games today. First: MIA @ BUF."
    assert sunday["url"] == "/sheet/"
    assert monday["title"] == "Game today: kickoff 8:15 PM ET"
    assert monday["body"] == "1 game today: NYJ @ LV."
    call = pushes.calls[0]
    headers = {k.lower(): v for k, v in (call.get("headers") or {}).items()}
    assert (call.get("ttl"), headers.get("urgency")) == (50 * 60, "high")


def test_n2_reminder_is_on_at_one_hour_until_he_changes_it_and_zero_turns_it_off(game_days, client, pushes):  # noqa: F811
    assert client.get("/api/meta").json()["reminder_minutes"] == 60
    assert client.put("/api/settings", json={"reminder_minutes": 0}).json()["reminder_minutes"] == 0
    assert push.send_kickoff_reminders(game_days, SUNDAY_EARLY - timedelta(minutes=30)) == 0
    assert client.put("/api/settings", json={"reminder_minutes": 180}).status_code == 200
    assert push.send_kickoff_reminders(game_days, SUNDAY_EARLY - timedelta(minutes=170)) == 1


def test_n2_no_reminder_after_the_first_kickoff_or_for_a_day_with_no_clock_time(session, client, pushes):  # noqa: F811
    service.ingest_schedules(session, [game_row("2026-10-18", "13:00"), game_row("2026-10-25", "", "2026_08_tbd")])
    subscribe(session)
    assert push.send_kickoff_reminders(session, SUNDAY_EARLY + timedelta(minutes=1)) == 0
    assert push.send_kickoff_reminders(session, datetime(2026, 10, 25, 4, 30, tzinfo=UTC)) == 0  # 00:30 EDT, time TBD
    assert pushes.calls == []


# N3, N4, N5 -------------------------------------------------------------------------------------------------------


def week4_game(session) -> Game:
    return session.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()


def test_n3_a_starting_qb_change_is_alerted_even_when_the_win_chance_barely_moves(loaded, pushes, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.99)
    subscribe(loaded)
    game = week4_game(loaded)
    game.home_qb = "Backup One"
    loaded.commit()
    events = engine.refresh_predictions(loaded, game_ids=[game.game_id])
    assert [e.game_id for e in events] == [game.game_id]
    assert push.alert_prediction_changes(loaded, events) == 1
    alert = sent(pushes)[0]
    assert alert["title"] == f"QB change: {game.away_team} @ {game.home_team}"
    assert "Backup One" in alert["body"]
    assert alert["url"] == f"/game/?id={game.game_id}"


def test_n4_a_label_change_is_alerted_even_when_the_win_chance_barely_moves(loaded, pushes, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.99)
    subscribe(loaded)
    game = week4_game(loaded)
    newest = select(Prediction).where(Prediction.game_id == game.game_id).order_by(Prediction.id.desc())
    last = loaded.scalars(newest).first()
    favourite = max(last.home_win_prob, 1 - last.home_win_prob)
    # An earlier snapshot with the same pick but on the other side of a label line.
    other = 0.60 if favourite >= 0.67 or favourite < 0.55 else 0.70
    earlier = {c.name: getattr(last, c.name) for c in Prediction.__table__.columns if c.name != "id"}
    earlier |= {"home_win_prob": other if last.home_win_prob >= 0.5 else 1 - other, "inputs_hash": "earlier-snapshot"}
    loaded.add(Prediction(**earlier))
    loaded.commit()

    events = engine.refresh_predictions(loaded, game_ids=[game.game_id])
    assert [e.game_id for e in events] == [game.game_id]
    assert push.alert_prediction_changes(loaded, events) == 1
    words = {"coin_flip": "coin flip", "tough_matchup": "tough matchup", "easy_pick": "easy pick"}
    from nflpi.analytics.metrics import pick_label

    alert = sent(pushes)[0]
    assert alert["title"] == f"Now a {words[pick_label(favourite)]}: {game.away_team} @ {game.home_team}"
    assert f"Was a {words[pick_label(other)]}" in alert["body"]


def test_n5_no_change_alert_once_the_game_has_kicked_off(loaded, pushes):  # noqa: F811
    subscribe(loaded)
    game = week4_game(loaded)
    flip = engine.ChangeEvent(game.game_id, 0.6, 0.4, game.home_team, game.away_team, "QB out")
    assert push.alert_prediction_changes(loaded, [flip], now=game.kickoff_utc + timedelta(minutes=1)) == 0
    assert pushes.calls == []
    assert loaded.scalar(select(Notification.id).where(Notification.game_id == game.game_id)) is None
    assert push.alert_prediction_changes(loaded, [flip], now=game.kickoff_utc - timedelta(minutes=1)) == 1


# N6 ---------------------------------------------------------------------------------------------------------------


def test_n6_send_test_alert_reports_what_the_push_service_answered(session, client, pushes):  # noqa: F811
    assert client.post("/api/push/test").json() == {"configured": True, "devices": 0, "delivered": 0, "results": []}
    subscribe(session)
    body = client.post("/api/push/test").json()
    assert (body["devices"], body["delivered"]) == (1, 1)
    assert body["results"] == [{"host": "push.example.test", "ok": True, "status": None, "error": None}]
    assert sent(pushes)[0]["title"] == "Test alert" and sent(pushes)[0]["url"] == "/settings/"

    pushes.fail = http_error(410)
    body = client.post("/api/push/test").json()
    assert (body["devices"], body["delivered"]) == (1, 0)
    gone = {"host": "push.example.test", "ok": False, "status": 410, "error": None}
    assert body["results"][0] | {"error": None} == gone
    assert body["results"][0]["error"]  # says why, in words
    assert subscriptions(session) == 0  # a subscription the push service calls gone is dropped


def test_n6_send_test_alert_needs_the_token_and_says_when_push_is_not_set_up(session, client):
    from fastapi.testclient import TestClient

    from nflpi.api.main import app

    assert TestClient(app).post("/api/push/test").status_code == 401
    subscribe(session)
    assert client.post("/api/push/test").json() == {"configured": False, "devices": 1, "delivered": 0, "results": []}


# N7 ---------------------------------------------------------------------------------------------------------------


class MockPushService(BaseHTTPRequestHandler):
    """A push service on this machine: it keeps what the server posted."""

    received: list[dict] = []

    def do_POST(self):  # noqa: N802 - http.server's name
        body = self.rfile.read(int(self.headers["Content-Length"]))
        MockPushService.received.append({"path": self.path, "headers": dict(self.headers), "body": body})
        self.send_response(201)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_n7_a_real_push_reaches_a_push_service_signed_and_encrypted(session, client, monkeypatch):
    public, private = push.generate_vapid_keys()
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", public)
    monkeypatch.setattr(settings, "vapid_private_key", private)
    monkeypatch.setattr(settings, "vapid_subject", "mailto:owner@example.test")

    MockPushService.received = []
    server = HTTPServer(("127.0.0.1", 0), MockPushService)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    phone_key = ec.generate_private_key(ec.SECP256R1())
    point = (serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    phone_public = phone_key.public_key().public_bytes(*point)
    auth = b"0123456789abcdef"
    session.add(PushSubscription(endpoint=f"{origin}/push/phone-1", p256dh=b64(phone_public), auth=b64(auth)))
    session.commit()
    try:
        body = client.post("/api/push/test").json()
    finally:
        server.shutdown()
    assert (body["delivered"], body["results"][0]["status"]) == (1, 201)

    (got,) = MockPushService.received
    headers = {k.lower(): v for k, v in got["headers"].items()}
    assert got["path"] == "/push/phone-1"
    assert headers["content-encoding"] == "aes128gcm"
    assert int(headers["ttl"]) > 0

    # The VAPID token: signed with the server's key, for this push service, not expired.
    scheme, _, params = headers["authorization"].partition(" ")
    fields = dict(p.strip().split("=", 1) for p in params.split(","))
    assert scheme == "vapid" and fields["k"] == public
    signed, _, signature = fields["t"].rpartition(".")
    claims = json.loads(unb64(signed.split(".")[1]))
    assert claims["aud"] == origin and claims["sub"] == "mailto:owner@example.test"
    assert claims["exp"] > datetime.now(UTC).timestamp()
    raw = unb64(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    server_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(public))
    server_key.verify(der, signed.encode(), ec.ECDSA(hashes.SHA256()))  # raises if the signature is wrong

    # Only the phone can read it.
    message = json.loads(http_ece.decrypt(got["body"], private_key=phone_key, auth_secret=auth, version="aes128gcm"))
    assert message == {"title": "Test alert", "body": "Alerts work on this device.", "url": "/settings/"}
