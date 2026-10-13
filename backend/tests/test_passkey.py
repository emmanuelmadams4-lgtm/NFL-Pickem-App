"""Step 10 server half: passkey sign-in. Frozen clauses P1-P20 (docs/gauntlet/logs/step-10-server.md).

Every test goes through the real app and the real verification library; the passkey is the software authenticator in
tests/fixtures/passkey. Nothing here reads production internals except three names the spec freezes for tests:
nflpi.auth.throttle (reset, LIMIT), nflpi.auth.passkeys (MAX_PASSKEYS, MAX_LIVE_CHALLENGES), nflpi.auth.sessions
(session_factory, for the fail-closed test), and the three table names.
"""

import asyncio
import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from nflpi.api.main import app  # also registers every table before the first truncate
from nflpi.config import get_settings
from tests.fixtures.passkey.authenticator import SoftAuthenticator, b64

RP = "pickem.tail0000.ts.net"
ORIGIN = f"https://{RP}"
NOT_CONFIGURED = {"detail": "Passkey sign-in is not configured"}
SIGNIN_FAILED = {"detail": "Passkey sign-in failed"}
REGISTER_FAILED = {"detail": "Passkey registration failed"}
TOKEN_NEEDED = {"detail": "Adding a passkey needs the app token"}
UNAVAILABLE = {"detail": "Sign-in is temporarily unavailable"}
TOO_MANY = {"detail": "Too many attempts, try again in a minute"}
WRONG_TOKEN = {"detail": "Missing or wrong access token"}
# One cheap route per way a router is mounted in api/main.py: the api router, live, news, and group's own wrapper.
MOUNTS = ["/api/freshness", "/api/live", "/api/news", "/api/group/standings"]


@pytest.fixture
def env():
    """Set environment settings for one test and put them back (the settings object is cached)."""
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


@pytest.fixture
def configured(session, env):
    from nflpi.auth import throttle

    env(PASSKEY_RP_ID=RP, PASSKEY_ORIGINS=ORIGIN)
    throttle.reset()
    yield session
    throttle.reset()


@pytest.fixture
def anon():
    return TestClient(app)


@pytest.fixture
def device():
    return SoftAuthenticator(RP, ORIGIN)


def bearer(value: str) -> dict:
    return {"Authorization": f"Bearer {value}"}


def register(client, device, label: str | None = "iPhone", **knobs):
    options = client.post("/api/passkey/register/begin").json()
    body = {"credential": device.create(options, **knobs)}
    return client.post("/api/passkey/register/finish", json=body if label is None else {**body, "label": label})


def sign_in(anon, device, **knobs):
    options = anon.post("/api/passkey/signin/begin").json()
    return anon.post("/api/passkey/signin/finish", json=device.get(options, **knobs))


def signed_in(client, anon, device) -> str:
    assert register(client, device).status_code == 201
    res = sign_in(anon, device)
    assert res.status_code == 200, res.text
    return res.json()["session"]


def count(session, table: str) -> int:
    return session.execute(text(f"select count(*) from {table}")).scalar_one()


def opens(anon, value: str, path: str = "/api/freshness") -> bool:
    return anon.get(path, headers=bearer(value)).status_code != 401


# P1 -------------------------------------------------------------------------------------------------------------------


def test_p1_unset_settings_answer_not_configured_on_every_ceremony_route_and_change_nothing_else(session, client, anon):
    for step in ("register/begin", "register/finish", "signin/begin", "signin/finish"):
        res = client.post(f"/api/passkey/{step}")
        assert (res.status_code, res.json()) == (503, NOT_CONFIGURED), step
    # list, remove and sign out need no relying party: they keep working so the owner can clean up while it is off
    assert client.get("/api/passkey").json() == {"passkeys": []}
    assert client.delete("/api/passkey/1").status_code == 404
    assert client.post("/api/passkey/signout").status_code == 204
    for method, path in [("get", "/api/passkey"), ("delete", "/api/passkey/1"), ("post", "/api/passkey/signout")]:
        assert anon.request(method, path).status_code == 401, path
    assert anon.post("/api/passkey/signin/begin").json() == NOT_CONFIGURED
    assert client.get("/api/freshness").status_code != 401
    assert (anon.get("/api/freshness").status_code, anon.get("/api/freshness").json()) == (401, WRONG_TOKEN)
    assert count(session, "passkey_challenges") == 0


@pytest.mark.parametrize(
    ("rp_id", "origins"),
    [
        (RP, ""),
        ("", ORIGIN),
        (RP, f"http://{RP}"),  # not https
        (RP, "https://evil.example"),  # host is not the relying party
        (RP, f"https://not{RP}"),  # suffix without a dot is another site
        (RP, f"{ORIGIN},https://evil.example"),  # one bad origin spoils the list
        (RP, f"{ORIGIN}/path"),  # an origin has no path
        ("*", "https://*"),  # a wildcard is not a host name
        ("*.ts.net", "https://a.*.ts.net"),  # nor is one with dots, even when the origin spells the same thing
        ("tsnet", "https://tsnet"),  # a bare name with no dot is not a real host (only localhost is)
    ],
)
def test_p1_half_set_or_unsafe_settings_count_as_not_configured(session, client, env, rp_id, origins):
    env(PASSKEY_RP_ID=rp_id, PASSKEY_ORIGINS=origins)
    res = client.post("/api/passkey/register/begin")
    assert (res.status_code, res.json()) == (503, NOT_CONFIGURED)


