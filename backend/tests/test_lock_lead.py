"""Step lock-lead: picks lock a set time before kickoff (Yahoo locks 15 minutes before), plus the 19a SEA@DEN
fresh-line fixes (C1-C3, D80). Clauses in docs/gauntlet/logs/step-lock15.md section 2. P tests need no database."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.test_hardening import pushes  # noqa: F401 - fixture

K = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)  # Sunday 13:00 EDT
SEA_DEN = datetime(2026, 10, 16, 0, 15, tzinfo=UTC)  # 2026_06_SEA_DEN kickoff


def _game(**over):
    from nflpi.models import Game

    return Game(**({"game_id": "g", "kickoff_utc": K, "status": "scheduled", "time_tbd": False} | over))


# --- P1 the setting ---------------------------------------------------------------------------------

def test_p1_the_lock_lead_is_one_setting_fifteen_minutes_by_default():
    from pydantic import ValidationError

    from nflpi.config import Settings

    assert Settings.model_fields["pick_lock_minutes"].default == 15
    for bad in (-1, 121):
        with pytest.raises(ValidationError):
            Settings(pick_lock_minutes=bad)


# --- P2 one lock rule -------------------------------------------------------------------------------

def test_p2_a_game_locks_fifteen_minutes_before_kickoff():
    from nflpi.predictions.sheet import is_locked

    assert is_locked(_game(), K - timedelta(minutes=16)) is False
    assert is_locked(_game(), K - timedelta(minutes=15)) is True
    assert is_locked(_game(), K - timedelta(minutes=14)) is True
    assert is_locked(_game(status="postponed"), K) is False
    assert is_locked(_game(time_tbd=True), K) is False
    assert is_locked(_game(status="final"), K - timedelta(days=1)) is True


def test_p2b_the_lead_follows_the_setting(monkeypatch):
    from nflpi.config import get_settings
    from nflpi.predictions.sheet import is_locked

    monkeypatch.setattr(get_settings(), "pick_lock_minutes", 0)
    assert is_locked(_game(), K - timedelta(minutes=1)) is False
    assert is_locked(_game(), K) is True


# --- P3 refresh targets: the last refresh lands 15 minutes before the lock --------------------------

def test_p3_refresh_targets_are_ninety_and_thirty_minutes_before_kickoff(monkeypatch):
    from nflpi.config import get_settings
    from nflpi.predictions.fresh_line import TARGET_SLACK, until_next_target

    now = K - timedelta(minutes=35)
    assert until_next_target([K], now) == timedelta(minutes=5) + TARGET_SLACK  # -30 target
    assert until_next_target([K], K - timedelta(minutes=100)) == timedelta(minutes=10) + TARGET_SLACK  # -90
    assert until_next_target([K], K - timedelta(minutes=29)) is None
    monkeypatch.setattr(get_settings(), "pick_lock_minutes", 30)
    assert until_next_target([K], K - timedelta(minutes=50)) == timedelta(minutes=5) + TARGET_SLACK  # -45


# --- P4 the 19a SEA@DEN numbers (research/nfl-pickem/19a-sea-den-queries.txt) -----------------------

def _line(prob, source, seen):
    from nflpi.predictions.fresh_line import Line

    return Line(prob, source, seen)


def _quote(prob, seen):
    from nflpi.predictions.fresh_line import Quote

    return Quote("kalshi", prob, seen)


def test_p4_c2_c3_at_00_10_kalshi_wins_over_an_nflverse_line_that_moved_seconds_later():
    from nflpi.predictions.fresh_line import choose_line

    now = datetime(2026, 10, 16, 0, 10, 28, tzinfo=UTC)
    nflverse = _line(0.4170, "nflverse", datetime(2026, 10, 16, 0, 9, 36, tzinfo=UTC))  # our ingest time
    quote = _quote(0.4307, datetime(2026, 10, 16, 0, 9, 26, tzinfo=UTC))
    previous = _line(0.4279, "nflverse", None)  # row 468, no market_seen_at
    line, refused = choose_line(nflverse, [quote], previous, now=now, kickoff=SEA_DEN)
    assert (line.prob, line.source, refused) == (0.4307, "kalshi", None)  # 1.4 points from the line in use


def test_p4b_at_23_57_a_kalshi_price_under_a_point_from_nflverse_keeps_nflverse():
    from nflpi.predictions.fresh_line import choose_line

    now = datetime(2026, 10, 15, 23, 57, 44, tzinfo=UTC)
    nflverse = _line(0.4279, "nflverse", datetime(2026, 10, 15, 22, 37, 26, tzinfo=UTC))
    quote = _quote(0.4350, datetime(2026, 10, 15, 23, 55, 0, tzinfo=UTC))  # confirmed by the 23:55 poll
    line, _ = choose_line(nflverse, [quote], _line(0.4279, "nflverse", None), now=now, kickoff=SEA_DEN)
    assert (line.prob, line.source) == (0.4279, "nflverse")  # 0.7 point: the churn guard holds, by design


def test_p4c_c3_the_churn_guard_compares_with_the_nflverse_line_in_use_not_an_older_row():
    from nflpi.predictions.fresh_line import choose_line

    now = datetime(2026, 10, 18, 15, 30, tzinfo=UTC)
    nflverse = _line(0.600, "nflverse", now - timedelta(minutes=2))
    line, _ = choose_line(nflverse, [_quote(0.615, now - timedelta(minutes=1))], _line(0.610, "nflverse", None),
                          now=now, kickoff=K)
    assert (line.prob, line.source) == (0.615, "kalshi")  # 1.5 points from nflverse 0.600, though 0.5 from 0.610


# --- D tests with the database (run in PR CI; the Mac test database is off) --------------------------

def _kickoff_in(loaded, minutes):
    from sqlalchemy import select

    from nflpi.models import Game
    from tests.conftest import CURRENT

    game = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)
                          .order_by(Game.game_id)).first()
    game.kickoff_utc = datetime.now(UTC) + timedelta(minutes=minutes)
    loaded.commit()
    return game


def test_d1_a_pick_or_points_change_inside_the_lead_is_refused(loaded, client):
    game = _kickoff_in(loaded, 14)
    res = client.put(f"/api/picks/{game.game_id}", json={"team": game.home_team})
    assert res.status_code == 409 and "15 minutes before kickoff" in res.json()["detail"]
    assert client.put(f"/api/picks/{game.game_id}/points", json={"points": 1}).status_code == 409
    game = _kickoff_in(loaded, 16)
    assert client.put(f"/api/picks/{game.game_id}", json={"team": game.home_team}).status_code == 200


def test_d2_the_api_marks_the_game_locked_and_says_the_lead(loaded, client):
    from tests.conftest import CURRENT

    game = _kickoff_in(loaded, 14)
    week = client.get(f"/api/weeks/{CURRENT}/4").json()
    assert next(g for g in week["games"] if g["game_id"] == game.game_id)["locked"] is True
    assert client.get("/api/meta").json()["pick_lock_minutes"] == 15


def test_d3_the_sheet_freezes_a_game_at_its_lock(loaded):
    from nflpi.models import SheetEntry
    from nflpi.predictions import sheet

    game = _kickoff_in(loaded, 60)
    sheet.finalize(loaded, game.kickoff_utc - timedelta(minutes=16))
    loaded.commit()
    assert loaded.get(SheetEntry, game.game_id) is None
    sheet.finalize(loaded, game.kickoff_utc - timedelta(minutes=15))
    loaded.commit()
    assert loaded.get(SheetEntry, game.game_id) is not None


def test_d4_the_game_day_reminder_counts_down_to_the_lock(session, pushes):  # noqa: F811
    from nflpi.ingestion import service
    from nflpi.notify import push
    from tests.test_alerts import SUNDAY_EARLY
    from tests.test_hardening import game_row, subscribe

    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    subscribe(session)
    assert push.send_kickoff_reminders(session, SUNDAY_EARLY - timedelta(minutes=76)) == 0  # 61 min before lock
    assert push.send_kickoff_reminders(session, SUNDAY_EARLY - timedelta(minutes=74)) == 1
    assert "12:45" in str(pushes.calls[-1]["data"]) and "lock" in str(pushes.calls[-1]["data"]).lower()


def test_d5_no_prediction_alert_after_the_lock(session, pushes):  # noqa: F811
    from nflpi.ingestion import service
    from nflpi.notify import push
    from nflpi.predictions.events import ChangeEvent
    from tests.test_alerts import SUNDAY_EARLY
    from tests.test_hardening import game_row, subscribe

    service.ingest_schedules(session, [game_row("2026-10-18", "13:00")])
    subscribe(session)
    event = ChangeEvent("2026_07_MIA_BUF", 0.55, 0.45, "BUF", "MIA", "flip")
    assert push.alert_prediction_changes(session, [event], SUNDAY_EARLY - timedelta(minutes=10)) == 0
    assert push.alert_prediction_changes(session, [event], SUNDAY_EARLY - timedelta(minutes=20)) == 1


def test_d6_c1_a_stable_kalshi_price_stays_current_while_polls_confirm_it(loaded):
    from nflpi.models import IngestionRun, MarketQuote
    from nflpi.predictions.fresh_line import pregame_quotes

    game = _kickoff_in(loaded, 600)
    stored = datetime(2026, 10, 15, 22, 15, 4, tzinfo=UTC)
    loaded.add(MarketQuote(game_id=game.game_id, source="kalshi", kind="pregame", home_prob=0.4350,
                           away_prob=0.5650, fetched_at=stored))
    for minute, status in ((53, "ok"), (55, "ok"), (56, "failed")):
        at = datetime(2026, 10, 15, 23, minute, tzinfo=UTC)
        loaded.add(IngestionRun(source="kalshi", dataset="market_quotes", started_at=at, finished_at=at,
                                status=status, rows=0))
    loaded.commit()
    now = datetime(2026, 10, 15, 23, 57, 44, tzinfo=UTC)
    quotes = pregame_quotes(loaded, [game.game_id], now)[game.game_id]
    assert [(q.home_prob, q.seen_at) for q in quotes] == [(0.4350, datetime(2026, 10, 15, 23, 55, tzinfo=UTC))]
    # with no poll after it was stored, the 102-minute-old price is not fresh
    assert pregame_quotes(loaded, [game.game_id], datetime(2026, 10, 15, 23, 52, tzinfo=UTC)) == {}
