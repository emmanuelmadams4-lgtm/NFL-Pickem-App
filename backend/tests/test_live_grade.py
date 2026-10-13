"""Step 15f (server side): grade the in-game win probabilities of finished games. Clauses G1-G12 are in
docs/gauntlet/logs/step-15f.md. All series here are made up; hand counts are worked in the log."""

import math
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nflpi.analytics import live_grade as lg
from nflpi.analytics.metrics import EPS
from nflpi.api.main import app
from nflpi.models import Game, LiveState, MarketQuote, ModelVersion, Prediction, UserPick
from tests.test_live import seed_game

KICKOFF = datetime(2026, 10, 4, 17, 0, tzinfo=UTC)


def at(minute: float) -> datetime:
    return KICKOFF + timedelta(minutes=minute)


def finished(session, key="A", home_score=27, away_score=20, week=5, status="final", home="LA", away="BUF"):
    return seed_game(
        session, away, home, KICKOFF, game_id=f"2026_{week:02d}_{key}", week=week, status=status,
        home_score=home_score, away_score=away_score,
    )  # fmt: skip


def espn(session, g, rows):
    """rows: (minute, state, home_wp); the last one is normally the 'post' row."""
    for minute, state, wp in rows:
        session.add(
            LiveState(game_id=g.game_id, espn_event_id="401", fetched_at=at(minute), state=state, home_wp=wp,
                      period=5 if minute >= 70 else 2)
        )  # fmt: skip
    session.commit()


def kalshi(session, g, rows, kind="live", source="kalshi"):
    for minute, prob in rows:
        session.add(MarketQuote(game_id=g.game_id, source=source, kind=kind, home_prob=prob, fetched_at=at(minute)))
    session.commit()


def predict(session, g, prob, minute=-60.0, kind="live"):
    mv = session.scalar(select(ModelVersion)) or ModelVersion(
        name="t", kind="t", params={}, trained_through_season=2025, is_active=True
    )
    session.add(mv)
    session.flush()
    session.add(
        Prediction(game_id=g.game_id, model_version_id=mv.id, created_at=at(minute), kind=kind, home_win_prob=prob,
                   pick=g.home_team if prob >= 0.5 else g.away_team, features={}, factors=[], uncertainty="low",
                   inputs_hash=f"h{minute}{prob}")
    )  # fmt: skip
    session.commit()


GAME_A = [(0, "in", 0.6), (20, "in", 0.8), (40, "in", None), (50, "in", 0.9), (60, "post", 0.9)]


def game_a(session):
    """Hand game A (home wins): window 60 min; ESPN .6/.8/gap/.9; Kalshi carries in .5 then .9/.95; model .7."""
    g = finished(session, "A")
    espn(session, g, GAME_A)
    kalshi(session, g, [(-5, 0.5), (30, 0.9), (45, 0.95)])
    predict(session, g, 0.7)
    return g


def game_b(session):
    """Hand game B (away wins): window 30 min; ESPN .5/.3/.1; Kalshi only two quotes; model .55."""
    g = finished(session, "B", home_score=17, away_score=24, home="DAL", away="TB")
    espn(session, g, [(0, "in", 0.5), (10, "in", 0.3), (20, "in", 0.1), (30, "post", 0.1)])
    kalshi(session, g, [(5, 0.4), (15, 0.2)])
    predict(session, g, 0.55)
    return g


def by_id(session):
    return {x.game_id: x for x in lg.grade_season(session, 2026)}


def nll(p):
    return -math.log(p)


# ---------------------------------------------------------------------------------------------- G1 weighting


def test_g1_points_are_weighted_by_the_time_each_one_held_not_one_vote_each(session):
    game_a(session)
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.status == "scored" and e.points == 3
    assert e.brier == pytest.approx(4.1 / 50)  # 20 min .6, 20 min .8, 10 min .9; not the per-point 0.07
    assert e.log_loss == pytest.approx((20 * nll(0.6) + 20 * nll(0.8) + 10 * nll(0.9)) / 50)
    assert e.coverage == pytest.approx(50 / 60)