def test_p1_localhost_over_http_is_allowed_for_a_dev_machine(session, client, env):
    env(PASSKEY_RP_ID="localhost", PASSKEY_ORIGINS="http://localhost:3000")
    assert client.post("/api/passkey/register/begin").status_code == 200


def test_p1_clearing_the_settings_stops_existing_sessions_without_a_database_call(
    configured, client, anon, device, env, monkeypatch, caplog
):
    from nflpi.auth import sessions

    value = signed_in(client, anon, device)
    assert opens(anon, value)
    env(PASSKEY_RP_ID="", PASSKEY_ORIGINS="")
    monkeypatch.setattr(sessions, "session_factory", lambda: pytest.fail("no lookup when passkeys are off"))
    res = anon.get("/api/freshness", headers=bearer(value))
    assert (res.status_code, res.json()) == (401, WRONG_TOKEN)
    # C3: a typo in the settings signs every device out, so it must be visible in the server log
    assert "passkey session refused: passkey sign-in is not configured" in caplog.text
    assert value not in caplog.text
    assert client.get("/api/freshness").status_code != 401


def test_p1_the_owner_can_remove_a_passkey_while_passkeys_are_off(configured, client, anon, device, env):
    value = signed_in(client, anon, device)
    env(PASSKEY_RP_ID="", PASSKEY_ORIGINS="")  # the off switch, pulled because something looks wrong
    (row,) = client.get("/api/passkey").json()["passkeys"]
    assert client.delete(f"/api/passkey/{row['id']}").status_code == 204
    env(PASSKEY_RP_ID=RP, PASSKEY_ORIGINS=ORIGIN)  # back on: the removed passkey and its session stay dead
    assert not opens(anon, value)
    assert sign_in(anon, device).status_code == 401
    assert (count(configured, "passkey_credentials"), count(configured, "passkey_sessions")) == (0, 0)


# P2, P3 ---------------------------------------------------------------------------------------------------------------


def test_p2_a_stranger_cannot_start_or_finish_a_registration(configured, anon, client, device):
    assert (anon.post("/api/passkey/register/begin").status_code, count(configured, "passkey_challenges")) == (401, 0)
    options = client.post("/api/passkey/register/begin").json()  # even with a live challenge from the owner
    res = anon.post("/api/passkey/register/finish", json={"credential": device.create(options)})
    assert (res.status_code, res.json()) == (401, WRONG_TOKEN)
    assert anon.post("/api/passkey/register/begin", headers=bearer("pks_" + "a" * 43)).status_code == 401
    assert count(configured, "passkey_credentials") == 0
    for method, path in [("get", "/api/passkey"), ("delete", "/api/passkey/1"), ("post", "/api/passkey/signout")]:
        assert anon.request(method, path).status_code == 401, path


def test_p3_the_owner_registers_a_passkey_and_replies_never_carry_the_key(configured, client, device):
    options = client.post("/api/passkey/register/begin").json()
    assert options["rp"]["id"] == RP
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["attestation"] == "none"
    res = client.post("/api/passkey/register/finish", json={"credential": device.create(options), "label": " iPhone "})
    assert res.status_code == 201, res.text
    assert set(res.json()) == {"id", "label", "created_at"}
    assert res.json()["label"] == "iPhone"
    listing = client.get("/api/passkey")
    assert listing.status_code == 200
    (row,) = listing.json()["passkeys"]
    assert set(row) == {"id", "label", "created_at", "last_used_at"}
    assert (row["id"], row["last_used_at"]) == (res.json()["id"], None)
    for reply in (res.text, listing.text):
        assert device.id not in reply
        assert b64(device.cose_public_key) not in reply
    assert count(configured, "passkey_challenges") == 0  # the challenge was used up


def test_p3_the_same_passkey_is_not_stored_twice_and_a_second_begin_excludes_it(configured, client, device):
    assert register(client, device).status_code == 201
    options = client.post("/api/passkey/register/begin").json()
    assert [c["id"] for c in options["excludeCredentials"]] == [device.id]
    res = client.post("/api/passkey/register/finish", json={"credential": device.create(options)})
    assert (res.status_code, res.json()) == (400, REGISTER_FAILED)
    assert count(configured, "passkey_credentials") == 1


@pytest.mark.parametrize("label", ["x" * 65, "bad\x00name", "line\nbreak", "   ", "right\u202eto left", 7])
def test_p3_a_bad_label_is_refused(configured, client, device, label):
    assert register(client, device, label=label).status_code == 422
    assert count(configured, "passkey_credentials") == 0


