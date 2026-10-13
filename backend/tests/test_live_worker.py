"""Step 15d (server side): the worker that keeps live state fresh while a game is on.

No test touches the network or a real clock: every source call goes to a fake `get`, time is passed in.
"""

import copy
import functools
import logging
import threading
import time
import types
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from nflpi import jobs, live_worker
from nflpi.ingestion.live import espn, fetch, run, store
from nflpi.models import Game, IngestionRun, LiveState, SourceStatus
from tests.test_live import JSON, KEY, in_progress, public_dns, recorded, seed_game

T0 = datetime(2026, 10, 13, 1, 15, tzinfo=UTC)  # one hour after the recorded BUF @ LA kickoff (00:15 UTC)
KICKOFF = datetime(2026, 10, 13, 0, 15, tzinfo=UTC)
EMPTY_ESPN = {"events": []}
EMPTY_KALSHI = {"markets": [], "cursor": ""}


class Net:
    """A fake `get` that routes by host, counts calls per source and can charge fake time per call."""

    def __init__(self, espn_reply=None, odds_credits: int | None = 500, cost: float = 0.0, clock=None):
        self.espn_routes = espn_reply if espn_reply is not None else {espn.SCOREBOARD_URL: EMPTY_ESPN}
        self.calls: list[str] = []
        self.credits = odds_credits
        self.cost, self.clock = cost, clock

    def count(self, source: str) -> int:
        marker = {"espn": "espn.com", "kalshi": "kalshi.com", "odds": "the-odds-api.com"}[source]
        return sum(marker in url for url in self.calls)

    def __call__(self, url: str) -> fetch.JsonResult:
        self.calls.append(url)
        if self.clock is not None:
            self.clock.t += self.cost
        if "the-odds-api.com" in url:
            headers = {}
            if self.credits is not None:
                self.credits -= 1
                headers = {"x-requests-remaining": str(self.credits)}
            return fetch.JsonResult(200, [], headers)
        if "kalshi.com" in url:
            return fetch.JsonResult(200, copy.deepcopy(EMPTY_KALSHI), {})
        return fetch.JsonResult(200, copy.deepcopy(self.espn_routes[url]), {})


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def step(session, now, schedule=None, net=None, clock=None, key=KEY):
    return live_worker.live_step(
        session, now, schedule or live_worker.Schedule(), get=net, clock=clock or Clock(), odds_key=key
    )


def play(session, start: datetime, seconds: int, net, *, every=5, key=KEY, schedule=None):
    schedule = schedule or live_worker.Schedule()
    for i in range(0, seconds, every):
        schedule = step(session, start + timedelta(seconds=i), schedule, net, key=key).schedule
    return schedule


def buf_la(session, kickoff=KICKOFF) -> Game:
    return seed_game(session, "BUF", "LA", kickoff, status="scheduled")


# ----------------------------------------------------------------------------------------------- W1, W2


def test_with_no_game_in_any_window_a_wake_makes_no_call_and_writes_nothing(session):
    net = Net()
    result = step(session, T0, net=net)
    assert net.calls == [] and result.results == ()
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 0
    assert session.scalar(select(func.count()).select_from(SourceStatus)) == 0


def test_a_week_of_wakes_in_the_off_season_makes_no_call(session):
    net = Net()
    play(session, T0, 7 * 86400, net, every=3600)
    assert net.calls == []


@pytest.mark.parametrize(
    "kickoff_offset",
    [timedelta(hours=-8, seconds=-1), timedelta(days=-3), timedelta(hours=25), timedelta(days=4)],
)
def test_a_game_outside_every_window_makes_no_call(session, kickoff_offset):
    buf_la(session, T0 + kickoff_offset)
    net = Net()
    step(session, T0, net=net)
    assert net.calls == []


def test_a_final_game_with_its_win_probability_is_not_in_play_so_nothing_is_fetched_for_it(session):
    game = buf_la(session)
    store.add_live_state(
        session,
        game_id=game.game_id,
        event_id="401872994",
        fetched_at=T0,
        state="post",
        home_score=34,
        away_score=37,
        period=4,
        clock="0:00",
        home_wp=0.0,
        tie_wp=0.0,
        last_play_id="1",
    )
    session.commit()
    net = Net()
    step(session, T0 + timedelta(minutes=1), net=net)
    assert net.calls == []


