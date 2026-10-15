"""Step 8i clauses A1-A14 (docs/gauntlet/logs/step-8i.md): star status alerts and the morning summary."""

import inspect
import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from nflpi import jobs
from nflpi.config import Settings, get_settings
from nflpi.db import session_factory
from nflpi.ingestion import service
from nflpi.models import AppSetting, Game, InjuryReport, Notification, TeamStar
from nflpi.notify import push, star_alerts
from tests.test_hardening import KICKOFF, game_row, http_error, pushes, subscribe  # noqa: F401 - pushes is a fixture

SEASON, WEEK = 2026, 7
SATURDAY_8_ET = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)  # 08:00 EDT, 29 hours before KICKOFF
MORNING = SATURDAY_8_ET + timedelta(minutes=30)
STARS = {  # club -> (slot, rank, player_id, name, position)
    "BUF": [
        ("qb", 1, "A1", "Josh Allen", "QB"), ("off", 1, "C1", "James Cook", "RB"),
        ("off", 2, "K1", "Khalil Shakir", "WR"), ("def", 1, "M1", "Matt Milano", "LB"),
        ("def", 2, "R1", "Ed Oliver", "DT"),
    ],
    "MIA": [
        ("qb", 1, "T1", "Tua Tagovailoa", "QB"), ("off", 1, "W1", "Jaylen Waddle", "WR"),
        ("off", 2, "H1", "De'Von Achane", "RB"), ("def", 1, "P1", "Jalen Ramsey", "CB"),
        ("def", 2, "C2", "Zach Sieler", "DT"),
    ],
}


def add_stars(session) -> None:
    for club, rows in STARS.items():
        for slot, rank, pid, name, pos in rows:
            session.add(TeamStar(season=SEASON, week=WEEK, team=club, slot=slot, rank=rank, player_id=pid, player=name,
                                 position=pos, snaps=100, production=1.0, score=1.0, source="test",
                                 computed_at=KICKOFF - timedelta(days=5)))
    session.commit()


def report(
    session, pid: str, name: str, club: str, status: str | None, observed: datetime | None = None, *,
    practice: str = "Limited", injury: str | None = "Knee", position: str = "WR", week: int = WEEK,
) -> InjuryReport:
    row = InjuryReport(season=SEASON, week=week, team=club, player_id=pid, player=name, position=position,
                       report_status=status, practice_status=practice, injury=injury, source="nflverse",
                       observed_at=observed or KICKOFF - timedelta(hours=3))
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def world(session, pushes):  # noqa: F811
    """One game MIA @ BUF at KICKOFF, ten stars, one subscribed phone, baseline already stored."""
    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    add_stars(session)
    subscribe(session)
    star_alerts.run(session, SATURDAY_8_ET - timedelta(hours=10))  # baseline run: nothing to send yet
    return session


def sent(pushes) -> list[dict]:  # noqa: F811
    return [json.loads(c["data"]) for c in pushes.calls]


def notes(session, kind: str) -> int:
    return session.scalar(select(func.count()).select_from(Notification).where(Notification.kind == kind))


# A1 ---------------------------------------------------------------------------------------------------------------


def test_a1_only_a_new_alert_status_on_a_star_of_an_upcoming_game_is_a_change(world, pushes):  # noqa: F811
    now = KICKOFF - timedelta(minutes=60)
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", practice="Did Not Participate")  # same status, practice moved
    report(world, "P1", "Jalen Ramsey", "MIA", None, position="CB")  # no status
    report(world, "H1", "De'Von Achane", "MIA", "Probable")  # not an alert status
    report(world, "Z9", "Not A Star", "MIA", "Out")  # not on the list
    report(world, "X1", "Other Club Star", "NYJ", "Out")  # no game for that club this week
    assert star_alerts.run(world, now) == {"immediate": 1, "summary": 0}
    assert [m["title"] for m in sent(pushes)] == ["Star out: Jaylen Waddle (MIA)"]
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", practice="Full")  # still the same status
    assert star_alerts.run(world, now) == {"immediate": 0, "summary": 0}