def test_p3_a_label_is_optional(configured, client, device):
    res = register(client, device, label=None)
    assert (res.status_code, res.json()["label"]) == (201, None)


# P4 -------------------------------------------------------------------------------------------------------------------


def test_p4_sign_in_issues_a_session_that_opens_every_router(configured, client, anon, device):
    assert register(client, device).status_code == 201
    res = sign_in(anon, device)
    assert res.status_code == 200, res.text
    assert set(res.json()) == {"session", "expires_at"}
    assert res.headers["cache-control"] == "no-store"
    value = res.json()["session"]
    assert value.startswith("pks_") and len(value) >= 47
    lifetime = datetime.fromisoformat(res.json()["expires_at"]) - datetime.now(UTC)
    assert timedelta(days=30) - timedelta(minutes=1) < lifetime <= timedelta(days=30)
    for path in MOUNTS:
        assert anon.get(path).status_code == 401, path
        assert opens(anon, value, path), path
    (row,) = client.get("/api/passkey").json()["passkeys"]
    assert row["last_used_at"] is not None


def test_p4_two_sign_ins_give_two_sessions(configured, client, anon, device):
    first = signed_in(client, anon, device)
    second = sign_in(anon, device).json()["session"]
    assert first != second and opens(anon, first) and opens(anon, second)


# R1: a session must not be able to mint a permanent passkey -----------------------------------------------------------


def test_r1_a_session_cannot_add_a_passkey_only_the_app_token_can(configured, client, anon, device):
    value = signed_in(client, anon, device)
    res = anon.post("/api/passkey/register/begin", headers=bearer(value))
    assert (res.status_code, res.json()) == (403, TOKEN_NEEDED)  # 403, not 401: the web app drops sign-in on a 401
    assert count(configured, "passkey_challenges") == 0

    thief = SoftAuthenticator(RP, ORIGIN)
    options = client.post("/api/passkey/register/begin").json()  # a live challenge the owner started
    res = anon.post("/api/passkey/register/finish", json={"credential": thief.create(options)}, headers=bearer(value))
    assert (res.status_code, res.json()) == (403, TOKEN_NEEDED)
    assert (count(configured, "passkey_credentials"), count(configured, "passkey_challenges")) == (1, 1)
    assert opens(anon, value)  # the session itself is still fine
    assert client.post("/api/passkey/register/finish", json={"credential": thief.create(options)}).status_code == 201


# R2: a passkey the owner did not add must be seen ---------------------------------------------------------------------


class FakePush:
    """Stands in for pywebpush.webpush, the network edge."""

    def __init__(self) -> None:
        self.titles: list[str] = []
        self.fail = False

    def __call__(self, info, data, **kwargs):
        self.titles.append(json.loads(data)["title"])
        if self.fail:
            raise RuntimeError("push service is down")


@pytest.fixture
def pushes(configured, env, monkeypatch):
    from nflpi.notify import push

    env(VAPID_PUBLIC_KEY="test-public-key", VAPID_PRIVATE_KEY="test-private-key", VAPID_SUBJECT="mailto:o@example.test")
    configured.execute(
        text(
            "insert into push_subscriptions (endpoint, p256dh, auth, created_at, last_seen) "
            "values ('https://web.push.apple.com/abc', 'k', 'a', now(), now())"
        )
    )
    configured.commit()
    fake = FakePush()
    monkeypatch.setattr(push, "webpush", fake)
    return fake


def passkey_alerts(session) -> int:
    session.rollback()
    return session.execute(text("select count(*) from notifications where kind = 'passkey'")).scalar_one()


def test_r2_adding_and_removing_a_passkey_alerts_the_owner(configured, client, device, pushes, caplog):
    res = register(client, device, label="iPad")
    assert res.status_code == 201
    assert pushes.titles == ["Passkey added"]
    assert passkey_alerts(configured) == 1
    assert "nobody was alerted" not in caplog.text
    assert client.delete(f"/api/passkey/{res.json()['id']}").status_code == 204
    assert pushes.titles == ["Passkey added", "Passkey removed"]
    assert passkey_alerts(configured) == 2
    assert client.delete(f"/api/passkey/{res.json()['id']}").status_code == 404  # nothing removed: nobody alerted
    assert (pushes.titles, passkey_alerts(configured)) == (["Passkey added", "Passkey removed"], 2)


def test_r2_a_refused_registration_alerts_nobody(configured, client, device, pushes):
    assert register(client, device, origin="https://evil.example").status_code == 400
    assert (pushes.titles, passkey_alerts(configured)) == ([], 0)


def test_r2_a_failed_alert_does_not_undo_the_change_and_is_still_on_record(configured, client, device, pushes, caplog):
    pushes.fail = True
    res = register(client, device)
    assert res.status_code == 201
    assert count(configured, "passkey_credentials") == 1
    assert client.delete(f"/api/passkey/{res.json()['id']}").status_code == 204
    assert (count(configured, "passkey_credentials"), passkey_alerts(configured)) == (0, 2)
    assert pushes.titles == ["Passkey added", "Passkey removed"]  # both were tried
    assert caplog.text.count("nobody was alerted") == 2