def test_g1_held_segments_are_clipped_to_the_window_and_carry_in_the_last_earlier_point():
    pts = [lg.Point(at(-5), 0.5), lg.Point(at(30), 0.9), lg.Point(at(70), 0.1)]
    assert lg.held_segments(pts, at(0), at(60)) == [(0.5, 1800.0), (0.9, 1800.0)]


# ---------------------------------------------------------------------------------------------- G2 window


def test_g2_a_game_whose_last_row_is_still_in_play_is_in_progress_and_never_scored(session):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (20, "in", 0.8)])
    predict(session, g, 0.7)
    x = by_id(session)["2026_05_A"]
    assert x.status == "in_progress" and x.forecasters == {} and x.window_seconds is None


def test_g2_a_game_that_ends_on_a_lost_row_is_incomplete_and_never_scored(session):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (30, "lost", 0.6)])
    x = by_id(session)["2026_05_A"]
    assert x.status == "incomplete" and x.forecasters == {} and x.window_seconds is None
    assert lg.summarise([x]).games_graded == 0


def test_g2_the_window_ends_at_the_first_post_row_and_later_rows_are_ignored(session):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (30, "in", 0.7), (40, "post", 0.7), (50, "lost", 0.7)])
    kalshi(session, g, [(0, 0.5), (20, 0.6), (35, 0.7), (45, 0.99)])  # 0.99 is after the end: settled price
    x = by_id(session)["2026_05_A"]
    assert x.status == "graded" and x.window_seconds == 2400.0
    assert x.forecasters["kalshi_live"].coverage == 1.0
    assert x.forecasters["kalshi_live"].brier == pytest.approx((20 * 0.25 + 15 * 0.16 + 5 * 0.09) / 40)


# ---------------------------------------------------------------------------------------------- G3 pregame


def test_g3_pregame_is_the_last_prediction_before_kickoff_held_flat(session):
    game_a(session)
    p = by_id(session)["2026_05_A"].forecasters["pregame_model"]
    assert p.status == "scored" and p.brier == pytest.approx(0.09) and p.log_loss == pytest.approx(nll(0.7))
    assert p.coverage == 1.0


def test_g3_a_later_or_earlier_prediction_picks_the_last_one_before_kickoff(session):
    g = game_a(session)
    predict(session, g, 0.2, minute=-120)  # earlier: ignored
    predict(session, g, 0.99, minute=10)  # during the game: ignored
    assert by_id(session)["2026_05_A"].forecasters["pregame_model"].brier == pytest.approx(0.09)


def test_g3_a_backfill_made_after_the_game_is_used_only_when_no_real_snapshot_exists_and_is_labelled(session):
    g = finished(session, "A")
    espn(session, g, GAME_A)
    predict(session, g, 0.8, minute=5000, kind="backfill")
    p = by_id(session)["2026_05_A"].forecasters["pregame_model"]
    assert p.brier == pytest.approx(0.04) and p.kind == "backfill"


def test_g3_a_real_snapshot_before_kickoff_beats_a_later_backfill_and_is_labelled_live(session):
    g = game_a(session)  # real snapshot .7 an hour before kickoff
    predict(session, g, 0.8, minute=5000, kind="backfill")
    p = by_id(session)["2026_05_A"].forecasters["pregame_model"]
    assert p.brier == pytest.approx(0.09) and p.kind == "live"
    assert by_id(session)["2026_05_A"].forecasters["espn_live"].kind is None


def test_g3_no_prediction_is_not_enough_data_not_a_score(session):
    g = finished(session, "A")
    espn(session, g, GAME_A)
    p = by_id(session)["2026_05_A"].forecasters["pregame_model"]
    assert (p.status, p.brier, p.log_loss, p.points) == ("not_enough_data", None, None, 0)


# ---------------------------------------------------------------------------------------------- G4 missing