def test_a1_a_status_that_moves_between_alert_statuses_is_a_new_change_each_round(world, pushes):  # noqa: F811
    now = KICKOFF - timedelta(minutes=60)
    for status, expected in (("Questionable", 1), ("Doubtful", 1), ("Questionable", 1)):
        report(world, "W1", "Jaylen Waddle", "MIA", status)
        assert star_alerts.run(world, now)["immediate"] == expected
    assert [m["title"] for m in sent(pushes)] == ["Star questionable: Jaylen Waddle (MIA)",
                                                  "Star doubtful: Jaylen Waddle (MIA)",
                                                  "Star questionable: Jaylen Waddle (MIA)"]


def test_a1b_changes_seen_in_one_round_collapse_to_the_newest_status(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Questionable")
    report(world, "W1", "Jaylen Waddle", "MIA", "Doubtful")
    report(world, "W1", "Jaylen Waddle", "MIA", "Questionable")
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60))["immediate"] == 1
    assert [m["title"] for m in sent(pushes)] == ["Star questionable: Jaylen Waddle (MIA)"]


def test_a1b_a_status_the_player_no_longer_has_is_not_alerted_or_summarised(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Questionable", observed=MORNING - timedelta(hours=3))
    report(world, "W1", "Jaylen Waddle", "MIA", None, observed=MORNING - timedelta(hours=1))  # cleared since
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60)) == {"immediate": 0, "summary": 0}
    assert star_alerts.run(world, MORNING) == {"immediate": 0, "summary": 0}
    assert pushes.calls == []


# A2 ---------------------------------------------------------------------------------------------------------------


def test_a2_the_first_run_with_a_star_list_stores_a_baseline_and_sends_nothing(session, pushes):  # noqa: F811
    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    subscribe(session)
    add_stars(session)
    for club, rows in STARS.items():
        for _, _, pid, name, pos in rows:
            report(session, pid, name, club, "Out", position=pos)
    now = KICKOFF - timedelta(minutes=60)
    assert star_alerts.run(session, now) == {"immediate": 0, "summary": 0}
    assert pushes.calls == [] and session.get(AppSetting, star_alerts.BASELINE_KEY) is not None
    report(session, "W1", "Jaylen Waddle", "MIA", "Questionable")
    assert star_alerts.run(session, now)["immediate"] == 1


def test_a2_without_a_star_list_there_is_no_baseline_and_the_first_list_is_not_a_flood(session, pushes):  # noqa: F811
    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    subscribe(session)
    report(session, "W1", "Jaylen Waddle", "MIA", "Out")
    now = KICKOFF - timedelta(minutes=60)
    assert star_alerts.run(session, now) == {"immediate": 0, "summary": 0}
    assert session.get(AppSetting, star_alerts.BASELINE_KEY) is None
    add_stars(session)  # the list appears; Waddle's Out was already there
    assert star_alerts.run(session, now) == {"immediate": 0, "summary": 0}
    assert pushes.calls == [] and session.get(AppSetting, star_alerts.BASELINE_KEY) is not None


# A3 ---------------------------------------------------------------------------------------------------------------


def test_a3_one_alert_per_change_across_rounds_and_restarts(world, pushes):  # noqa: F811
    row = report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    now = KICKOFF - timedelta(minutes=60)
    assert star_alerts.run(world, now)["immediate"] == 1
    assert star_alerts.run(world, now + timedelta(minutes=5))["immediate"] == 0
    with session_factory()() as restarted:
        assert star_alerts.run(restarted, now + timedelta(minutes=10)) == {"immediate": 0, "summary": 0}
    assert len(pushes.calls) == 1
    assert world.scalar(select(Notification.dedupe_key).where(Notification.kind == "star")) == f"star:{row.id}"