def test_r2_with_no_device_to_alert_the_change_is_recorded_and_warned(configured, client, device, caplog):
    """C1: adding a passkey needs no push setup, so a silent add must still leave a record and a warning."""
    res = register(client, device, label="quiet")
    assert res.status_code == 201
    assert passkey_alerts(configured) == 1
    assert f"passkey added, nobody was alerted, id={res.json()['id']}" in caplog.text
    assert client.delete(f"/api/passkey/{res.json()['id']}").status_code == 204
    assert passkey_alerts(configured) == 2
    assert f"passkey removed, nobody was alerted, id={res.json()['id']}" in caplog.text


# P5, P6 ---------------------------------------------------------------------------------------------------------------


def test_p5_a_sign_in_challenge_works_once(configured, client, anon, device):
    assert register(client, device).status_code == 201
    body = device.get(anon.post("/api/passkey/signin/begin").json())
    assert anon.post("/api/passkey/signin/finish", json=body).status_code == 200
    replay = anon.post("/api/passkey/signin/finish", json=body)
    assert (replay.status_code, replay.json()) == (401, SIGNIN_FAILED)
    assert count(configured, "passkey_sessions") == 1


def test_p5_a_failed_finish_also_uses_up_the_challenge(configured, client, anon, device):
    assert register(client, device).status_code == 201
    options = anon.post("/api/passkey/signin/begin").json()
    assert anon.post("/api/passkey/signin/finish", json=device.get(options, tamper="signature")).status_code == 401
    assert anon.post("/api/passkey/signin/finish", json=device.get(options)).status_code == 401
    assert count(configured, "passkey_sessions") == 0


def test_p5_a_failed_registration_finish_also_uses_up_the_challenge(configured, client, device):
    options = client.post("/api/passkey/register/begin").json()
    bad = client.post("/api/passkey/register/finish", json={"credential": device.create(options, uv=False)})
    assert (bad.status_code, bad.json()) == (400, REGISTER_FAILED)
    retry = client.post("/api/passkey/register/finish", json={"credential": device.create(options)})
    assert (retry.status_code, retry.json()) == (400, REGISTER_FAILED)
    assert (count(configured, "passkey_credentials"), count(configured, "passkey_challenges")) == (0, 0)


def test_p5_finishes_racing_on_one_challenge_spend_it_once(configured, client, anon, device):
    assert register(client, device).status_code == 201
    body = device.get(anon.post("/api/passkey/signin/begin").json())

    def finish(_: int) -> int:
        return TestClient(app).post("/api/passkey/signin/finish", json=body).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(finish, range(6)))
    assert sorted(codes) == [200, 401, 401, 401, 401, 401]
    assert count(configured, "passkey_sessions") == 1


def test_r3_a_challenge_is_matched_by_its_bytes_not_its_spelling(configured, client, anon, device):
    assert register(client, device).status_code == 201
    options = anon.post("/api/passkey/signin/begin").json()
    assert len(options["challenge"]) % 4 != 0  # so the padded spelling really differs
    padded = anon.post("/api/passkey/signin/finish", json=device.get(options, pad=True))
    assert padded.status_code == 200, padded.text  # the same bytes: found, burnt, verified
    assert count(configured, "passkey_challenges") == 0
    again = anon.post("/api/passkey/signin/finish", json=device.get(options))
    assert (again.status_code, again.json()) == (401, SIGNIN_FAILED)
    assert count(configured, "passkey_sessions") == 1


def test_p5_a_registration_challenge_works_once(configured, client, device):
    options = client.post("/api/passkey/register/begin").json()
    assert client.post("/api/passkey/register/finish", json={"credential": device.create(options)}).status_code == 201
    other = SoftAuthenticator(RP, ORIGIN)
    replay = client.post("/api/passkey/register/finish", json={"credential": other.create(options)})
    assert (replay.status_code, replay.json()) == (400, REGISTER_FAILED)
    assert count(configured, "passkey_credentials") == 1


def expire(session, table: str) -> None:
    session.execute(text(f"update {table} set expires_at = now() - interval '1 second'"))
    session.commit()


def test_p6_a_challenge_expires(configured, client, anon, device):
    options = client.post("/api/passkey/register/begin").json()
    row = configured.execute(text("select created_at, expires_at from passkey_challenges")).one()
    assert row.expires_at - row.created_at == timedelta(minutes=5)
    expire(configured, "passkey_challenges")
    late = client.post("/api/passkey/register/finish", json={"credential": device.create(options)})
    assert (late.status_code, late.json()) == (400, REGISTER_FAILED)

    assert register(client, device).status_code == 201
    options = anon.post("/api/passkey/signin/begin").json()
    expire(configured, "passkey_challenges")
    late = anon.post("/api/passkey/signin/finish", json=device.get(options))
    assert (late.status_code, late.json()) == (401, SIGNIN_FAILED)
    assert count(configured, "passkey_sessions") == 0