def test_g4_missing_numbers_are_never_filled_the_gap_gets_no_weight(session):
    game_a(session)
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.coverage < 1.0  # the 10 minute gap is not covered
    assert e.brier != pytest.approx((20 * 0.16 + 30 * 0.04) / 50)  # .8 was not stretched over the gap


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 1.2, -0.1])
def test_g4_a_stored_number_outside_0_to_1_or_not_finite_is_missing_never_clamped(session, bad):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (20, "in", bad), (30, "in", 0.8), (40, "in", 0.7), (60, "post", 0.7)])
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.points == 3 and e.coverage == pytest.approx(50 / 60)  # the bad row's 10 minutes get no weight
    assert e.brier == pytest.approx((20 * 0.16 + 10 * 0.04 + 20 * 0.09) / 50)


def test_g4_only_in_play_rows_are_points_a_lost_row_mid_game_ends_the_hold_without_adding_one(session):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (20, "lost", 0.99), (30, "in", 0.7), (45, "in", 0.8), (60, "post", 0.8)])
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.points == 3 and e.coverage == pytest.approx(50 / 60)
    assert e.brier == pytest.approx((20 * 0.16 + 15 * 0.09 + 15 * 0.04) / 50)


def test_g4_a_null_kalshi_row_ends_the_hold_and_only_live_kalshi_quotes_count(session):
    g = finished(session, "A")
    espn(session, g, GAME_A)
    kalshi(session, g, [(0, 0.6), (15, None), (30, 0.7), (40, 0.8)])
    kalshi(session, g, [(0, 0.01)], kind="pregame")
    kalshi(session, g, [(0, 0.01)], source="oddsapi")
    k = by_id(session)["2026_05_A"].forecasters["kalshi_live"]
    assert k.points == 3 and k.coverage == pytest.approx(45 / 60)  # .6 15 min, .7 10 min, .8 20 min
    assert k.brier == pytest.approx((15 * 0.16 + 10 * 0.09 + 20 * 0.04) / 45)


# ---------------------------------------------------------------------------------------------- G5 enough data


def test_g5_a_forecaster_with_too_few_points_is_not_enough_data_with_no_numbers(session):
    game_b(session)
    k = by_id(session)["2026_05_B"].forecasters["kalshi_live"]
    assert (k.status, k.brier, k.log_loss, k.points) == ("not_enough_data", None, None, 2)


def test_g5_a_forecaster_covering_under_half_the_window_is_not_enough_data(session):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (10, "in", 0.7), (15, "in", 0.8), (20, "in", None), (60, "post", None)])
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.points == 3 and e.coverage == pytest.approx(20 / 60) and e.status == "not_enough_data"


# ---------------------------------------------------------------------------------------------- G6-G8 game kinds


def test_g6_a_tie_is_not_graded_and_not_counted(session):
    g = finished(session, "A", home_score=24, away_score=24)
    espn(session, g, GAME_A)
    x = by_id(session)["2026_05_A"]
    assert x.status == "tie" and x.forecasters == {}
    assert lg.summarise([x]).games_graded == 0


def test_g7_a_final_game_with_no_in_play_row_is_no_live_data(session):
    finished(session, "A")
    g = finished(session, "B", home="DAL", away="TB")
    espn(session, g, [(0, "pre", None)])
    got = by_id(session)
    assert got["2026_05_B"].status == "no_live_data" and got["2026_05_B"].forecasters == {}
    assert "2026_05_A" not in got  # no live row and nothing to say: not listed at all


def test_g8_overtime_rows_are_ordinary_points_and_the_window_runs_to_the_last_row(session):
    g = finished(session, "A")
    espn(session, g, [(0, "in", 0.6), (60, "in", 0.5), (70, "in", 0.9), (80, "post", 0.9)])  # minute >= 70 is period 5
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.points == 3 and e.coverage == 1.0
    assert e.brier == pytest.approx((60 * 0.16 + 10 * 0.25 + 10 * 0.01) / 80)


