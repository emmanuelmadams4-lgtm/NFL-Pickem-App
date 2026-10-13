"""Step 1 acceptance criteria A1-A14 (docs/gauntlet/logs/step-1.md). One test per criterion; A5-A7, A11 need a few."""

import contextlib
import copy
import inspect
import json
import os
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import pywebpush
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from nflpi import jobs
from nflpi.ai import providers, research
from nflpi.ai.providers import AIError
from nflpi.api.main import create_app
from nflpi.config import get_settings
from nflpi.db import get_engine
from nflpi.ingestion import nflverse, service, weather
from nflpi.models import AppSetting, Game, ModelVersion, Prediction, PushSubscription, UserPick
from nflpi.notify import push
from nflpi.predictions import engine
from tests.conftest import CURRENT, schedule_rows
from tests.test_api import _report

BACKEND = Path(__file__).resolve().parents[1]
EASTERN = ZoneInfo("America/New_York")
GAME_ID = "2026_07_MIA_BUF"
KICKOFF = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)  # Sunday 13:00 EDT
HALF_HOUR_BEFORE = KICKOFF - timedelta(minutes=30)


def game_row(gameday: str, gametime: str, game_id: str = GAME_ID, **over: str) -> dict:
    """An unplayed nflverse schedule row."""
    base = schedule_rows()[-1] | {"away_team": "MIA", "home_team": "BUF", "season": "2026", "week": "7"}
    return base | {"game_id": game_id, "gameday": gameday, "gametime": gametime} | over


def week_rows(week: int) -> list[dict]:
    return [r for r in schedule_rows() if r["season"] == str(CURRENT) and r["week"] == str(week)]


def reingest(session, changed: dict[str, dict]) -> None:
    """Load the fixture schedule again with some rows changed (keyed by game_id)."""
    service.ingest_schedules(session, [r | changed.get(r["game_id"], {}) for r in schedule_rows()])


def subscribe(session, device: str = "iphone") -> None:
    session.add(PushSubscription(endpoint=f"https://push.example.test/{device}", p256dh="B" * 87, auth="a" * 22))
    session.commit()


def subscriptions(session) -> int:
    return session.scalar(select(func.count()).select_from(PushSubscription))


class FakeWebPush:
    """Stands in for pywebpush.webpush (the network edge). Records each call by parameter name."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fail: Exception | None = None

    def __call__(self, *args, **kwargs):
        self.calls.append(dict(inspect.signature(pywebpush.webpush).bind(*args, **kwargs).arguments))
        if self.fail is not None:
            raise self.fail
        return "sent"

    def titles(self) -> list[str]:
        return [json.loads(c["data"])["title"] for c in self.calls]


def http_error(status: int) -> pywebpush.WebPushException:
    return pywebpush.WebPushException(f"push service said {status}", response=SimpleNamespace(status_code=status))


@pytest.fixture
def pushes(monkeypatch) -> FakeWebPush:
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:owner@example.test")
    fake = FakeWebPush()
    monkeypatch.setattr(push, "webpush", fake)
    return fake


@pytest.fixture
def reminder_game(session, client, pushes):
    """One game kicking off at KICKOFF (its day's first) and a 60-minute reminder window. No subscription yet."""
    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    assert client.put("/api/settings", json={"reminder_minutes": 60}).status_code == 200
    return session


# A1 ---------------------------------------------------------------------------------------------------------------


def test_refresh_and_cycle_run_under_one_advisory_lock(loaded, client, monkeypatch):
    from nflpi.db import REFRESH_LOCK_KEY  # new contract name: the bigint key both paths must lock

    db = get_engine()
    key = {"k": REFRESH_LOCK_KEY}
    try_lock, unlock = text("select pg_try_advisory_lock(:k)"), text("select pg_advisory_unlock(:k)")
    ran = []

    def locked_now() -> bool:
        with db.connect() as probe:
            if not probe.scalar(try_lock, key):
                return True
            probe.execute(unlock, key)
            return False

    monkeypatch.setattr(jobs, "ingest", lambda session, weather=True: ran.append(("ingest", locked_now())) or {})
    monkeypatch.setattr(jobs, "predict", lambda session: ran.append(("predict", locked_now())) or 0)

    def refresh() -> dict:
        body = client.post("/api/refresh").json()
        for thread in threading.enumerate():  # let a started background refresh finish
            if thread is not threading.current_thread():
                thread.join(timeout=10)
        return body

    with db.connect() as other:
        assert other.scalar(try_lock, key)
        try:
            started = refresh()["started"]
            jobs.cycle(loaded)
        finally:
            other.execute(unlock, key)
    assert (started, ran) == (False, [])

    jobs.cycle(loaded)
    assert refresh()["started"] is True
    assert ran == [("ingest", True), ("predict", True)] * 2  # each ran while the lock was held


# A2 ---------------------------------------------------------------------------------------------------------------


def test_retraining_a_season_inserts_a_new_model_version_and_new_snapshots(loaded, monkeypatch):
    old = engine.active_model(loaded)
    before = (old.name, old.trained_through_season, copy.deepcopy(old.params))
    games = set(loaded.scalars(select(Prediction.game_id)))

    monkeypatch.setattr(get_settings(), "train_window_seasons", 2)  # same season, a different fit
    new = engine.train(loaded, through_season=CURRENT - 1)
    assert new.id != old.id and new.params != before[2]
    loaded.refresh(old)
    assert (old.name, old.trained_through_season, old.params) == before
    assert engine.active_model(loaded).id == new.id

    engine.refresh_predictions(loaded)
    by_version = {old.id: set(), new.id: set()}
    for game_id, version in loaded.execute(select(Prediction.game_id, Prediction.model_version_id)):
        by_version[version].add(game_id)
    assert by_version == {old.id: games, new.id: games}
    assert loaded.scalar(select(func.count()).select_from(ModelVersion)) == 2


# A3 ---------------------------------------------------------------------------------------------------------------


def test_csv_import_never_changes_a_pick_after_kickoff(loaded, client):
    past = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 1)).first()

    def import_pick(team: str) -> int:
        return client.post("/api/picks/import", content=f"game_id,my_pick\n{past.game_id},{team}\n").json()["imported"]

    assert import_pick(past.home_team) == 1  # no pick yet: backfilling history is allowed
    assert import_pick(past.away_team) == 0
    assert loaded.scalar(select(UserPick.picked_team).where(UserPick.game_id == past.game_id)) == past.home_team


