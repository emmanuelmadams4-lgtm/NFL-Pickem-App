"""Data timing (step 13, B8): when the line, each club's quarterback and injury rows were first seen and last changed.

Made-up rows only. Every ingestion time is passed in, so the clock never matters.
"""

import random
from datetime import UTC, datetime, timedelta

from nflpi.analytics import timing
from nflpi.ingestion import nflverse, service
from tests.conftest import _row

KICKOFF = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)
T0 = KICKOFF - timedelta(hours=100)
T1 = KICKOFF - timedelta(hours=60)
T2 = KICKOFF - timedelta(hours=30)
AFTER = KICKOFF + timedelta(hours=1)
GID = "2026_06_MIA_BUF"


def game_row(away="MIA", home="BUF", kickoff=KICKOFF, **over) -> dict:
    return _row(2026, 6, kickoff, away, home, random.Random(1), False) | over


def ingest(session, at, *rows):
    service.upsert_games(session, nflverse.parse_games(list(rows), 2018), at)


def injury_row(status="Questionable", player="A Passer", team="BUF") -> dict:
    return {
        "season": "2026",
        "game_type": "REG",
        "team": team,
        "week": "6",
        "gsis_id": "00-1",
        "position": "QB",
        "full_name": player,
        "report_primary_injury": "Knee",
        "practice_primary_injury": "",
        "report_status": status,
        "practice_status": "Limited Participation in Practice",
    }


# --- the line --------------------------------------------------------------------------------------------------------


def test_unchanged_line_on_a_new_run_does_not_move_last_changed(session):
    ingest(session, T0, game_row())
    ingest(session, T1, game_row())
    line = timing.game_timing(session, GID)["line"]
    assert line == {"first_seen": T0, "last_changed": T0}


def test_changed_line_moves_last_changed_and_never_first_seen(session):
    ingest(session, T0, game_row())
    ingest(session, T1, game_row(spread_line="3.5"))
    ingest(session, T2, game_row(spread_line="3.5"))
    line = timing.game_timing(session, GID)["line"]
    assert line == {"first_seen": T0, "last_changed": T1}


# --- quarterbacks ----------------------------------------------------------------------------------------------------


def test_unchanged_quarterback_does_not_move_last_changed(session):
    ingest(session, T0, game_row())
    ingest(session, T1, game_row())
    qb = timing.game_timing(session, GID)["home_qb"]
    assert qb == {"first_seen": T0, "last_changed": T0}


def test_changed_quarterback_moves_last_changed_and_never_first_seen(session):
    ingest(session, T0, game_row())
    ingest(session, T1, game_row(home_qb_name="BUF QB2"))
    t = timing.game_timing(session, GID)
    assert t["home_qb"] == {"first_seen": T0, "last_changed": T1}
    assert t["away_qb"] == {"first_seen": T0, "last_changed": T0}  # the other club did not change


def test_blank_quarterback_stays_blank_and_is_not_first_seen(session):
    ingest(session, T0, game_row(home_qb_name=""))
    assert timing.game_timing(session, GID)["home_qb"] == {"first_seen": None, "last_changed": T0}
    ingest(session, T1, game_row(home_qb_name="BUF QB1"))
    ingest(session, T2, game_row(home_qb_name=""))  # the feed drops the name again: missing stays missing
    assert timing.game_timing(session, GID)["home_qb"] == {"first_seen": T1, "last_changed": T2}


# --- injuries --------------------------------------------------------------------------------------------------------


def test_injury_rows_keep_first_seen_and_move_last_changed_only_on_a_change(session):
    key = ("BUF", "00-1")
    service.ingest_injuries(session, 2026, [injury_row()], now=T0)
    service.ingest_injuries(session, 2026, [injury_row()], now=T1)  # unchanged
    ingest(session, T0, game_row())
    inj = timing.game_timing(session, GID)["injuries"]
    assert inj[key] == {"first_seen": T0, "last_changed": T0}
    service.ingest_injuries(session, 2026, [injury_row(status="Out")], now=T2)
    inj = timing.game_timing(session, GID)["injuries"]
    assert inj[key] == {"first_seen": T0, "last_changed": T2}


# --- the report: no hindsight ----------------------------------------------------------------------------------------


def report_game(session, game_id=GID):
    return next(g for g in timing.week_report(session, 2026, 6)["games"] if g["game_id"] == game_id)


def test_line_age_is_kickoff_minus_the_last_pregame_snapshot(session):
    ingest(session, T0, game_row())
    ingest(session, T2, game_row(spread_line="2.5"))
    assert report_game(session)["line_age_hours"] == 30.0


def test_a_line_first_seen_after_kickoff_is_not_a_pregame_line(session):
    ingest(session, AFTER, game_row())
    assert report_game(session)["line_age_hours"] is None


def test_a_line_change_after_kickoff_does_not_shorten_the_pregame_age(session):
    ingest(session, T0, game_row())
    ingest(session, AFTER, game_row(spread_line="9"))
    assert report_game(session)["line_age_hours"] == 100.0


def test_a_quarterback_seen_only_after_kickoff_counts_as_blank_pregame(session):
    ingest(session, AFTER, game_row())
    g = report_game(session)
    assert (g["home_qb"], g["away_qb"], g["qb_blank"]) == (None, None, True)


def test_a_quarterback_change_after_kickoff_does_not_replace_the_pregame_one(session):
    ingest(session, T0, game_row())
    ingest(session, AFTER, game_row(home_qb_name="BUF QB9"))
    g = report_game(session)
    assert (g["home_qb"], g["qb_blank"]) == ("BUF QB1", False)


# --- the report: missing stays missing, week summary -----------------------------------------------------------------


NO_LINE = {"home_moneyline": "", "away_moneyline": "", "spread_line": "", "total_line": ""}


def test_median_skips_games_without_a_line_and_is_none_when_all_are_missing(session):
    ingest(session, T0, game_row(), game_row("NE", "KC") | NO_LINE)
    r = timing.week_report(session, 2026, 6)
    assert [g["line_age_hours"] for g in r["games"] if g["game_id"] == "2026_06_NE_KC"] == [None]
    assert r["median_line_age_hours"] == 100.0  # not 50.0: a missing line is not an age of zero
    ingest(session, T0, game_row("LV", "NYJ") | NO_LINE)
    only_missing = timing.week_report(session, 2026, 6)
    assert only_missing["games_with_line"] == 1
    session_empty = timing.week_report(session, 2026, 7)
    assert session_empty["games"] == [] and session_empty["median_line_age_hours"] is None


def test_week_report_counts_blank_quarterbacks_and_the_median(session):
    ingest(
        session,
        T0,
        game_row(),  # line age 100, both quarterbacks
        game_row("NE", "KC", home_qb_name=""),  # one blank
        game_row("LV", "NYJ", home_qb_name="", away_qb_name=""),  # both blank
    )
    ingest(session, T2, game_row("LV", "NYJ", home_qb_name="", away_qb_name="", spread_line="7"))  # line age 30
    r = timing.week_report(session, 2026, 6)
    assert r["median_line_age_hours"] == 100.0  # ages 100, 100, 30
    assert r["blank_qb_games"] == 2
    assert r["blank_qb_slots"] == 3
    assert r["games_with_line"] == 3