# P7, P8, P9, P11 ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "knobs",
    [
        {"origin": "https://evil.example"},  # P7
        {"origin": f"http://{RP}"},  # P7: same host, not https
        {"rp_id": "evil.example"},  # P8
        {"uv": False},  # P11: no Face ID / Touch ID
        {"tamper": "signature"},  # P9
        {"tamper": "auth_data"},  # P9
    ],
)
def test_p7_p8_p9_p11_a_wrong_or_tampered_sign_in_is_refused(configured, client, anon, device, knobs):
    assert register(client, device).status_code == 201
    res = sign_in(anon, device, **knobs)
    assert (res.status_code, res.json()) == (401, SIGNIN_FAILED)
    assert count(configured, "passkey_sessions") == 0
    assert sign_in(anon, device).status_code == 200  # the same passkey, untampered, is fine


@pytest.mark.parametrize("knobs", [{"origin": "https://evil.example"}, {"rp_id": "evil.example"}, {"uv": False}])
def test_p7_p8_p11_a_wrong_registration_is_refused(configured, client, device, knobs):
    res = register(client, device, **knobs)
    assert (res.status_code, res.json()) == (400, REGISTER_FAILED)
    assert count(configured, "passkey_credentials") == 0


def test_p9_a_signature_from_another_key_is_refused(configured, client, anon, device):
    assert register(client, device).status_code == 201
    thief = SoftAuthenticator(RP, ORIGIN)
    thief.credential_id = device.credential_id  # claims the owner's passkey, signs with its own key
    res = sign_in(anon, thief)
    assert (res.status_code, res.json()) == (401, SIGNIN_FAILED)


def test_p9_a_challenge_is_bound_to_its_kind(configured, client, anon, device):
    assert register(client, device).status_code == 201
    register_options = client.post("/api/passkey/register/begin").json()
    res = anon.post("/api/passkey/signin/finish", json=device.get(register_options))
    assert (res.status_code, res.json()) == (401, SIGNIN_FAILED)

    signin_options = anon.post("/api/passkey/signin/begin").json()
    other = SoftAuthenticator(RP, ORIGIN)
    res = client.post("/api/passkey/register/finish", json={"credential": other.create(signin_options)})
    assert (res.status_code, res.json()) == (400, REGISTER_FAILED)
    assert (count(configured, "passkey_sessions"), count(configured, "passkey_credentials")) == (0, 1)


# P10 ------------------------------------------------------------------------------------------------------------------


def stored_count(session) -> int:
    session.rollback()
    return session.execute(text("select sign_count from passkey_credentials")).scalar_one()


def test_p10_a_sign_count_that_does_not_go_up_is_refused_and_a_higher_one_is_stored(configured, client, anon, device):
    assert register(client, device).status_code == 201
    assert sign_in(anon, device, count=5).status_code == 200
    assert stored_count(configured) == 5
    for stale in (3, 5):  # backwards, and a replayed counter
        res = sign_in(anon, device, count=stale)
        assert (res.status_code, res.json()) == (401, SIGNIN_FAILED)
        assert stored_count(configured) == 5
    assert count(configured, "passkey_sessions") == 1
    assert sign_in(anon, device, count=6).status_code == 200
    assert stored_count(configured) == 6


def test_p10_a_passkey_that_never_counts_keeps_working(configured, client, anon, device):
    assert register(client, device).status_code == 201
    assert [sign_in(anon, device, count=0).status_code for _ in range(2)] == [200, 200]  # Apple passkeys send 0


# P12 ------------------------------------------------------------------------------------------------------------------


def test_p12_only_the_hash_of_a_session_is_stored(configured, client, anon, device):
    value = signed_in(client, anon, device)
    row = configured.execute(text("select * from passkey_sessions")).mappings().one()
    assert row["token_hash"] == hashlib.sha256(value.encode()).hexdigest()
    assert value not in repr(dict(row)) and value.removeprefix("pks_") not in repr(dict(row))


def test_p12_an_expired_session_is_refused(configured, client, anon, device):
    value = signed_in(client, anon, device)
    assert opens(anon, value)
    expire(configured, "passkey_sessions")
    res = anon.get("/api/freshness", headers=bearer(value))
    assert (res.status_code, res.json()) == (401, WRONG_TOKEN)
    assert sign_in(anon, device).status_code == 200
    assert count(configured, "passkey_sessions") == 1  # the expired row was cleared at the next sign-in


def test_p12_sign_out_revokes_that_session_only(configured, client, anon, device):
    phone = signed_in(client, anon, device)
    laptop = sign_in(anon, device).json()["session"]
    assert anon.post("/api/passkey/signout", headers=bearer(phone)).status_code == 204
    assert not opens(anon, phone)
    assert opens(anon, laptop)
    assert client.post("/api/passkey/signout").status_code == 204  # with the app token: nothing to revoke
    assert opens(anon, laptop) and client.get("/api/freshness").status_code != 401