# A4 ---------------------------------------------------------------------------------------------------------------


def test_recommendation_is_the_last_snapshot_before_kickoff(loaded, client):
    game = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    for qb, when in (("Backup One", timedelta(hours=-1)), ("Backup Two", timedelta(hours=1))):
        game.home_qb = qb
        loaded.commit()
        engine.refresh_predictions(loaded, now=game.kickoff_utc + when, game_ids=[game.game_id])
    ids = loaded.scalars(select(Prediction.id).where(Prediction.game_id == game.game_id).order_by(Prediction.id)).all()
    assert len(ids) == 3  # first, one hour before kickoff, one hour after

    detail = client.get(f"/api/games/{game.game_id}").json()
    assert [p["id"] for p in detail["prediction_history"]] == ids
    assert detail["prediction"]["id"] == ids[1]


# A5 ---------------------------------------------------------------------------------------------------------------


def test_reminder_push_has_a_timeout_ttl_to_kickoff_and_high_urgency(reminder_game, pushes):
    subscribe(reminder_game)
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 1
    call = pushes.calls[0]
    headers = {k.lower(): v for k, v in (call.get("headers") or {}).items()}
    assert (call.get("timeout"), call.get("ttl"), headers.get("urgency")) == (10, 30 * 60, "high")


@pytest.mark.parametrize(
    "failure", [requests.ConnectionError("push service unreachable"), http_error(500)], ids=["network", "http-500"]
)
def test_failed_reminder_send_keeps_the_subscription_and_is_retried(reminder_game, pushes, failure):
    subscribe(reminder_game)
    pushes.fail = failure
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 0
    assert subscriptions(reminder_game) == 1

    pushes.fail = None
    next_tick = HALF_HOUR_BEFORE + timedelta(minutes=5)
    assert push.send_kickoff_reminders(reminder_game, next_tick) == 1
    assert push.send_kickoff_reminders(reminder_game, next_tick) == 0
    assert len(pushes.calls) == 2  # one failed, one delivered, never again


@pytest.mark.parametrize("status", [404, 410])
def test_gone_subscription_is_deleted_and_the_reminder_waits_for_a_successful_push(reminder_game, pushes, status):
    subscribe(reminder_game)
    pushes.fail = http_error(status)
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 0
    assert subscriptions(reminder_game) == 0

    pushes.fail = None
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 0  # nobody to send to: still unsent
    subscribe(reminder_game, "new-phone")
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 1
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 0
    assert len(pushes.calls) == 2  # the rejected push and the delivered one


# A6 ---------------------------------------------------------------------------------------------------------------