def test_a_game_kicking_off_now_is_in_play_and_eight_hours_after_kickoff_it_is_not(session):
    buf_la(session)
    assert live_worker.in_window(session, KICKOFF, timedelta(0))
    assert live_worker.in_window(session, KICKOFF + timedelta(hours=8) - timedelta(seconds=1), timedelta(0))
    assert not live_worker.in_window(session, KICKOFF + timedelta(hours=8), timedelta(0))
    assert not live_worker.in_window(session, KICKOFF - timedelta(seconds=1), timedelta(0))
    assert live_worker.in_window(session, KICKOFF - timedelta(hours=2), timedelta(hours=2))


def test_a_final_game_still_missing_its_final_win_probability_stays_in_play_until_the_summary_is_stored(session):
    game = buf_la(session)
    store.add_live_state(
        session,
        game_id=game.game_id,
        event_id="401872994",
        fetched_at=T0,
        state="post",
        home_score=34,
        away_score=37,
        period=4,
        clock="0:00",
        home_wp=None,
        tie_wp=None,
        last_play_id="1",
    )
    session.commit()
    assert live_worker.in_window(session, T0 + timedelta(minutes=1), timedelta(0))
    final = {
        espn.SCOREBOARD_URL: recorded("espn_scoreboard_final.json"),
        espn.summary_url("401872994"): recorded("espn_summary_buf_lar.json"),
    }
    step(session, T0 + timedelta(minutes=1), net=Net(final))
    assert session.scalars(select(LiveState).order_by(LiveState.id.desc())).first().home_wp is not None
    assert not live_worker.in_window(session, T0 + timedelta(minutes=2), timedelta(0))


# ----------------------------------------------------------------------------------------------- W3


def test_a_game_in_play_gets_its_score_stored_and_the_next_wake_inside_30_seconds_fetches_nothing(session):
    buf_la(session)
    net = Net(in_progress())
    first = step(session, T0, net=net)
    assert [r.source for r in first.results].count("espn_live") == 1
    assert net.count("espn") == 2  # scoreboard + one summary
    assert [r.state for r in session.scalars(select(LiveState))] == ["in"]
    before = len(net.calls)
    step(session, T0 + timedelta(seconds=10), first.schedule, net)
    assert len(net.calls) == before
    step(session, T0 + timedelta(seconds=31), first.schedule, net)
    assert net.count("espn") == 4  # the scoreboard and the summary again, 31 s after the first


def test_over_a_three_hour_game_espn_is_fetched_about_every_30_seconds(session):
    buf_la(session)
    net = Net(in_progress())
    play(session, T0, 3 * 3600, net)
    scoreboards = sum(url == espn.SCOREBOARD_URL for url in net.calls)
    assert 300 <= scoreboards <= 360


def test_when_the_game_turns_final_polling_stops(session):
    buf_la(session)
    net = Net(in_progress())
    schedule = step(session, T0, net=net).schedule
    final = {espn.SCOREBOARD_URL: recorded("espn_scoreboard_final.json")}
    final.update({espn.summary_url("401872994"): recorded("espn_summary_buf_lar.json")})
    net.espn_routes = final
    schedule = step(session, T0 + timedelta(seconds=40), schedule, net).schedule
    assert [r.state for r in session.scalars(select(LiveState))] == ["in", "post"]
    before = len(net.calls)
    play(session, T0 + timedelta(minutes=5), 600, net, schedule=schedule)
    assert len(net.calls) == before


# ----------------------------------------------------------------------------------------------- W4


def test_kalshi_is_asked_only_inside_the_two_hour_lead_and_every_120_seconds(session):
    buf_la(session, T0 + timedelta(hours=1))
    net = Net()
    play(session, T0, 600, net)
    assert net.count("kalshi") == 5  # t = 0, 120, 240, 360, 480
    assert net.count("espn") == 0  # not in play yet
    other = Net()
    session.query(Game).delete()
    session.commit()
    buf_la(session, T0 + timedelta(hours=3))
    play(session, T0, 600, other)
    assert other.count("kalshi") == 0