def test_p12_a_session_is_accepted_from_the_authorization_header_only(configured, client, anon, device):
    value = signed_in(client, anon, device)
    assert anon.get("/api/freshness", params={"session": value, "token": value}).status_code == 401
    assert anon.get("/api/freshness", headers={"Cookie": f"session={value}", "X-Session": value}).status_code == 401
    for near_miss in (value[:-1], value + "x", value.upper(), value.removeprefix("pks_"), "pks_"):
        assert not opens(anon, near_miss), near_miss


# P13 ------------------------------------------------------------------------------------------------------------------


def test_p13_removing_a_passkey_ends_its_sessions_and_the_app_token_still_works(configured, client, anon, device):
    phone = signed_in(client, anon, device)
    laptop_device = SoftAuthenticator(RP, ORIGIN)
    laptop = signed_in(client, anon, laptop_device)
    first, second = (p["id"] for p in client.get("/api/passkey").json()["passkeys"])  # listed oldest first

    assert client.delete(f"/api/passkey/{first}").status_code == 204
    assert not opens(anon, phone) and opens(anon, laptop)
    assert sign_in(anon, device).status_code == 401
    assert client.delete(f"/api/passkey/{first}").status_code == 404
    assert client.delete("/api/passkey/999999").status_code == 404
    for bad in ("0", "-1", "99999999999999999999", "abc"):  # refused cleanly, never a server error
        assert client.delete(f"/api/passkey/{bad}").status_code == 422, bad

    assert anon.delete(f"/api/passkey/{second}", headers=bearer(laptop)).status_code == 204  # the last one
    assert not opens(anon, laptop)
    assert client.get("/api/passkey").json() == {"passkeys": []}
    assert (count(configured, "passkey_credentials"), count(configured, "passkey_sessions")) == (0, 0)
    for path in MOUNTS:
        assert client.get(path).status_code != 401, path
    assert register(client, device).status_code == 201  # and the token can register again


# P14 ------------------------------------------------------------------------------------------------------------------


def test_p14_every_sign_in_failure_answers_the_same(configured, client, anon, device):
    assert register(client, device).status_code == 201
    stranger = SoftAuthenticator(RP, ORIGIN)  # never registered

    def live() -> dict:
        return anon.post("/api/passkey/signin/begin").json()

    replies = [
        sign_in(anon, stranger),
        sign_in(anon, device, tamper="signature"),
        anon.post("/api/passkey/signin/finish", json=device.get({"challenge": b64(b"never issued by the server")})),
        anon.post("/api/passkey/signin/finish", content=b"not json"),
        anon.post("/api/passkey/signin/finish", json={}),
        anon.post("/api/passkey/signin/finish", json=[1, 2]),
        anon.post("/api/passkey/signin/finish", json={"id": device.id, "response": {"clientDataJSON": "!!"}}),
        anon.post("/api/passkey/signin/finish"),
        anon.post("/api/passkey/signin/finish", content=b"[" * 60_000),  # nesting deeper than the parser allows
        anon.post("/api/passkey/signin/finish", json={**device.get(live()), "id": "nul\x00byte"}),
        anon.post("/api/passkey/signin/finish", json={**device.get(live()), "id": "x" * 2000}),
        anon.post("/api/passkey/signin/finish", json={**device.get(live()), "id": 7}),
        anon.post("/api/passkey/signin/finish", json={**device.get(live()), "response": "text"}),
    ]
    assert {(r.status_code, r.text, r.headers.get("content-type")) for r in replies} == {
        (401, '{"detail":"Passkey sign-in failed"}', "application/json")
    }


def test_p14_sign_in_begin_looks_the_same_with_and_without_a_passkey(configured, client, anon, device):
    before = anon.post("/api/passkey/signin/begin")
    assert register(client, device).status_code == 201
    after = anon.post("/api/passkey/signin/begin")
    assert before.status_code == after.status_code == 200
    assert set(before.json()) == set(after.json())
    for options in (before.json(), after.json()):
        assert options["rpId"] == RP
        assert options["userVerification"] == "required"
        assert options.get("allowCredentials", []) == []
    assert before.json()["challenge"] != after.json()["challenge"]
    assert device.id not in after.text


# P15 ------------------------------------------------------------------------------------------------------------------