def test_reminder_tick_sends_reminders_without_network_ingest(reminder_game, pushes, monkeypatch):
    fetched = []
    monkeypatch.setattr(nflverse, "fetch_csv", lambda path: fetched.append(path) or [])
    monkeypatch.setattr(weather, "fetch_forecast", lambda *args: fetched.append("weather"))
    subscribe(reminder_game)

    jobs.tick(reminder_game, HALF_HOUR_BEFORE)
    assert pushes.titles() == ["Game today: kickoff 1:00 PM ET"]
    assert fetched == []
    assert jobs.TICK_SECONDS <= 5 * 60


def test_one_broken_subscription_does_not_stop_reminders_or_the_heartbeat(reminder_game, pushes, monkeypatch):
    subscribe(reminder_game, "broken")
    subscribe(reminder_game, "good")

    def flaky(info, *args, **kwargs):
        if info["endpoint"].endswith("broken"):
            raise ValueError("bad subscription key")
        return pushes(info, *args, **kwargs)

    monkeypatch.setattr(push, "webpush", flaky)
    jobs.tick(reminder_game, HALF_HOUR_BEFORE)
    assert pushes.titles() == ["Game today: kickoff 1:00 PM ET"]
    assert reminder_game.get(AppSetting, jobs.HEARTBEAT_KEY) is not None


def test_ingest_failure_in_the_cycle_does_not_skip_reminders(session, client, pushes, monkeypatch):
    soon = (datetime.now(UTC) + timedelta(minutes=30)).astimezone(EASTERN)  # cycle reads the real clock
    service.ingest_schedules(session, [game_row(soon.date().isoformat(), soon.strftime("%H:%M"))])
    assert client.put("/api/settings", json={"reminder_minutes": 60}).status_code == 200
    subscribe(session)

    def nflverse_down(session, weather=True):
        raise RuntimeError("nflverse down")

    monkeypatch.setattr(jobs, "ingest", nflverse_down)
    with contextlib.suppress(Exception):  # whether the cycle re-raises the ingest error is not part of the criterion
        jobs.cycle(session)
    assert pushes.titles() == [f"Game today: kickoff {soon.strftime('%-I:%M %p')} ET"]


# A7 ---------------------------------------------------------------------------------------------------------------


def test_schedule_times_handle_dst_london_and_time_tbd(session):
    rows = [
        game_row("2026-11-01", "13:00", "2026_08_dst"),  # clocks went back at 02:00 that morning: EST
        game_row("2026-10-11", "09:30", "2026_05_london", location="Neutral"),  # US still on EDT
        game_row("2026-12-19", "", "2026_15_tbd"),  # flexed Saturday game, time not announced
    ]
    assert service.ingest_schedules(session, rows).status == "ok"
    stored = {g.game_id: (g.kickoff_utc, g.time_tbd) for g in session.scalars(select(Game))}
    assert stored == {
        "2026_08_dst": (datetime(2026, 11, 1, 18, 0, tzinfo=UTC), False),
        "2026_05_london": (datetime(2026, 10, 11, 13, 30, tzinfo=UTC), False),
        # Date only: the start of the game day in US Eastern (00:00 EST), not a 13:00 guess.
        "2026_15_tbd": (datetime(2026, 12, 19, 5, 0, tzinfo=UTC), True),
    }


def test_rescheduled_kickoff_reminds_again(reminder_game, pushes):
    subscribe(reminder_game)
    assert push.send_kickoff_reminders(reminder_game, HALF_HOUR_BEFORE) == 1

    service.ingest_schedules(reminder_game, [game_row("2026-10-19", "20:15")])  # moved to Monday night
    reminder_game.expire_all()
    moved = datetime(2026, 10, 20, 0, 15, tzinfo=UTC)
    assert push.send_kickoff_reminders(reminder_game, moved - timedelta(minutes=30)) == 1
    assert push.send_kickoff_reminders(reminder_game, moved - timedelta(minutes=30)) == 0


def test_postponed_game_keeps_its_status_and_gets_no_reminder_or_pick_lock(session, client, pushes):
    row = game_row("2025-10-05", "13:00", "2025_05_MIA_BUF", season="2025", week="5")  # kickoff time long past
    stale_kickoff = datetime(2025, 10, 5, 17, 0, tzinfo=UTC)
    service.ingest_schedules(session, [row])
    game = session.get(Game, row["game_id"])
    game.status = "postponed"
    session.commit()
    assert client.put("/api/settings", json={"reminder_minutes": 60}).status_code == 200
    subscribe(session)

    service.ingest_schedules(session, [row])  # same unplayed row again
    session.refresh(game)
    assert game.status == "postponed"
    assert push.send_kickoff_reminders(session, stale_kickoff - timedelta(minutes=30)) == 0
    assert pushes.calls == []
    assert client.get(f"/api/games/{game.game_id}").json()["locked"] is False
    assert client.put(f"/api/picks/{game.game_id}", json={"team": "BUF"}).status_code == 200