# ---------------------------------------------------------------------------------------------- G9 clamp


def test_g9_log_loss_is_clamped_at_the_metrics_epsilon_but_brier_is_not(session):
    g = finished(session, "A")
    espn(
        session, g, [(0, "in", 0.0), (10, "in", 0.0), (20, "in", 0.0), (30, "post", 0.0)]
    )  # certain the home team loses; it won
    e = by_id(session)["2026_05_A"].forecasters["espn_live"]
    assert e.points == 3
    assert e.log_loss == pytest.approx(-math.log(EPS)) and math.isfinite(e.log_loss)
    assert e.brier == pytest.approx(1.0)


# ---------------------------------------------------------------------------------------------- G10 in progress


def test_g10_a_game_not_final_in_games_is_never_graded_even_with_a_post_row(session):
    g = finished(session, "A", status="scheduled", home_score=None, away_score=None)
    espn(session, g, GAME_A)
    x = by_id(session)["2026_05_A"]
    assert x.status == "in_progress" and x.forecasters == {}
    assert lg.summarise([x]).games_graded == 0


def test_g10_a_scheduled_game_with_no_live_row_is_left_out(session):
    finished(session, "A", status="scheduled", home_score=None, away_score=None)
    assert lg.grade_season(session, 2026) == []


# ---------------------------------------------------------------------------------------------- G11 aggregates


def test_g11_averages_are_equal_weight_per_game_and_skip_games_that_were_not_scored(session):
    game_a(session)
    game_b(session)
    s = lg.summarise(lg.grade_season(session, 2026))
    assert s.games_graded == 2
    assert s.forecasters["espn_live"].games == 2
    assert s.forecasters["espn_live"].brier == pytest.approx((0.082 + 0.35 / 3) / 2)
    assert s.forecasters["pregame_model"].brier == pytest.approx((0.09 + 0.3025) / 2)
    assert s.forecasters["kalshi_live"].games == 1  # game B was not enough data
    assert s.forecasters["kalshi_live"].brier == pytest.approx(7.6875 / 60)
    assert s.forecasters["kalshi_live"].log_loss == pytest.approx((30 * nll(0.5) + 15 * nll(0.9) + 15 * nll(0.95)) / 60)


def test_g11_a_forecaster_never_scored_has_null_averages():
    s = lg.summarise([])
    assert s.games_graded == 0
    assert all(f.games == 0 and f.brier is None and f.log_loss is None for f in s.forecasters.values())
    assert list(s.forecasters) == ["pregame_model", "espn_live", "kalshi_live"]


# ---------------------------------------------------------------------------------------------- G12 route

URL = "/api/live/grades"
GAME_FIELDS = {"game_id", "week", "home_team", "away_team", "home_score", "away_score", "status", "window_seconds",
               "forecasters"}  # fmt: skip
FORECAST_FIELDS = {"name", "status", "points", "coverage", "brier", "log_loss", "kind"}
SUMMARY_FIELDS = {"games_graded", "forecasters"}
SUMMARY_FORECAST_FIELDS = {"name", "games", "brier", "log_loss"}


def test_g12_the_route_needs_the_token(session):
    bare = TestClient(app)
    assert bare.get(URL, params={"season": 2026, "week": 5}).status_code == 401
    wrong = {"Authorization": "Bearer wrong"}
    assert bare.get(URL, params={"season": 2026, "week": 5}, headers=wrong).status_code == 401