def test_the_odds_api_is_asked_inside_the_24_hour_lead_every_6_hours_and_never_outside(session):
    buf_la(session, T0 + timedelta(hours=12))
    net = Net()
    play(session, T0, 12 * 3600, net, every=300)
    assert net.count("odds") == 2  # t = 0 and t = 6 h
    session.query(Game).delete()
    session.commit()
    buf_la(session, T0 + timedelta(hours=25))
    far = Net()
    play(session, T0, 3000, far, every=300)  # kickoff stays more than 24 h away
    assert far.count("odds") == 0


def test_without_an_odds_key_the_odds_api_is_never_asked_and_nothing_fails(session):
    buf_la(session, T0 + timedelta(hours=1))
    net = Net()
    play(session, T0, 1800, net, key="")
    assert net.count("odds") == 0 and net.count("kalshi") > 0


def test_a_game_in_play_gets_all_three_sources(session):
    buf_la(session)
    net = Net(in_progress())
    step(session, T0, net=net)
    assert net.count("espn") and net.count("kalshi") == 1 and net.count("odds") == 1


# ----------------------------------------------------------------------------------------------- W5


def test_a_31_day_month_with_a_game_every_day_stays_far_under_the_odds_budget(session):
    first = datetime(2026, 10, 1, 20, 15, tzinfo=UTC)
    for day in range(31):
        seed_game(
            session, "BUF", "MIA", first + timedelta(days=day), game_id=f"2026_{day:02d}_BUF_MIA", status="scheduled"
        )
    net = Net(espn_reply={espn.SCOREBOARD_URL: EMPTY_ESPN})
    play(session, first - timedelta(hours=26), 31 * 86400, net, every=1800)
    calls = net.count("odds")
    assert 100 <= calls <= 124, calls  # 4 a day at most
    assert net.credits >= 500 - 124 and net.credits >= 50


def test_a_restarted_worker_cannot_spend_a_second_odds_credit_inside_the_6_hour_floor(session):
    buf_la(session, T0 + timedelta(hours=3))
    net = Net()
    step(session, T0, live_worker.Schedule(), net)
    assert net.count("odds") == 1
    for minutes in (1, 59, 5 * 60 + 59):  # the old worker object is gone; a new one starts with no memory
        step(session, T0 + timedelta(minutes=minutes), live_worker.Schedule(), net)
    assert net.count("odds") == 1
    step(session, T0 + timedelta(hours=6), live_worker.Schedule(), net)
    assert net.count("odds") == 2


def test_a_credit_header_below_50_stops_the_odds_api_for_35_days(session):
    for day in range(45):
        seed_game(
            session,
            "BUF",
            "MIA",
            T0 + timedelta(days=day, hours=1),
            game_id=f"2026_{day:02d}_BUF_MIA",
            status="scheduled",
        )
    net = Net(odds_credits=50)  # the first call brings it to 49
    play(session, T0, 40 * 86400, net, every=6 * 3600)
    assert net.count("odds") == 2  # one call, 35 days stopped, then one call that refreshes the count


# ----------------------------------------------------------------------------------------------- W6


def test_the_deadline_wrapper_refuses_a_fetch_started_after_the_run_deadline():
    clock, calls = Clock(), []

    def get(url):
        calls.append(url)
        clock.t += 10
        return fetch.JsonResult(200, {}, {})

    wrapped = live_worker.with_deadline(get, 25, clock)
    for _ in range(3):
        wrapped("u")
    with pytest.raises(fetch.FetchError, match="deadline"):
        wrapped("u")
    assert len(calls) == 3
    with pytest.raises(fetch.FetchError):
        wrapped("u")
    assert len(calls) == 3