def test_a3_a_quarterback_change_step_7_already_alerted_is_not_alerted_again(world, pushes):  # noqa: F811
    report(world, "A1", "Josh Allen", "BUF", "Out", position="QB")
    world.add(Notification(kind="injury", game_id=None, dedupe_key=f"inj:{SEASON}:{WEEK}:A1:Out", payload={}))
    world.commit()
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60)) == {"immediate": 0, "summary": 0}
    assert pushes.calls == []


def test_a3_a_quarterback_whose_step_7_alert_never_reached_a_device_is_alerted_here(world, pushes):  # noqa: F811
    report(world, "A1", "Josh Allen", "BUF", "Out", position="QB")  # no inj: record, so step 7 did not deliver it
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60))["immediate"] == 1


# A4 ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(minutes=-91), 0),
        (timedelta(minutes=-90, seconds=-1), 0),
        (timedelta(minutes=-90), 1),
        (timedelta(minutes=-1), 1),
        (timedelta(seconds=-1), 1),
        (timedelta(0), 0),
        (timedelta(minutes=5), 0),
    ],
)
def test_a4_a_change_goes_out_on_its_own_only_in_the_last_ninety_minutes(world, pushes, offset, expected):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=KICKOFF - timedelta(hours=4))
    now = KICKOFF + offset
    assert star_alerts.run(world, now)["immediate"] == expected
    assert len(pushes.calls) == expected