def test_g12_the_reply_shape_is_frozen(client, session):
    game_a(session)
    game_b(session)
    r = client.get(URL, params={"season": 2026, "week": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data) == {"season", "week", "games", "week_summary", "season_summary"}
    assert (data["season"], data["week"]) == (2026, 5)
    assert [x["game_id"] for x in data["games"]] == ["2026_05_A", "2026_05_B"]
    a = data["games"][0]
    assert set(a) == GAME_FIELDS and a["status"] == "graded" and a["window_seconds"] == 3600
    assert [f["name"] for f in a["forecasters"]] == ["pregame_model", "espn_live", "kalshi_live"]
    assert all(set(f) == FORECAST_FIELDS for f in a["forecasters"])
    assert a["forecasters"][1]["brier"] == pytest.approx(0.082)
    for key in ("week_summary", "season_summary"):
        assert set(data[key]) == SUMMARY_FIELDS
        assert all(set(f) == SUMMARY_FORECAST_FIELDS for f in data[key]["forecasters"])
    assert data["week_summary"]["games_graded"] == 2


def test_g12_week_summary_is_that_week_and_season_summary_is_every_week(client, session):
    game_a(session)
    g = finished(session, "C", week=6, home="DAL", away="TB")
    espn(session, g, [(0, "in", 0.9), (30, "post", 0.9)])
    data = client.get(URL, params={"season": 2026, "week": 6}).json()
    assert [x["game_id"] for x in data["games"]] == ["2026_06_C"]
    assert data["week_summary"]["games_graded"] == 1 and data["season_summary"]["games_graded"] == 2


def test_g12_a_game_with_no_graded_state_has_empty_forecasters_in_the_reply(client, session):
    g = finished(session, "A", home_score=24, away_score=24)
    espn(session, g, GAME_A)
    a = client.get(URL, params={"season": 2026, "week": 5}).json()["games"][0]
    assert a["status"] == "tie" and a["forecasters"] == [] and a["window_seconds"] is None


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"season": 2026},
        {"week": 5},
        {"season": "abc", "week": 5},
        {"season": 1999, "week": 5},
        {"season": 2101, "week": 5},
        {"season": 2026, "week": 0},
        {"season": 2026, "week": 23},
        {"season": "20 26", "week": 5},
        {"season": "2026.5", "week": 5},
        {"season": "٢٠٢٦", "week": 5},
        {"season": "9" * 400, "week": 5},
        {"season": 2026, "week": "<script>x</script>"},
    ],
)
def test_g12_bad_query_values_are_422_with_a_fixed_message_and_nothing_echoed(client, params):
    r = client.get(URL, params=params)
    assert r.status_code == 422
    assert r.json() == {"detail": "season must be a year 2000 to 2100 and week a number 1 to 22"}
    message = r.json()["detail"]
    for value in params.values():
        assert str(value) in message or str(value) not in r.text


def test_g12_the_route_only_reads_and_never_touches_picks_or_predictions(client, session):
    game_a(session)
    session.add(UserPick(game_id="2026_05_A", picked_team="BUF"))
    session.commit()

    def counts():
        tables = (Game, LiveState, MarketQuote, Prediction, UserPick)
        return [session.scalar(select(func.count()).select_from(t)) for t in tables]

    before = counts()
    assert client.get(URL, params={"season": 2026, "week": 5}).status_code == 200
    session.expire_all()
    assert counts() == before
    assert session.get(UserPick, "2026_05_A").picked_team == "BUF"
    assert set(app.openapi()["paths"][URL]) == {"get"}
    for verb in ("post", "put", "patch", "delete"):
        assert getattr(client, verb)(URL, params={"season": 2026, "week": 5}).status_code == 405


def test_g12_work_is_bounded_by_the_season_the_query_count_does_not_grow_with_games(client, session):
    from sqlalchemy import event

    from nflpi.db import get_engine

    def run(n):
        for i in range(n):
            g = finished(session, f"X{i}{n}", home="DAL", away="TB")
            espn(session, g, GAME_A)
        seen = []
        eng = get_engine()
        listener = lambda *a: seen.append(1)  # noqa: E731
        event.listen(eng, "before_cursor_execute", listener)
        try:
            assert client.get(URL, params={"season": 2026, "week": 5}).status_code == 200
        finally:
            event.remove(eng, "before_cursor_execute", listener)
        return len(seen)

    few = run(2)
    many = run(8)
    assert many == few