def test_a_slow_source_costs_a_run_at_most_the_deadline_so_summaries_are_skipped_not_waited_for(session, monkeypatch):
    buf_la(session)
    clock = Clock()
    monkeypatch.setattr(live_worker, "ESPN_DEADLINE", 5)
    net = Net(in_progress(), cost=10, clock=clock)
    result = step(session, T0, net=net, clock=clock)
    assert net.count("espn") == 1  # the scoreboard; the summary was refused by the deadline, not fetched
    row = session.scalar(select(LiveState))
    assert row.state == "in" and row.home_wp is None  # missing stays missing
    assert next(r for r in result.results if r.source == "espn_live").status == "ok"


def test_the_default_deadlines_are_45_seconds(session):
    assert live_worker.ESPN_DEADLINE == 45 and live_worker.QUOTE_DEADLINE == 45


# ----------------------------------------------------------------------------------------------- W7


class Killed(BaseException):
    """The process dying mid run (a signal, an out of memory kill)."""


def test_a_killed_run_leaves_a_running_row_a_reserved_source_and_no_half_written_state(session):
    buf_la(session)
    net = Net(in_progress())

    def dying(url):
        raise Killed

    with pytest.raises(Killed):
        step(session, T0, net=dying)
    session.rollback()
    runs = list(session.scalars(select(IngestionRun)))
    assert [(r.source, r.status) for r in runs] == [("espn", "running")]
    assert session.scalar(select(func.count()).select_from(LiveState)) == 0
    assert store.source_blocked_until(session, "espn_live") == T0 + timedelta(seconds=30)
    # a restart does not refetch at once
    step(session, T0 + timedelta(seconds=5), net=net)
    assert net.count("espn") == 0


def test_the_sweep_fails_old_running_rows_of_the_live_sources_and_nothing_else(session):
    old, fresh = T0 - timedelta(minutes=11), T0 - timedelta(minutes=9)
    session.add_all(
        [
            IngestionRun(source="espn", dataset="live_scores", status="running", started_at=old),
            IngestionRun(source="kalshi", dataset="market_quotes", status="running", started_at=old),
            IngestionRun(source="oddsapi", dataset="market_quotes", status="running", started_at=old),
            IngestionRun(source="espn", dataset="live_scores", status="running", started_at=fresh),
            IngestionRun(source="espn", dataset="live_scores", status="ok", started_at=old),
            IngestionRun(source="nflverse", dataset="games", status="running", started_at=old),
            IngestionRun(source="espn", dataset="head_coaches", status="running", started_at=old),
            IngestionRun(source="kalshi", dataset="games", status="running", started_at=old),
        ]
    )
    session.commit()
    assert live_worker.sweep_stale_runs(session, T0) == 3
    rows = {(r.source, r.started_at, r.status): r for r in session.scalars(select(IngestionRun))}
    assert rows[("espn", old, "failed")].error == "interrupted"
    assert rows[("kalshi", old, "failed")].finished_at == T0
    assert ("espn", fresh, "running") in rows and ("nflverse", old, "running") in rows
    assert ("espn", old, "running") in rows  # the head_coaches row the main loop owns
    assert ("kalshi", old, "running") in rows  # a kalshi row of another dataset
    assert ("espn", old, "ok") in rows
    assert live_worker.sweep_stale_runs(session, T0) == 0


# ----------------------------------------------------------------------------------------------- W8


def test_one_source_blowing_up_does_not_stop_the_others_and_its_message_is_never_logged(session, monkeypatch, caplog):
    buf_la(session)

    def boom(*a, **k):
        raise RuntimeError(f"secret apiKey={KEY}")

    monkeypatch.setattr(run, "refresh_live_games", boom)
    net = Net(in_progress())
    with caplog.at_level(logging.DEBUG):
        result = step(session, T0, net=net)
    assert net.count("kalshi") == 1 and net.count("odds") == 1
    assert KEY not in caplog.text and "secret" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert {r.source for r in result.results} == {"kalshi", "oddsapi"}