def test_time_tbd_game_is_not_locked_or_reminded_from_its_placeholder_time(session, client, pushes):
    row = game_row("2025-10-05", "", "2025_05_MIA_BUF", season="2025", week="5")  # day long past, no clock time
    service.ingest_schedules(session, [row])
    game = session.get(Game, row["game_id"])
    assert client.put("/api/settings", json={"reminder_minutes": 60}).status_code == 200
    subscribe(session)

    assert push.send_kickoff_reminders(session, game.kickoff_utc - timedelta(minutes=30)) == 0
    assert pushes.calls == []
    assert client.get(f"/api/games/{game.game_id}").json()["locked"] is False

    game.status = "final"  # once the result is in, a missing clock time must not leave the pick open
    session.commit()
    assert client.get(f"/api/games/{game.game_id}").json()["locked"] is True


# A8 ---------------------------------------------------------------------------------------------------------------


def test_upcoming_game_without_a_projected_qb_is_flagged(loaded, client):
    blank = week_rows(4)[0]["game_id"]
    reingest(loaded, {blank: {"home_qb_name": ""}})
    games = client.get(f"/api/weeks/{CURRENT}/4").json()["games"]
    assert {g["game_id"]: g["qb_not_projected"] for g in games} == {g["game_id"]: g["game_id"] == blank for g in games}


# A9 ---------------------------------------------------------------------------------------------------------------


def test_current_week_is_the_week_of_the_next_kickoff(session):
    cancelled = week_rows(2)[0]["game_id"]  # weeks 1-3 are in the past; this one never got a score
    reingest(session, {cancelled: {"home_score": "", "away_score": ""}})
    assert engine.current_week(session) == (CURRENT, 4)


def test_current_week_stays_until_its_last_game_is_final(session):
    live = week_rows(3)[0]["game_id"]  # kicked off an hour ago, no final score yet
    started = (datetime.now(UTC) - timedelta(hours=1)).astimezone(EASTERN)
    in_progress = {"home_score": "", "away_score": "", "gameday": f"{started:%Y-%m-%d}", "gametime": f"{started:%H:%M}"}
    reingest(session, {live: in_progress})
    assert engine.current_week(session) == (CURRENT, 3)


# A10 --------------------------------------------------------------------------------------------------------------


def test_health_is_degraded_without_a_fresh_worker_heartbeat(loaded, client, monkeypatch):
    monkeypatch.setattr(weather, "fetch_forecast", lambda *args: None)
    service.ingest_injuries(loaded, CURRENT, rows=[])
    service.ingest_weather(loaded)  # now every dataset is fresh and a model is active

    def status() -> str:
        res = client.get("/api/health", headers={"Authorization": ""})  # public
        assert res.status_code == 200
        return res.json()["status"]

    assert status() == "degraded"  # no heartbeat yet
    now = datetime.now(UTC)  # an input, not an expected value: health reads the real clock
    jobs.tick(loaded, now - timedelta(seconds=2 * jobs.HEARTBEAT_STALE_SECONDS))
    assert status() == "degraded"
    jobs.tick(loaded, now)
    assert status() == "ok"


# A11 --------------------------------------------------------------------------------------------------------------


class AlwaysWrong:
    name, model = "claude", "fake-model"
    calls = 0

    def complete(self, system, user, json_schema=None, max_tokens=16000):
        self.calls += 1
        return "not json"


def test_ai_daily_cap_counts_failed_attempts(loaded, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_max_retries", 2)
    monkeypatch.setattr(get_settings(), "ai_daily_call_limit", 3)
    gid = week_rows(4)[0]["game_id"]
    provider = AlwaysWrong()
    assert research.generate_report(loaded, gid, provider=provider).status == "failed"
    assert provider.calls == 3  # one try, two retries: the whole daily budget
    with pytest.raises(AIError, match="limit"):
        research.generate_report(loaded, gid, provider=provider)
    assert provider.calls == 3


class FakeAnthropic:
    """Stands in for the Anthropic SDK client: any `client.a.b.create(**kwargs)` call is recorded."""

    def __init__(self, reply: str) -> None:
        self.reply, self.calls = reply, []

    def __getattr__(self, name: str) -> "FakeAnthropic":
        return self

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.reply)])


