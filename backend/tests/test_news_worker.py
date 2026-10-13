"""Step 8g (server side): the worker that polls the news feeds slowly and prunes old rows.

No test touches the network or a real clock: feeds are recorded fixtures behind a fake transport, time is passed in.
Clauses W1 to W10 are frozen in docs/gauntlet/logs/step-8g-server.md section 2a.
"""

import hashlib
import logging
import threading
import time
import types
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import String, cast, func, select

from nflpi import jobs, live_worker, news_worker
from nflpi.ingestion.news import sources
from nflpi.models import IngestionRun, NewsItem, Team
from tests.test_news import CBS, ESPN, RECORDED_AT, Web, public_dns, real_web, seed_names

T0 = RECORDED_AT
HALF_HOUR = timedelta(minutes=30)
DAY = timedelta(hours=24)


@pytest.fixture(autouse=True)
def no_leftover_run(monkeypatch):
    monkeypatch.setattr(news_worker, "_inflight", None)


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> datetime:
        return T0 + timedelta(seconds=self.t)


class Recorder:
    """Wraps a Web: remembers the fake time of every request for a feed (not robots.txt), per host."""

    def __init__(self, web: Web, clock: Clock):
        self.web, self.clock = web, clock
        self.feed_times: dict[str, list[float]] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path != "/robots.txt":
            self.feed_times.setdefault(request.headers["host"], []).append(self.clock.t)
        return self.web(request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def blocked_espn_web() -> Web:
    web = real_web()
    web.routes[(ESPN.host, httpx.URL(ESPN.url).path)] = httpx.Response(403, content=b"")
    return web


def all_blocked_web() -> Web:
    web = blocked_espn_web()
    web.routes[(CBS.host, httpx.URL(CBS.url).path)] = httpx.Response(403, content=b"")
    return web


def old_item(session, title: str, fetched_at: datetime) -> None:
    session.add(
        NewsItem(
            source="espn", title=title, title_sha256=hashlib.sha256(title.encode()).hexdigest(),
            url_canonical=f"https://www.espn.com/{title.replace(' ', '-')}", published_at=None, fetched_at=fetched_at,
            extract="", team_ids=[], player_ids=[], tags=[],
        )  # fmt: skip
    )
    session.commit()


def loop(clock: Clock, hours: float, *, transport, wake: int | None = None, monkeypatch=None, **kw) -> None:
    """Run the real run_forever on the fake clock; stop it after `hours` of fake time."""
    stop = threading.Event()
    if wake is not None:
        monkeypatch.setattr(news_worker, "WAKE_SECONDS", wake)

    def fake_wait(seconds: float) -> bool:
        clock.t += seconds
        return clock.t >= hours * 3600

    news_worker.run_forever(
        stop, now=clock.now, wait=fake_wait, resolver=public_dns, transport=transport, **kw
    )


def gaps(times: list[float]) -> list[float]:
    return [b - a for a, b in zip(times, times[1:], strict=False)]


# ---------------------------------------------------------------- W1


def test_w1_a_step_polls_both_sources_once_and_stores_the_items_tied_by_team(session):
    seed_names(session)
    web = real_web()
    made = news_worker.news_step(session, T0, resolver=public_dns, transport=web.transport)
    assert sorted(r.source for r in made) == ["cbs", "espn"]
    assert all(r.status == "ok" for r in made)
    assert session.scalar(select(func.count()).select_from(NewsItem)) > 20
    assert session.scalar(select(func.count()).select_from(NewsItem).where(cast(NewsItem.team_ids, String) != "[]")) > 0
    assert sum(p.endswith(httpx.URL(ESPN.url).path) for p in web.paths()) == 1


# ---------------------------------------------------------------- W2


@pytest.mark.parametrize("wake", [None, 60])
def test_w2_the_schedule_never_asks_a_source_more_often_than_every_thirty_minutes(session, monkeypatch, wake):
    seed_names(session)
    clock = Clock()
    rec = Recorder(real_web(), clock)
    loop(clock, 3, transport=rec.transport, wake=wake, monkeypatch=monkeypatch)
    assert set(rec.feed_times) == {ESPN.host, CBS.host}
    for host, times in rec.feed_times.items():
        assert len(times) >= 4, host  # it does keep polling
        assert min(gaps(times)) >= HALF_HOUR.total_seconds(), (host, gaps(times))


def test_w2_the_real_wake_is_slow_and_the_frozen_numbers():
    assert news_worker.WAKE_SECONDS == 600
    assert news_worker.RUN_DEADLINE == 180
    assert news_worker.STALE_RUNNING == timedelta(minutes=10)


# ---------------------------------------------------------------- W3


def test_w3_a_blocked_source_is_asked_once_then_left_alone_for_a_day(session):
    seed_names(session)
    clock = Clock()
    rec = Recorder(blocked_espn_web(), clock)
    loop(clock, 49, transport=rec.transport)
    espn_times, cbs_times = rec.feed_times[ESPN.host], rec.feed_times[CBS.host]
    assert 2 <= len(espn_times) <= 3
    assert min(gaps(espn_times)) >= DAY.total_seconds()
    assert len(cbs_times) > 40 and min(gaps(cbs_times)) >= HALF_HOUR.total_seconds()


def test_w3_the_worker_never_changes_how_it_asks_after_a_block(session):
    seed_names(session)
    clock = Clock()
    agents: list[str] = []
    web = blocked_espn_web()

    def spy(request: httpx.Request) -> httpx.Response:
        agents.append(request.headers["user-agent"])
        return web(request)

    loop(clock, 25, transport=httpx.MockTransport(spy))
    assert len(set(agents)) == 1


# ---------------------------------------------------------------- W4, W5


def test_w4_with_every_source_blocked_the_step_returns_and_old_rows_are_still_pruned(session):
    seed_names(session)
    old_item(session, "fetched long ago", T0 - timedelta(days=31))
    made = news_worker.news_step(session, T0, resolver=public_dns, transport=all_blocked_web().transport)
    assert [r.status for r in made] == ["failed", "failed"]
    assert all((r.error or "").startswith("blocked:") for r in made)
    assert session.scalar(select(func.count()).select_from(NewsItem)) == 0
    never = httpx.MockTransport(lambda request: pytest.fail("a blocked source must not be asked again"))
    again = news_worker.news_step(session, T0 + timedelta(minutes=10), resolver=public_dns, transport=never)
    assert again == []  # still inside the 24 h block: nothing asked, nothing raised


def test_w5_old_rows_are_pruned_on_every_step_even_when_nothing_is_due(session):
    seed_names(session)
    web = real_web()
    news_worker.news_step(session, T0, resolver=public_dns, transport=web.transport)
    old_item(session, "fetched long ago", T0 - timedelta(days=31))
    old_item(session, "fetched recently", T0 - timedelta(days=29))
    before = len(web.requests)
    assert news_worker.news_step(session, T0 + timedelta(minutes=5), resolver=public_dns, transport=web.transport) == []
    assert len(web.requests) == before  # nothing was due
    titles = set(session.scalars(select(NewsItem.title)))
    assert "fetched long ago" not in titles and "fetched recently" in titles


# ---------------------------------------------------------------- W6


def test_w6_with_no_teams_loaded_nothing_is_asked_and_nothing_is_recorded(session, caplog):
    assert session.scalar(select(func.count()).select_from(Team)) == 0

    def boom(request):
        raise AssertionError("no request may be made before teams are loaded")

    with caplog.at_level(logging.INFO, logger="nflpi.news_worker"):
        assert news_worker.news_step(session, T0, resolver=public_dns, transport=httpx.MockTransport(boom)) == []
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 0
    assert any("teams" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------- W7


def test_w7_a_hung_run_is_given_up_on_at_the_deadline_and_no_second_run_starts_meanwhile():
    release, started = threading.Event(), threading.Event()
    calls: list[int] = []

    def hang():
        calls.append(1)
        started.set()
        release.wait(5)

    begun = time.monotonic()
    assert news_worker.run_with_deadline(hang, 0.2) is False
    assert time.monotonic() - begun < 2
    assert started.is_set()
    assert news_worker.run_with_deadline(lambda: calls.append(2), 0.2) is False  # the first is still alive
    assert calls == [1]
    release.set()
    news_worker._inflight.join(2)
    assert news_worker.run_with_deadline(lambda: calls.append(3), 1) is True
    assert calls == [1, 3]


def test_w7_a_hung_step_does_not_stop_the_loop_from_waking(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(news_worker, "news_step", lambda *a, **k: release.wait(5))
    monkeypatch.setattr(news_worker, "RUN_DEADLINE", 0.1)
    waits: list[float] = []

    def fake_wait(seconds):
        waits.append(seconds)
        return len(waits) >= 3

    begun = time.monotonic()
    try:
        news_worker.run_forever(threading.Event(), wait=fake_wait)
        assert time.monotonic() - begun < 3 and len(waits) == 3
    finally:
        release.set()


def test_w7_the_loop_runs_the_step_on_a_session_it_opens_inside_the_worker_thread(monkeypatch):
    seen: list[tuple[str, int]] = []

    def spy(session, now, **k):
        seen.append((threading.current_thread().name, id(session)))

    monkeypatch.setattr(news_worker, "news_step", spy)
    waits: list[float] = []
    main = threading.current_thread().name
    news_worker.run_forever(threading.Event(), wait=lambda s: waits.append(s) or len(waits) >= 2)
    assert len(seen) == 2 and all(name != main for name, _ in seen)


def test_w7_each_wake_skipped_because_a_run_is_still_alive_is_warned_about(monkeypatch, caplog):
    release = threading.Event()
    monkeypatch.setattr(news_worker, "news_step", lambda *a, **k: release.wait(5))
    monkeypatch.setattr(news_worker, "RUN_DEADLINE", 0.05)
    waits: list[float] = []
    try:
        with caplog.at_level(logging.WARNING, logger="nflpi.news_worker"):
            news_worker.run_forever(threading.Event(), wait=lambda s: waits.append(s) or len(waits) >= 4)
    finally:
        release.set()
    assert sum("still running" in r.getMessage() for r in caplog.records) >= 3


def test_w9_the_sweep_also_runs_on_every_wake_not_only_at_start_up(session, monkeypatch):
    started = T0 - timedelta(minutes=30)
    session.add(IngestionRun(source="espn", dataset="news:espn", started_at=started, status="running"))
    session.commit()
    monkeypatch.setattr(news_worker, "news_step", lambda *a, **k: None)
    monkeypatch.setattr(news_worker, "sweep_stale_runs", lambda s, n: calls.append(1) or 0)
    calls: list[int] = []
    waits: list[float] = []
    news_worker.run_forever(threading.Event(), wait=lambda s: waits.append(s) or len(waits) >= 3)
    assert len(calls) == 3  # once at start, then after each of the first two waits (the third wait ends the loop)


# ---------------------------------------------------------------- W8


def test_w8_a_step_that_raises_is_logged_by_class_name_only_and_the_loop_goes_on(monkeypatch, caplog):
    calls: list[int] = []

    def explode(*a, **k):
        calls.append(1)
        raise RuntimeError("secret-token-abc https://user:pw@example.test/x")

    monkeypatch.setattr(news_worker, "news_step", explode)
    waits: list[float] = []

    def fake_wait(seconds):
        waits.append(seconds)
        return len(waits) >= 3

    with caplog.at_level(logging.DEBUG):
        news_worker.run_forever(threading.Event(), wait=fake_wait)
    assert len(calls) == 3
    text = " ".join(r.getMessage() + str(r.exc_info) for r in caplog.records)
    assert "RuntimeError" in text and "secret-token-abc" not in text and "pw@" not in text


def test_w8_a_stop_that_is_already_set_ends_the_loop_without_a_run(monkeypatch):
    monkeypatch.setattr(news_worker, "news_step", lambda *a, **k: pytest.fail("no run after stop"))
    stop = threading.Event()
    stop.set()
    news_worker.run_forever(stop, wait=lambda s: pytest.fail("no wait after stop"))


# ---------------------------------------------------------------- W9


def test_w9_old_running_news_rows_are_marked_interrupted_and_nothing_else_is_touched(session):
    def row(dataset, minutes_old, status="running"):
        started = T0 - timedelta(minutes=minutes_old)
        session.add(IngestionRun(source=dataset.split(":")[0], dataset=dataset, started_at=started, status=status))

    row("news:espn", 11)
    row("news:cbs", 5)
    row("live_scores", 11)
    row("news:espn", 90, status="ok")
    session.commit()
    assert news_worker.sweep_stale_runs(session, T0) == 1
    got = {(r.dataset, r.status, r.error) for r in session.scalars(select(IngestionRun))}
    assert ("news:espn", "failed", "interrupted") in got
    assert ("news:cbs", "running", None) in got
    assert ("live_scores", "running", None) in got
    assert ("news:espn", "ok", None) in got


# ---------------------------------------------------------------- W10


def test_w10_the_worker_loop_starts_the_news_thread_once_after_the_live_thread(monkeypatch):
    started: list[str] = []

    class StopLoop(BaseException):
        pass

    def stop_sleeping(_):
        raise StopLoop

    monkeypatch.setattr(live_worker, "start", lambda: started.append("live"))
    monkeypatch.setattr(news_worker, "start", lambda: started.append("news"))
    monkeypatch.setattr(jobs, "tick", lambda *a, **k: None)
    monkeypatch.setattr(jobs, "cycle", lambda *a, **k: None)
    monkeypatch.setattr(jobs, "time", types.SimpleNamespace(monotonic=time.monotonic, sleep=stop_sleeping))
    with pytest.raises(StopLoop):
        jobs.loop()
    assert started == ["live", "news"]


def test_w10_jobs_py_holds_no_news_logic():
    source = open(jobs.__file__).read()
    assert "run_news" not in source and "store.prune" not in source and "news_worker.start()" in source


def test_w10_start_returns_a_running_daemon_thread(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(news_worker, "run_forever", lambda stop, **k: release.wait(5))
    thread = news_worker.start()
    try:
        assert thread.daemon and thread.is_alive() and thread.name == "news-worker"
    finally:
        release.set()
        thread.join(2)


def test_sources_are_still_the_two_landed_feeds():
    assert [s.id for s in sources.SOURCES] == ["espn", "cbs"]

# ---------------------------------------------------------------- Dwight's code review round (C1, C2, C3, L7, L8)


def test_c1_the_sweep_leaves_the_row_of_a_run_that_is_still_alive_alone(session, monkeypatch):
    release, started = threading.Event(), threading.Event()

    def hang(step_session, now, **k):  # the live run writes its own "running" row, long past the sweep limit
        step_session.add(
            IngestionRun(source="espn", dataset="news:espn", started_at=T0 - timedelta(minutes=30), status="running")
        )
        step_session.commit()
        started.set()
        release.wait(5)

    monkeypatch.setattr(news_worker, "news_step", hang)
    monkeypatch.setattr(news_worker, "RUN_DEADLINE", 0.2)
    waits: list[float] = []
    try:
        news_worker.run_forever(threading.Event(), now=lambda: T0, wait=lambda s: waits.append(s) or len(waits) >= 3)
        session.expire_all()
        assert started.is_set()
        assert session.scalar(select(IngestionRun.status)) == "running"  # a live run is not "interrupted"
    finally:
        release.set()


def test_c2_a_stuck_run_is_reported_with_its_age_and_becomes_an_error_after_three_skipped_wakes(monkeypatch, caplog):
    release = threading.Event()
    monkeypatch.setattr(news_worker, "news_step", lambda *a, **k: release.wait(5))
    monkeypatch.setattr(news_worker, "RUN_DEADLINE", 0.05)
    waits: list[float] = []
    try:
        with caplog.at_level(logging.WARNING, logger="nflpi.news_worker"):
            news_worker.run_forever(threading.Event(), wait=lambda s: waits.append(s) or len(waits) >= 6)
    finally:
        release.set()
    skipped = [r for r in caplog.records if "still running" in r.getMessage()]
    assert len(skipped) >= 4 and all("for" in r.getMessage() and " s" in r.getMessage() for r in skipped)
    assert [r.levelno for r in skipped[:2]] == [logging.WARNING, logging.WARNING]
    assert skipped[-1].levelno == logging.ERROR


def test_c3_a_database_that_will_not_open_is_logged_by_class_name_and_does_not_escape_the_thread(monkeypatch, caplog):
    class Down(Exception):
        pass

    def broken():
        raise Down("password=hunter2 host=10.0.0.9")

    monkeypatch.setattr(news_worker, "session_factory", lambda: broken)
    escaped: list[object] = []
    monkeypatch.setattr(threading, "excepthook", lambda args: escaped.append(args))
    waits: list[float] = []
    with caplog.at_level(logging.DEBUG):
        news_worker.run_forever(threading.Event(), wait=lambda s: waits.append(s) or len(waits) >= 2)
    news_worker._inflight.join(2)
    assert escaped == []
    text = " ".join(r.getMessage() + str(r.exc_info) for r in caplog.records)
    assert "Down" in text and "hunter2" not in text and "10.0.0.9" not in text


def test_l7_l8_a_missing_teams_table_is_a_warning_and_a_sweep_that_marks_rows_logs_the_count(session, caplog):
    started = T0 - timedelta(minutes=30)
    session.add(IngestionRun(source="espn", dataset="news:espn", started_at=started, status="running"))
    session.commit()
    with caplog.at_level(logging.INFO, logger="nflpi.news_worker"):
        news_worker.sweep_stale_runs(session, T0)
        news_worker.news_step(session, T0)
    levels = {r.getMessage(): r.levelno for r in caplog.records}
    assert any("1" in m and "interrupted" in m for m in levels)
    assert any("teams" in m and lv == logging.WARNING for m, lv in levels.items())
