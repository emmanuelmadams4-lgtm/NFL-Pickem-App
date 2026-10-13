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


def test_n3_a_first_named_starter_is_not_a_qb_change(loaded, pushes, monkeypatch):  # noqa: F811
    """No starter known, then one is named: that is news about the lineup, not a change of QB."""
    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.99)
    subscribe(loaded)
    game = week4_game(loaded)
    game.home_qb = None
    loaded.commit()
    push.alert_prediction_changes(loaded, engine.refresh_predictions(loaded, game_ids=[game.game_id]))
    game.home_qb = "Named Starter"
    loaded.commit()
    push.alert_prediction_changes(loaded, engine.refresh_predictions(loaded, game_ids=[game.game_id]))
    assert [a["title"] for a in sent(pushes) if a["title"].startswith("QB change")] == []


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
    words = {"coin_flip": "a coin flip", "tough_matchup": "a tough matchup", "easy_pick": "an easy pick"}
    from nflpi.analytics.metrics import pick_label

    alert = sent(pushes)[0]
    assert alert["title"] == f"Now {words[pick_label(favourite)]}: {game.away_team} @ {game.home_team}"
    assert f"Was {words[pick_label(other)]}" in alert["body"]


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


# Round 2: findings of the security review and the fresh critic --------------------------------------------------------

def test_n2_no_second_reminder_once_the_days_first_game_is_over(session, client, pushes):  # noqa: F811
    """Critic B2: the 13:00 game going final must not make the 20:20 game 'the day's first'."""
    early = game_row("2026-10-18", "13:00")
    late = game_row("2026-10-18", "20:20", "2026_07_NE_KC", away_team="NE", home_team="KC")
    service.ingest_schedules(session, [early, late])
    subscribe(session)
    assert push.send_kickoff_reminders(session, datetime(2026, 10, 18, 16, 10, tzinfo=UTC)) == 1  # 12:10 ET
    session.get(Game, early["game_id"]).status = "final"
    session.commit()
    assert push.send_kickoff_reminders(session, datetime(2026, 10, 18, 23, 50, tzinfo=UTC)) == 0  # 7:50 PM ET
    assert [a["title"] for a in sent(pushes)] == ["Games today: first kickoff 1:00 PM ET"]


def _earlier_snapshot(loaded, game, shift: float) -> float | None:
    """Adds a snapshot `shift` away from the newest one, same pick and same label. None when no such value exists."""
    from nflpi.analytics.metrics import pick_label

    newest = select(Prediction).where(Prediction.game_id == game.game_id).order_by(Prediction.id.desc())
    last = loaded.scalars(newest).first()
    now = last.home_win_prob
    for was in (now - shift, now + shift):
        same_pick = (was >= 0.5) == (now >= 0.5)
        if 0 < was < 1 and same_pick and pick_label(max(was, 1 - was)) == pick_label(max(now, 1 - now)):
            earlier = {c.name: getattr(last, c.name) for c in Prediction.__table__.columns if c.name != "id"}
            loaded.add(Prediction(**earlier | {"home_win_prob": was, "inputs_hash": "earlier-snapshot"}))
            loaded.commit()
            return was
    return None


def test_n1_an_exact_seven_point_move_is_alerted_as_a_big_move(loaded, pushes):  # noqa: F811
    """Critic S4: 0.57 - 0.50 is 0.0699... in floating point; a 7 point move must still count."""
    subscribe(loaded)
    game = week4_game(loaded)
    was = _earlier_snapshot(loaded, game, 0.07)
    assert was is not None, "fixture: no 7 point neighbour with the same pick and label"
    events = engine.refresh_predictions(loaded, game_ids=[game.game_id])
    assert [e.game_id for e in events] == [game.game_id]
    assert push.alert_prediction_changes(loaded, events) == 1
    alert = sent(pushes)[0]
    assert alert["title"] == f"Big move: {game.away_team} @ {game.home_team}"
    assert f"{was:.0%}" in alert["body"] and "Pick stays" in alert["body"]


def test_n1_a_six_and_a_half_point_move_is_not_alerted(loaded, pushes):  # noqa: F811
    subscribe(loaded)
    game = week4_game(loaded)
    assert _earlier_snapshot(loaded, game, 0.065) is not None, "fixture: no 6.5 point neighbour"
    assert engine.refresh_predictions(loaded, game_ids=[game.game_id]) == []


KEYS = {"p256dh": "B" * 87, "auth": "a" * 22}