def test_ai_calls_allow_at_least_16000_output_tokens(loaded, monkeypatch):
    gid = week_rows(4)[0]["game_id"]
    reply = _report(research.evidence_pack(loaded, gid))
    claude = providers.ClaudeProvider("test-key", "fake-model")
    claude.client = FakeAnthropic(reply)
    posted = []

    def post(url, json, **kwargs):
        posted.append(json)
        body = {"choices": [{"message": {"content": reply}}]}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)

    monkeypatch.setattr(providers.httpx, "post", post)
    jev = providers.OpenRouterProvider("test-key", "fake-model", "https://openrouter.example.test/chat")

    for provider in (claude, jev):
        assert research.generate_report(loaded, gid, provider=provider).status == "ok"
        research.answer_question(loaded, gid, "Who wins?", provider=provider)
    asked = [call["max_tokens"] for call in claude.client.calls + posted]
    assert len(asked) == 4 and min(asked) >= 16000


# A12 --------------------------------------------------------------------------------------------------------------


def test_one_migration_builds_the_schema_with_no_drift():
    url = make_url(os.environ["DATABASE_URL"]).set(database="nflpi_migration_test")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    drop = text(f'drop database if exists "{url.database}" with (force)')
    env = os.environ | {"DATABASE_URL": url.render_as_string(hide_password=False)}

    def alembic(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120
        )

    with admin.connect() as c:
        c.execute(drop)
        c.execute(text(f'create database "{url.database}"'))
    try:
        upgrade = alembic("upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr
        check = alembic("check")
        assert check.returncode == 0, check.stdout + check.stderr
    finally:
        with admin.connect() as c:
            c.execute(drop)
        admin.dispose()
    versions = sorted((BACKEND / "migrations" / "versions").glob("*.py"))
    # initial schema, then the pick sheet (step 4), then team stars (step 8a)
    assert [v.name[:4] for v in versions] == ["0001", "0002", "0003"]
    for version in versions:
        source = version.read_text()
        # A migration is a frozen record: explicit tables, never the live models (or it can never drift).
        assert "op.create_table" in source and "create_all" not in source and "metadata" not in source


# A13 --------------------------------------------------------------------------------------------------------------


def test_static_files_are_served_with_cache_headers(tmp_path, monkeypatch):
    chunk = tmp_path / "_next" / "static" / "chunks" / "app-abc123.js"
    chunk.parent.mkdir(parents=True)
    chunk.write_text("console.log('app')")
    (tmp_path / "index.html").write_text("<!doctype html><title>Pick'em</title>")
    (tmp_path / "sw.js").write_text("self.addEventListener('fetch', () => {})")
    (tmp_path / "manifest.webmanifest").write_text("{}")
    monkeypatch.setattr(get_settings(), "web_dist_dir", tmp_path)
    web = TestClient(create_app())

    responses = {p: web.get(p) for p in ("/", "/sw.js", "/manifest.webmanifest", "/_next/static/chunks/app-abc123.js")}
    assert {r.status_code for r in responses.values()} == {200}
    cache = {path: r.headers.get("cache-control") for path, r in responses.items()}
    assert "immutable" in (cache.pop("/_next/static/chunks/app-abc123.js") or "")
    assert cache == {"/": "no-cache", "/sw.js": "no-cache", "/manifest.webmanifest": "no-cache"}


# A14 --------------------------------------------------------------------------------------------------------------


def moneylines(home_prob: float) -> dict[str, str]:
    """A two-way line whose no-vig home probability is `home_prob`."""
    odds = round(100 * max(home_prob, 1 - home_prob) / min(home_prob, 1 - home_prob), 2)
    home, away = (-odds, odds) if home_prob >= 0.5 else (odds, -odds)
    return {"home_moneyline": str(home), "away_moneyline": str(away)}


def test_upset_watch_needs_an_underdog_pick_or_a_twelve_point_gap(loaded, client):
    def week() -> dict[str, dict]:
        return {g["game_id"]: g["prediction"] for g in client.get(f"/api/weeks/{CURRENT}/4").json()["games"]}

    stats = {gid: p["stats_only_home_prob"] for gid, p in week().items()}
    side = {gid: 1 if p >= 0.5 else -1 for gid, p in stats.items()}  # +1: the stats model picks the home team
    close, apart, underdog = sorted(stats)
    reingest(
        loaded,
        {
            close: moneylines(stats[close] + 0.11 * side[close]),  # same favorite, 11 points apart
            apart: moneylines(stats[apart] + 0.14 * side[apart]),  # same favorite, 14 points apart
            underdog: moneylines(0.5 - 0.05 * side[underdog]),  # market favors the other team
        },
    )
    engine.refresh_predictions(loaded)
    assert {gid: bool(p["upset_flags"]) for gid, p in week().items()} == {close: False, apart: True, underdog: True}