def test_a4_the_immediate_alert_expires_at_kickoff_and_is_urgent(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    star_alerts.run(world, KICKOFF - timedelta(minutes=30))
    call = pushes.calls[0]
    headers = {k.lower(): v for k, v in (call.get("headers") or {}).items()}
    assert (call["ttl"], headers.get("urgency")) == (30 * 60, "high")


# A5 ---------------------------------------------------------------------------------------------------------------


def test_a5_nothing_for_a_game_that_is_final_or_postponed(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    for status in ("final", "postponed"):
        game = world.get(Game, "2026_07_MIA_BUF")
        game.status = status
        world.commit()
        assert star_alerts.run(world, KICKOFF - timedelta(minutes=30)) == {"immediate": 0, "summary": 0}
        assert star_alerts.run(world, MORNING) == {"immediate": 0, "summary": 0}
    assert pushes.calls == []


def test_a5_a_game_that_has_kicked_off_is_left_out_of_the_summary(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=KICKOFF - timedelta(hours=1))
    monday = datetime(2026, 10, 19, 12, 30, tzinfo=UTC)
    assert star_alerts.run(world, monday) == {"immediate": 0, "summary": 0}
    assert pushes.calls == []


# A6, A7, A8 -------------------------------------------------------------------------------------------------------


def test_a6_one_summary_per_eastern_day_at_the_set_hour_with_that_days_changes(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Questionable", observed=MORNING - timedelta(hours=50))  # too old
    report(world, "P1", "Jalen Ramsey", "MIA", "Out", observed=MORNING - timedelta(hours=5), position="CB")
    assert star_alerts.run(world, SATURDAY_8_ET - timedelta(minutes=1)) == {"immediate": 0, "summary": 0}  # 07:59
    assert star_alerts.run(world, SATURDAY_8_ET) == {"immediate": 0, "summary": 1}  # 08:00
    assert star_alerts.run(world, MORNING) == {"immediate": 0, "summary": 0}  # once a day
    (message,) = sent(pushes)
    assert message["title"] == "Star report: 1 change today"
    assert message["body"] == "Jalen Ramsey (MIA) Out"
    assert message["url"] == "/"
    assert notes(world, "starsum") == 1


def test_a6_the_summary_waits_for_the_hour_and_is_dropped_after_three_hours(world, pushes):  # noqa: F811
    report(world, "P1", "Jalen Ramsey", "MIA", "Out", observed=MORNING - timedelta(hours=5), position="CB")
    assert star_alerts.run(world, SATURDAY_8_ET + timedelta(hours=3))["summary"] == 0  # 11:00, past the grace
    assert pushes.calls == []
    assert star_alerts.run(world, SATURDAY_8_ET + timedelta(hours=2, minutes=59))["summary"] == 1


def test_a6_the_hour_is_a_setting_and_follows_eastern_time_across_the_clock_change(world, pushes, monkeypatch):  # noqa: F811
    assert Settings.model_fields["star_summary_hour"].default == 8
    with pytest.raises(ValueError):
        Settings(star_summary_hour=21)  # the 3-hour window would cross midnight
    with pytest.raises(ValueError):
        Settings(star_summary_hour=-1)
    report(world, "P1", "Jalen Ramsey", "MIA", "Out", observed=MORNING - timedelta(hours=5), position="CB")
    monkeypatch.setattr(get_settings(), "star_summary_hour", 10)
    assert star_alerts.run(world, MORNING)["summary"] == 0  # 08:30 EDT
    assert star_alerts.run(world, SATURDAY_8_ET + timedelta(hours=2))["summary"] == 1  # 10:00 EDT


def test_a6_the_summary_hour_is_eastern_after_the_clock_goes_back(session, pushes):  # noqa: F811
    service.ingest_schedules(session, [game_row("2026-11-08", "13:00", "2026_09_MIA_BUF", week="9")])
    add_stars(session)
    subscribe(session)
    star_alerts.run(session, datetime(2026, 11, 6, 12, 0, tzinfo=UTC))
    report(session, "P1", "Jalen Ramsey", "MIA", "Out", datetime(2026, 11, 7, 3, 0, tzinfo=UTC), position="CB", week=9)
    assert star_alerts.run(session, datetime(2026, 11, 7, 12, 30, tzinfo=UTC))["summary"] == 0  # 07:30 EST
    assert star_alerts.run(session, datetime(2026, 11, 7, 13, 30, tzinfo=UTC))["summary"] == 1  # 08:30 EST


def test_a6_two_changes_to_one_star_are_one_line_with_the_newest_status_and_the_older_one_never_surfaces(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Questionable", observed=MORNING - timedelta(hours=6))
    second = report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=MORNING - timedelta(hours=2))
    star_alerts.run(world, MORNING)
    (message,) = sent(pushes)
    assert message["body"] == "Jaylen Waddle (MIA) Out"
    keys = set(world.scalars(select(Notification.dedupe_key).where(Notification.kind == "star")))
    assert keys == {f"star:{second.id}"}  # the older row is superseded: never alerted, never listed
    assert star_alerts.run(world, MORNING + timedelta(minutes=5)) == {"immediate": 0, "summary": 0}


def test_a7_no_pending_change_means_no_summary_and_no_record(world, pushes):  # noqa: F811
    assert star_alerts.run(world, MORNING) == {"immediate": 0, "summary": 0}
    assert pushes.calls == [] and notes(world, "starsum") == 0
    assert star_alerts.run(world, MORNING + timedelta(minutes=5)) == {"immediate": 0, "summary": 0}


def test_a8_the_summary_lists_four_stars_then_a_count_and_stays_short_and_plain(world, pushes):  # noqa: F811
    hostile = "Ev\nil\x07 " + "N" * 56  # the column holds 64 characters
    names = [("W1", "Jaylen Waddle", "MIA"), ("P1", "Jalen Ramsey", "MIA"), ("H1", "De'Von Achane", "MIA"),
             ("C2", "Zach Sieler", "MIA"), ("C1", "James Cook", "BUF"), ("K1", hostile, "BUF")]
    for index, (pid, name, club) in enumerate(names):
        if pid == "K1":
            world.get(TeamStar, (SEASON, WEEK, "BUF", "off", 2)).player = name  # a star whose name is hostile
            world.commit()
        report(world, pid, name, club, "Out", observed=MORNING - timedelta(hours=10 - index))
    star_alerts.run(world, MORNING)
    (message,) = sent(pushes)
    lines = message["body"].split("\n")
    assert message["title"] == "Star report: 6 changes today"
    assert len(lines) == 5 and lines[-1] == "+2 more"
    assert len(message["body"]) < 300 and len(message["title"]) < 60
    assert all(ch.isprintable() or ch == "\n" for ch in message["body"])
    assert all(len(line) <= 50 for line in lines)  # name cut at 40 + ' (BUF) Out'


def test_a8_the_immediate_alert_cleans_the_name_and_injury_text_too(world, pushes):  # noqa: F811
    world.get(TeamStar, (SEASON, WEEK, "MIA", "off", 1)).player = "Jay\nlen\x07 " + "W" * 50
    world.commit()
    report(world, "W1", "x", "MIA", "Out", injury="Knee\r\n<b>" + "k" * 50)
    star_alerts.run(world, KICKOFF - timedelta(minutes=30))
    (message,) = sent(pushes)
    for text in (message["title"], message["body"]):
        assert all(ch.isprintable() for ch in text)
    assert len(message["title"]) < 80 and len(message["body"]) < 160
    assert message["body"].endswith("Knee <b>" + "k" * 50 + ".")  # the injury text is cut at 60 characters


def test_a8_format_characters_are_removed_and_a_full_width_injury_text_stays_short(world, pushes):  # noqa: F811
    world.get(TeamStar, (SEASON, WEEK, "MIA", "off", 1)).player = "Jay\u202elen\u200b Wad\u2066dle"
    world.commit()
    report(world, "W1", "x", "MIA", "Out", injury="K" * 64)  # the column holds 64; the cut at 60 is a second guard
    star_alerts.run(world, KICKOFF - timedelta(minutes=30))
    (message,) = sent(pushes)
    assert message["title"] == "Star out: Jaylen Waddle (MIA)"
    assert message["body"] == "MIA @ BUF, 1:00 PM ET. " + "K" * 60 + "."
    assert len(json.dumps(message)) < 500


def test_a6_a_change_seen_just_after_a_summary_is_in_the_next_one(world, pushes):  # noqa: F811
    report(world, "P1", "Jalen Ramsey", "MIA", "Out", observed=SATURDAY_8_ET - timedelta(hours=3), position="CB")
    assert star_alerts.run(world, SATURDAY_8_ET)["summary"] == 1  # day one
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=SATURDAY_8_ET + timedelta(minutes=2))
    day_two = SATURDAY_8_ET + timedelta(days=1, minutes=5)  # 24 h 03 min after the change; the game is at 13:00
    world.get(Game, "2026_07_MIA_BUF").kickoff_utc = day_two + timedelta(hours=6)
    world.commit()
    assert star_alerts.run(world, day_two)["summary"] == 1
    assert [m["body"] for m in sent(pushes)] == ["Jalen Ramsey (MIA) Out", "Jaylen Waddle (MIA) Out"]


def test_a6_a_change_to_a_game_already_in_its_last_ninety_minutes_is_not_repeated_in_the_summary(world, pushes):  # noqa: F811
    early = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)  # a 10:00 ET game on summary day
    world.get(Game, "2026_07_MIA_BUF").kickoff_utc = early
    world.commit()
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=early - timedelta(hours=1))
    assert star_alerts.run(world, early - timedelta(minutes=80)) == {"immediate": 1, "summary": 0}  # 08:40 ET
    assert len(pushes.calls) == 1