@pytest.mark.parametrize("endpoint", [
    "https://127.0.0.1:5432/x",
    "https://169.254.169.254/x",
    "https://100.64.0.1/x",
    "https://example.com/x",
    "https://fcm.googleapis.com.evil.example/x",
    "https://evilpush.apple.com.example/x",
    "https://notpush.apple.com/x",
    "https://web.push.apple.com:8443/x",
    "https://user@web.push.apple.com/x",
    "https://web.push.apple.com@127.0.0.1/x",
    # Security delta: the address parser and the HTTP library disagree about a backslash; the library would connect
    # to the part before it. Whitespace and control characters are refused for the same reason.
    "https://evil.com\\.push.apple.com/x",
    "https://169.254.169.254\\.push.apple.com/x",
    "https://127.0.0.1\\.fcm.googleapis.com/x",
    "https://evil.com\\@push.apple.com/x",
    "https://web.push.apple.com/a\tb",
    "https://web.push.apple.com/abc\n",
    "https://WEB.push.apple.com /x",
])
def test_s1a_subscribe_refuses_an_address_that_is_not_a_push_service(session, client, endpoint):
    """Security S1a: the server sends to the stored address, so only real push services may be stored."""
    assert client.post("/api/push/subscribe", json={"endpoint": endpoint, "keys": KEYS}).status_code == 422
    assert subscriptions(session) == 0


@pytest.mark.parametrize("endpoint", [
    "https://web.push.apple.com/abc",
    "https://fcm.googleapis.com/fcm/send/abc",
    "https://updates.push.services.mozilla.com/wpush/v2/abc",
    "https://wns2-par02p.notify.windows.com/w/?token=abc",
])
def test_s1a_subscribe_accepts_the_real_push_services(session, client, endpoint):
    assert client.post("/api/push/subscribe", json={"endpoint": endpoint, "keys": KEYS}).status_code == 204
    assert subscriptions(session) == 1
    # The library that sends the alert connects to the same host the check approved.
    from urllib.parse import urlsplit

    from urllib3.util import parse_url

    assert parse_url(endpoint).host == urlsplit(endpoint).hostname


def test_s2_an_unexpected_send_failure_logs_its_kind_and_never_the_address(session, pushes, monkeypatch, caplog):  # noqa: F811
    subscribe(session, "secret-device-path")

    def boom(*args, **kwargs):
        raise ValueError("bad key near https://push.example.test/secret-device-path")

    monkeypatch.setattr(push, "webpush", boom)
    with caplog.at_level("WARNING"):
        assert push.send_test_alert(session)["delivered"] == 0
    assert "ValueError" in caplog.text and "push.example.test" in caplog.text
    assert "secret-device-path" not in caplog.text and "bad key" not in caplog.text


def test_n6_a_device_the_push_service_forgot_is_told_what_to_do(session, client, pushes):  # noqa: F811
    """Design critic 2, point 3, as ruled by the fresh critic: for 404 and 410 the remedy is always the same."""
    subscribe(session)
    pushes.fail = http_error(410)
    error = client.post("/api/push/test").json()["results"][0]["error"]
    assert error == "Push service no longer recognizes this device. Turn alerts off and on again."


def test_n3_an_alert_that_reached_no_device_is_not_recorded_as_sent(loaded, pushes, monkeypatch):  # noqa: F811
    """Security S3, critic S1, integrator ruling: a failed send must not use up the alert."""
    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.99)
    subscribe(loaded)
    game = week4_game(loaded)
    game.home_qb = "Backup One"
    loaded.commit()
    events = engine.refresh_predictions(loaded, game_ids=[game.game_id])
    pushes.fail = http_error(503)
    assert push.alert_prediction_changes(loaded, events) == 0
    assert loaded.scalar(select(Notification.id).where(Notification.kind == "prediction")) is None
    pushes.fail = None
    assert push.alert_prediction_changes(loaded, events) == 1
    assert push.alert_prediction_changes(loaded, events) == 0  # delivered once: not sent again
    assert len(pushes.calls) == 2  # the failed try and the delivered one


def test_n3_an_alert_that_reached_no_device_says_so_in_the_log(loaded, pushes, monkeypatch, caplog):  # noqa: F811
    """Security delta F1: nothing is retried, so the miss must at least be written down, with the alert's key."""
    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.99)
    subscribe(loaded)
    game = week4_game(loaded)
    game.home_qb = "Backup One"
    loaded.commit()
    events = engine.refresh_predictions(loaded, game_ids=[game.game_id])
    pushes.fail = http_error(503)
    with caplog.at_level("WARNING"):
        assert push.alert_prediction_changes(loaded, events) == 0
    assert f"alert pred:{game.game_id}:qb:" in caplog.text and "reached 0 devices" in caplog.text