def test_p15_nothing_secret_is_logged(configured, client, anon, device, caplog):
    caplog.set_level(logging.DEBUG)
    register_options = client.post("/api/passkey/register/begin").json()
    created = device.create(register_options)
    assert client.post("/api/passkey/register/finish", json={"credential": created}).status_code == 201
    signin_options = anon.post("/api/passkey/signin/begin").json()
    asserted = device.get(signin_options)
    value = anon.post("/api/passkey/signin/finish", json=asserted).json()["session"]
    assert sign_in(anon, device, tamper="signature").status_code == 401
    assert sign_in(anon, device, origin="https://evil.example").status_code == 401
    stranger = SoftAuthenticator(RP, ORIGIN)  # never registered: its id must not be logged either
    assert sign_in(anon, stranger).status_code == 401
    assert sign_in(anon, device).status_code == 200
    assert anon.get("/api/freshness", headers=bearer(value + "x")).status_code == 401
    # refused registrations: a wrong origin, the same passkey again, a body that is not a credential, too big, too many
    spare = SoftAuthenticator(RP, ORIGIN)
    refused_options = client.post("/api/passkey/register/begin").json()
    refused = spare.create(refused_options, origin="https://evil.example")
    assert client.post("/api/passkey/register/finish", json={"credential": refused}).status_code == 400
    assert register(client, device).status_code == 400
    assert client.post("/api/passkey/register/finish", json={"credential": "text"}).status_code == 400
    assert anon.post("/api/passkey/signin/finish", content=b"a" * 70_000).status_code == 413
    assert anon.post("/api/passkey/register/begin", headers=bearer(value)).status_code == 403
    assert anon.post("/api/passkey/signout", headers=bearer(value)).status_code == 204
    (row,) = client.get("/api/passkey").json()["passkeys"]
    assert client.delete(f"/api/passkey/{row['id']}").status_code == 204

    logged = caplog.text + "".join(repr(r.args) + repr(r.__dict__.get("exc_text")) for r in caplog.records)
    assert "passkey" in logged.lower()  # the events themselves are logged
    secrets_ = {
        "app token": "test-token",
        "session": value,
        "session body": value.removeprefix("pks_"),
        "session hash": hashlib.sha256(value.encode()).hexdigest(),
        "register challenge": register_options["challenge"],
        "sign-in challenge": signin_options["challenge"],
        "credential id": device.id,
        "credential id hex": device.credential_id.hex(),
        "public key": b64(device.cose_public_key),
        "public key hex": device.cose_public_key.hex(),
        "signature": asserted["response"]["signature"],
        "attestation": created["response"]["attestationObject"],
        "client data": asserted["response"]["clientDataJSON"],
        "refused challenge": refused_options["challenge"],
        "unknown credential id": stranger.id,
        "refused credential id": spare.id,
        "refused attestation": refused["response"]["attestationObject"],
    }
    for name, secret in secrets_.items():
        assert secret not in logged, name


# P16 ------------------------------------------------------------------------------------------------------------------


def test_p16_the_public_routes_share_one_rate_limit(configured, client, anon, device):
    from nflpi.auth import throttle

    assert register(client, device).status_code == 201
    assert throttle.LIMIT == 30
    throttle.reset()
    for _ in range(throttle.LIMIT - 1):
        assert anon.post("/api/passkey/signin/begin").status_code == 200
    assert anon.post("/api/passkey/signin/finish", json={}).status_code == 401  # call number LIMIT
    for path in ("/api/passkey/signin/begin", "/api/passkey/signin/finish"):
        before = count(configured, "passkey_challenges")
        res = anon.post(path, json={})
        assert (res.status_code, res.json()) == (429, TOO_MANY), path
        assert count(configured, "passkey_challenges") == before  # T3: refused before any row is written
    assert anon.post("/api/passkey/signin/finish", content=b"a" * 70_000).status_code == 429  # and before the body
    assert client.post("/api/passkey/register/begin").status_code == 200  # signed-in routes are not limited
    assert client.get("/api/freshness").status_code != 401
    throttle.reset()
    assert sign_in(anon, device).status_code == 200


def test_p16_the_rate_window_slides(configured, anon, monkeypatch):
    from nflpi.auth import throttle

    assert throttle.WINDOW_S == 60.0
    clock = [1000.0]
    monkeypatch.setattr(throttle.time, "monotonic", lambda: clock[0])
    throttle.reset()
    for _ in range(throttle.LIMIT):
        assert anon.post("/api/passkey/signin/finish", json={}).status_code == 401
    clock[0] += 59.0
    assert anon.post("/api/passkey/signin/finish", json={}).status_code == 429  # still inside the minute
    clock[0] += 1.0
    assert anon.post("/api/passkey/signin/finish", json={}).status_code == 401  # the oldest calls have aged out
    clock[0] += 3600.0
    assert anon.post("/api/passkey/signin/begin").status_code == 200


def test_p16_r5_live_challenges_are_capped_per_kind_and_expired_ones_are_cleared(configured, client, anon):
    from nflpi.auth import passkeys

    assert passkeys.MAX_LIVE_CHALLENGES == 50
    configured.execute(
        text(
            "insert into passkey_challenges (challenge_hash, kind, created_at, expires_at) "
            "select md5(n::text), 'signin', now(), now() + interval '5 minutes' from generate_series(1, :n) n"
        ),
        {"n": passkeys.MAX_LIVE_CHALLENGES},
    )
    configured.commit()
    res = anon.post("/api/passkey/signin/begin")
    assert (res.status_code, res.json()) == (429, TOO_MANY)
    assert count(configured, "passkey_challenges") == passkeys.MAX_LIVE_CHALLENGES
    # R5: the cap is per kind, so a flood of public sign-in challenges cannot block the owner adding a passkey
    assert client.post("/api/passkey/register/begin").status_code == 200
    assert register(client, SoftAuthenticator(RP, ORIGIN)).status_code == 201
    configured.execute(text("delete from passkey_challenges where kind = 'register'"))
    expire(configured, "passkey_challenges")
    assert anon.post("/api/passkey/signin/begin").status_code == 200
    assert count(configured, "passkey_challenges") == 1