def test_m2_a_game_with_no_confirmed_time_never_gets_its_own_alert_but_is_in_the_summary(world, pushes):  # noqa: F811
    game = world.get(Game, "2026_07_MIA_BUF")
    game.time_tbd = True
    world.commit()
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=MORNING)
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=30)) == {"immediate": 0, "summary": 0}
    assert star_alerts.run(world, MORNING + timedelta(days=1))["summary"] == 1  # Sunday 08:30 ET, game 4.5 h away
    assert [m["body"] for m in sent(pushes)] == ["Jaylen Waddle (MIA) Out"]


# A9, A10 ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("failure", [http_error(500), RuntimeError("boom"), ConnectionError("down")])
def test_a9_a_failed_send_records_nothing_never_raises_and_is_retried(world, pushes, failure, caplog):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    pushes.fail = failure
    caplog.set_level(logging.DEBUG)
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60)) == {"immediate": 0, "summary": 0}
    assert notes(world, "star") == 0
    for secret in ("https://push.example.test/iphone", "B" * 87, "a" * 22):
        assert secret not in caplog.text
    pushes.fail = None
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=55)) == {"immediate": 1, "summary": 0}
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=50)) == {"immediate": 0, "summary": 0}


def test_a9_a_failed_summary_is_retried_inside_its_window(world, pushes):  # noqa: F811
    report(world, "P1", "Jalen Ramsey", "MIA", "Out", observed=MORNING - timedelta(hours=5), position="CB")
    pushes.fail = http_error(503)
    assert star_alerts.run(world, MORNING)["summary"] == 0
    assert notes(world, "starsum") == 0
    pushes.fail = None
    assert star_alerts.run(world, MORNING + timedelta(minutes=5))["summary"] == 1