def test_through_the_real_fetch_path_with_every_logger_turned_up_the_key_never_reaches_a_log(session, caplog):
    buf_la(session, T0 + timedelta(hours=1))
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = b"[]" if "the-odds-api.com" in request.headers["host"] else b'{"markets": [], "cursor": ""}'
        return httpx.Response(200, headers=JSON | {"x-requests-remaining": "499"}, content=body)

    get = functools.partial(fetch.fetch_json, resolver=public_dns, transport=httpx.MockTransport(handler))
    for name in ("", "httpx", "httpcore", "nflpi"):
        caplog.set_level(logging.DEBUG, logger=name)
    step(session, T0, net=get)
    assert any("apiKey=" + KEY in str(r.url) for r in seen)  # the key really was sent
    assert KEY not in caplog.text and "apiKey=" not in caplog.text
    stored = " ".join(f"{r.error} {r.dataset}" for r in session.scalars(select(IngestionRun)))
    assert KEY not in stored


def test_the_job_logging_setup_cannot_turn_the_http_loggers_back_up():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
    source = open(jobs.__file__).read()
    assert "httpx" not in source and "httpcore" not in source


def test_the_thread_says_when_it_starts(session, caplog):
    with caplog.at_level(logging.INFO, logger="nflpi.live_worker"):
        live_worker.run_forever(threading.Event(), get=Net(), wait=lambda s: True)
    assert "live worker started" in caplog.text


def test_a_broken_window_query_is_logged_by_class_and_returns_normally(session, monkeypatch, caplog):
    monkeypatch.setattr(live_worker, "_candidates", lambda *a, **k: (_ for _ in ()).throw(ValueError(f"x{KEY}")))
    with caplog.at_level(logging.DEBUG):
        result = step(session, T0, net=Net())
    assert result.results == () and KEY not in caplog.text and "ValueError" in caplog.text


# ----------------------------------------------------------------------------------------------- W9


def test_run_forever_sweeps_first_survives_a_failing_step_and_stops_when_told(session, monkeypatch):
    session.add(
        IngestionRun(
            source="kalshi", dataset="market_quotes", status="running", started_at=datetime(2020, 1, 1, tzinfo=UTC)
        )
    )
    session.commit()
    seen = []

    def flaky_step(*a, **k):
        seen.append(1)
        raise RuntimeError("down")

    monkeypatch.setattr(live_worker, "live_step", flaky_step)
    stop, waits = threading.Event(), []

    def wait(seconds):
        waits.append(seconds)
        return len(waits) >= 3

    live_worker.run_forever(stop, get=Net(), wait=wait)
    assert len(seen) == 3 and waits == [live_worker.WAKE_SECONDS] * 3
    session.expire_all()
    assert session.scalar(select(IngestionRun.status)) == "failed"


def test_start_returns_at_once_with_a_daemon_thread(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(live_worker, "run_forever", lambda stop, **k: release.wait(5))
    thread = live_worker.start()
    try:
        assert thread.daemon and thread.is_alive()
    finally:
        release.set()
        thread.join(2)


def test_the_worker_loop_starts_the_live_thread_once(monkeypatch):
    started = []

    class StopLoop(BaseException):
        pass

    def stop_sleeping(_):
        raise StopLoop

    monkeypatch.setattr(live_worker, "start", lambda: started.append(1))
    monkeypatch.setattr(jobs, "tick", lambda *a, **k: None)
    monkeypatch.setattr(jobs, "cycle", lambda *a, **k: None)
    monkeypatch.setattr(jobs, "time", types.SimpleNamespace(monotonic=time.monotonic, sleep=stop_sleeping))
    with pytest.raises(StopLoop):
        jobs.loop()
    assert started == [1]


def test_the_frozen_schedule_numbers():
    assert live_worker.WAKE_SECONDS == 5
    assert live_worker.MAX_GAME == timedelta(hours=8)
    assert live_worker.KALSHI_EVERY == timedelta(seconds=120) and live_worker.KALSHI_LEAD == timedelta(hours=2)
    assert live_worker.ODDS_EVERY == timedelta(hours=6) and live_worker.ODDS_LEAD == timedelta(hours=24)
    assert live_worker.STALE_RUNNING == timedelta(minutes=10)
    assert live_worker.ODDS_EVERY >= run.ODDS_MIN_INTERVAL and live_worker.KALSHI_EVERY >= run.KALSHI_MIN_INTERVAL