def declared_post(path: str, body: bytes, content_length: bytes) -> int:
    """POST straight to the app with a Content-Length that need not match the body (a client library would fix it)."""
    statuses: list[int] = []
    chunks = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive() -> dict:
        return chunks.pop() if chunks else {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"content-length", content_length), (b"authorization", b"Bearer test-token")],
        "server": ("testserver", 443),
        "client": ("testclient", 50000),
    }
    asyncio.run(app(scope, receive, send))
    return statuses[0]


def test_p16_a_declared_length_over_the_cap_is_refused_without_reading_the_body(configured):
    for path in ("/api/passkey/signin/finish", "/api/passkey/register/finish"):
        assert declared_post(path, b"{}", b"70000") == 413, path
        assert declared_post(path, b"{}", b"not a number") == 400, path
    assert declared_post("/api/passkey/signin/finish", b"{}", b"2") == 401  # an honest small body is just a bad sign-in


def test_p16_an_oversized_body_is_refused_before_it_is_parsed(configured, client, anon):
    big = b'{"id": "' + b"a" * 70_000 + b'"}'
    assert anon.post("/api/passkey/signin/finish", content=big).status_code == 413
    assert client.post("/api/passkey/register/finish", content=big).status_code == 413

    def chunks():  # no content-length: the cap must hold on the stream itself
        for _ in range(8):
            yield b"a" * 10_000

    assert anon.post("/api/passkey/signin/finish", content=chunks()).status_code == 413


def test_p16_at_most_ten_passkeys(configured, client):
    from nflpi.auth import passkeys

    assert passkeys.MAX_PASSKEYS == 10
    for n in range(passkeys.MAX_PASSKEYS):
        assert register(client, SoftAuthenticator(RP, ORIGIN), label=f"device {n}").status_code == 201
    res = register(client, SoftAuthenticator(RP, ORIGIN), label="one too many")
    assert (res.status_code, res.json()) == (409, {"detail": "Passkey limit reached (10). Remove one first."})
    assert count(configured, "passkey_credentials") == passkeys.MAX_PASSKEYS


# P19, P20 -------------------------------------------------------------------------------------------------------------


def test_p19_the_app_token_check_is_unchanged_and_a_plain_wrong_token_costs_no_database_call(
    configured, client, anon, monkeypatch
):
    from nflpi.auth import sessions

    def no_database():
        raise AssertionError("the session lookup must not run for this value")

    monkeypatch.setattr(sessions, "session_factory", no_database)
    for value in ("", "wrong", "test-token-x", "Bearer test-token", "pks_", "pks_" + "a" * 200, "PKS_" + "a" * 43):
        res = anon.get("/api/freshness", headers={"Authorization": f"Bearer {value}"} if value else {})
        assert (res.status_code, res.json()) == (401, WRONG_TOKEN), value
    assert client.get("/api/freshness").status_code != 401  # the token itself never reaches the session lookup


def test_p19_r4_a_database_failure_during_the_session_check_is_a_503_not_a_401(
    configured, client, anon, device, monkeypatch, caplog
):
    from nflpi.auth import sessions

    value = signed_in(client, anon, device)

    def broken():
        raise RuntimeError(f"db down while checking {value}")

    monkeypatch.setattr(sessions, "session_factory", broken)
    for path in MOUNTS:  # 503 keeps the value on the device; a 401 would make the web app throw the sign-in away
        res = anon.get(path, headers=bearer(value))
        assert (res.status_code, res.json()) == (503, UNAVAILABLE), path
    assert value not in caplog.text and "session check" in caplog.text
    assert client.get("/api/freshness").status_code != 401


def test_p19_no_app_token_on_the_server_still_answers_503_even_with_a_session(configured, client, anon, device, env):
    value = signed_in(client, anon, device)
    env(APP_ACCESS_TOKEN="")
    res = anon.get("/api/freshness", headers=bearer(value))
    assert (res.status_code, res.json()) == (503, {"detail": "Server has no APP_ACCESS_TOKEN set"})


def test_p20_the_relying_party_and_origin_come_from_settings_never_from_the_request(configured, client, anon, device):
    forged = {
        "Host": "evil.example",
        "Origin": "https://evil.example",
        "Referer": "https://evil.example/",
        "X-Forwarded-Host": "evil.example",
        "X-Forwarded-Proto": "https",
        "Forwarded": "host=evil.example;proto=https",
    }
    created = client.post("/api/passkey/register/begin", headers=forged).json()
    assert created["rp"]["id"] == RP
    assert register(client, device).status_code == 201
    options = anon.post("/api/passkey/signin/begin", headers=forged).json()
    assert options["rpId"] == RP
    evil = device.get(options, origin="https://evil.example", rp_id="evil.example")
    res = anon.post("/api/passkey/signin/finish", json=evil, headers=forged)
    assert (res.status_code, res.json()) == (401, SIGNIN_FAILED)