def test_m4_an_error_inside_the_module_logs_its_class_only_never_its_text(world, pushes, monkeypatch, caplog):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    secret = "https://push.example.test/iphone p256dh=" + "B" * 87
    monkeypatch.setattr(push, "send", lambda *a, **k: (_ for _ in ()).throw(RuntimeError(secret)))
    caplog.set_level(logging.DEBUG)
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60)) == {"immediate": 0, "summary": 0}
    assert "RuntimeError" in caplog.text and "push.example.test" not in caplog.text and "B" * 20 not in caplog.text
    assert "Traceback" not in caplog.text


def test_a10_the_round_completes_without_a_subscription_keys_a_list_or_reports(session, pushes, monkeypatch):  # noqa: F811
    assert star_alerts.run(session, MORNING) == {"immediate": 0, "summary": 0}  # empty database
    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    add_stars(session)
    star_alerts.run(session, MORNING)  # baseline
    report(session, "W1", "Jaylen Waddle", "MIA", "Out")
    assert star_alerts.run(session, KICKOFF - timedelta(minutes=30)) == {"immediate": 0, "summary": 0}  # nobody to tell
    subscribe(session)
    monkeypatch.setattr(get_settings(), "vapid_private_key", "")
    assert star_alerts.run(session, KICKOFF - timedelta(minutes=29)) == {"immediate": 0, "summary": 0}  # no keys
    assert pushes.calls == [] and notes(session, "star") == 0


# A11, A13 ---------------------------------------------------------------------------------------------------------


def test_a11_alert_text_never_reads_news():
    source = inspect.getsource(star_alerts)
    assert "NewsItem" not in source and "news" not in source.lower().replace("newest", "")


def test_a13_the_immediate_alert_reads_exactly_like_this(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Doubtful", injury="Hamstring")
    report(world, "H1", "De'Von Achane", "MIA", "Questionable", injury=None)
    star_alerts.run(world, KICKOFF - timedelta(minutes=45))
    first, second = sent(pushes)
    assert first == {"title": "Star doubtful: Jaylen Waddle (MIA)", "body": "MIA @ BUF, 1:00 PM ET. Hamstring.",
                     "url": "/game/?id=2026_07_MIA_BUF"}
    assert second["title"] == "Star questionable: De'Von Achane (MIA)"
    assert second["body"] == "MIA @ BUF, 1:00 PM ET."


# A12 --------------------------------------------------------------------------------------------------------------


def test_a12_the_worker_tick_runs_star_alerts_and_survives_their_failure(session, monkeypatch, caplog):
    calls = []
    monkeypatch.setattr(
        star_alerts, "run", lambda s, now: calls.append(now) or (_ for _ in ()).throw(RuntimeError("secret-endpoint"))
    )
    monkeypatch.setattr(push, "send_kickoff_reminders", lambda s, now: calls.append("reminders") or 0)
    now = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    jobs.tick(session, now)
    assert now in calls and "reminders" in calls
    assert "RuntimeError" in caplog.text and "secret-endpoint" not in caplog.text


# A14 --------------------------------------------------------------------------------------------------------------


def test_a14_each_round_that_sends_logs_one_count_line(world, pushes, caplog):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    caplog.set_level(logging.INFO)
    star_alerts.run(world, KICKOFF - timedelta(minutes=30))
    assert "star alerts: immediate=1 summary=0" in caplog.text


# Added after the mutation sweep (step 8i log, section 5): clauses a first sweep found under-tested ------------------


def test_a1_a_status_row_of_another_week_is_not_the_previous_row(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=KICKOFF - timedelta(days=8), week=WEEK - 1)
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")  # first row of this week: a change whatever last week said
    assert star_alerts.run(world, KICKOFF - timedelta(minutes=60))["immediate"] == 1


def test_a4b_a_game_with_no_confirmed_time_stays_in_the_summary_even_if_its_placeholder_is_near(world, pushes):  # noqa: F811
    game = world.get(Game, "2026_07_MIA_BUF")
    game.time_tbd = True
    game.kickoff_utc = MORNING + timedelta(minutes=30)  # a placeholder 30 minutes after the summary
    world.commit()
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=MORNING - timedelta(hours=1))
    assert star_alerts.run(world, MORNING) == {"immediate": 0, "summary": 1}


def test_a5_a_scheduled_game_with_no_confirmed_time_whose_placeholder_has_passed_is_left_out(world, pushes):  # noqa: F811
    game = world.get(Game, "2026_07_MIA_BUF")
    game.time_tbd = True
    game.kickoff_utc = MORNING - timedelta(hours=1)
    world.commit()
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=MORNING - timedelta(hours=2))
    assert star_alerts.run(world, MORNING) == {"immediate": 0, "summary": 0}
    assert pushes.calls == []


def test_a6_a_change_seen_after_the_days_summary_waits_for_the_next_day(world, pushes):  # noqa: F811
    report(world, "P1", "Jalen Ramsey", "MIA", "Out", observed=SATURDAY_8_ET - timedelta(hours=3), position="CB")
    assert star_alerts.run(world, SATURDAY_8_ET)["summary"] == 1
    report(world, "W1", "Jaylen Waddle", "MIA", "Out", observed=SATURDAY_8_ET + timedelta(minutes=2))
    assert star_alerts.run(world, SATURDAY_8_ET + timedelta(minutes=30)) == {"immediate": 0, "summary": 0}
    assert notes(world, "starsum") == 1 and len(pushes.calls) == 1


def test_a8_the_name_is_cut_at_forty_characters(world, pushes):  # noqa: F811
    world.get(TeamStar, (SEASON, WEEK, "MIA", "off", 1)).player = "N" * 60
    world.commit()
    report(world, "W1", "x", "MIA", "Out")
    star_alerts.run(world, KICKOFF - timedelta(minutes=30))
    assert sent(pushes)[0]["title"] == "Star out: " + "N" * 40 + " (MIA)"


def test_a3b_a_repeated_quarterback_status_is_alerted_even_when_step_7_keyed_the_first_one(world, pushes):  # noqa: F811
    now = KICKOFF - timedelta(minutes=60)
    report(world, "A1", "Josh Allen", "BUF", "Questionable", position="QB")
    world.add(Notification(kind="injury", game_id=None, dedupe_key=f"inj:{SEASON}:{WEEK}:A1:Questionable", payload={}))
    world.commit()
    assert star_alerts.run(world, now)["immediate"] == 0  # step 7 sent that one
    report(world, "A1", "Josh Allen", "BUF", "Out", position="QB")
    assert star_alerts.run(world, now)["immediate"] == 1
    report(world, "A1", "Josh Allen", "BUF", "Questionable", position="QB")  # the same status again, a new change
    assert star_alerts.run(world, now)["immediate"] == 1


def test_a4_the_time_to_live_is_at_least_one_second(world, pushes):  # noqa: F811
    report(world, "W1", "Jaylen Waddle", "MIA", "Out")
    star_alerts.run(world, KICKOFF - timedelta(milliseconds=500))
    assert pushes.calls[0]["ttl"] == 1
