"""Step 19a: a fresh pregame line in the predictions before kickoff. Clauses F1-F8 (pure) and D1-D4 (database) in
docs/gauntlet/logs/step-19a.md section 2. The F tests need no database."""

import math
from datetime import UTC, datetime, timedelta

import pytest

NOW = datetime(2026, 10, 18, 15, 30, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)


def _fl():
    from nflpi.predictions import fresh_line  # imported per test so collection works while 19a is red

    return fresh_line


def nfl(prob=0.60, minutes_ago=600):
    return _fl().Line(prob, "nflverse", NOW - timedelta(minutes=minutes_ago))


def q(prob, minutes_ago=5, source="kalshi"):
    return _fl().Quote(source, prob, NOW - timedelta(minutes=minutes_ago))


def choose(quotes, nflverse=None, previous=None, now=NOW, kickoff=KICKOFF):
    return _fl().choose_line(nflverse if nflverse is not None else nfl(), quotes, previous, now=now, kickoff=kickoff)


# --- F1-F5 choose_line ------------------------------------------------------------------------------

def test_f1_a_fresh_pregame_quote_newer_than_nflverse_is_used_with_its_source_and_time():
    line, reason = choose([q(0.64)])
    assert (line.prob, line.source, line.seen_at, reason) == (0.64, "kalshi", NOW - timedelta(minutes=5), None)


@pytest.mark.parametrize("quote", [
    "after_kickoff", "too_old", "from_the_future", "not_a_probability", "nan", "older_than_nflverse"])
def test_f2_unusable_quotes_leave_the_nflverse_line(quote):
    fl = _fl()
    quotes = {
        "after_kickoff": [q(0.64)], "too_old": [q(0.64, minutes_ago=31)], "from_the_future": [q(0.64, minutes_ago=-1)],
        "not_a_probability": [q(1.0)], "nan": [q(math.nan)], "older_than_nflverse": [q(0.64, minutes_ago=20)],
    }[quote]
    kickoff = NOW - timedelta(minutes=1) if quote == "after_kickoff" else KICKOFF
    base = nfl(minutes_ago=10) if quote == "older_than_nflverse" else nfl()
    line, _ = choose(quotes, nflverse=base, kickoff=kickoff)
    assert line == base and fl.FRESH_MAX_AGE == timedelta(minutes=30)


def test_f3_a_quote_far_from_the_nflverse_line_is_refused_as_a_likely_wrong_side():
    line, reason = choose([q(0.40)])  # 0.20 away from nflverse 0.60
    assert line == nfl() and reason == "sanity"
    line, reason = choose([q(0.4005)])  # just inside the gap
    assert line.source == "kalshi" and reason is None
    no_line = _fl().Line(None, "nflverse", None)
    line, reason = choose([q(0.30)], nflverse=no_line)  # nothing to compare against: the quote is the only line
    assert line.prob == 0.30 and reason is None
    assert _fl().SANITY_GAP == 0.20


def test_f4_a_move_under_one_point_keeps_the_previous_line_exactly():
    fl = _fl()
    previous = fl.Line(0.6400, "kalshi", NOW - timedelta(minutes=12))
    line, _ = choose([q(0.6450)], previous=previous)
    assert line == previous  # same prob, source and time: no new prediction row
    line, _ = choose([q(0.6500)], previous=previous)
    assert line.prob == 0.65 and line.seen_at == NOW - timedelta(minutes=5)
    # back to nflverse within a point of the previous fresh line: keep the previous line too
    line, _ = choose([], nflverse=nfl(prob=0.645), previous=previous)
    assert line == previous
    assert fl.CHURN_GAP == 0.01


def test_f4b_nflverse_moves_alone_behave_as_today():
    previous = nfl(prob=0.600)
    line, _ = choose([], nflverse=nfl(prob=0.605), previous=previous)
    assert line == nfl(prob=0.605)  # the churn rule is only for fresh quotes


def test_f5_the_newest_fresh_quote_wins_across_sources_and_ties_go_by_source_name():
    line, _ = choose([q(0.62, 8, "kalshi"), q(0.63, 3, "oddsapi:bookone")])
    assert line.source == "oddsapi:bookone"
    line, _ = choose([q(0.62, 3, "oddsapi:bookone"), q(0.63, 3, "kalshi")])
    assert line.source == "kalshi"


# --- F6 fair moneylines ------------------------------------------------------------------------------

@pytest.mark.parametrize("p", [0.05, 0.31, 0.5, 0.64, 0.97])
def test_f6_fair_moneylines_carry_the_quote_probability_unchanged(p):
    from nflpi.predictions.market import novig_home_prob

    home_ml, away_ml = _fl().fair_moneylines(p)
    assert novig_home_prob(home_ml, away_ml) == pytest.approx(p, abs=1e-9)


# --- F7 confidence-points rank ----------------------------------------------------------------------

def test_f7_rank_change_follows_the_confidence_pool_order():
    rank_changed = _fl().rank_changed
    old = {"g1": 0.80, "g2": 0.30, "g3": 0.60}  # confidence 0.80, 0.70, 0.60
    assert rank_changed(old, old | {"g3": 0.62}, "g3") is False
    assert rank_changed(old, old | {"g3": 0.75}, "g3") is True  # passes g2
    assert rank_changed(old, old | {"g3": 0.30}, "g3") is False  # pick flips, confidence 0.70 ties g2: g2 < g3 by id
    assert rank_changed({"g1": 0.7, "g2": 0.7}, {"g1": 0.7, "g2": 0.7}, "g2") is False


# --- F8 refresh targets -----------------------------------------------------------------------------

def test_f8_the_wait_lands_one_minute_after_the_next_kickoff_target():
    until = _fl().until_next_target
    assert until([NOW + timedelta(minutes=100)], NOW) == timedelta(minutes=11)  # -90 target in 10 min
    assert until([NOW + timedelta(minutes=25)], NOW) == timedelta(minutes=6)  # -20 target in 5 min
    assert until([NOW + timedelta(minutes=10)], NOW) is None  # both targets passed
    assert until([NOW + timedelta(minutes=100), NOW + timedelta(minutes=24)], NOW) == timedelta(minutes=5)
    assert until([], NOW) is None


# --- D1-D4 with the database (run in PR CI; the Mac test database is off) ---------------------------

def _setup_quote(loaded, minutes_before_kickoff=60, shift=0.05, kind="pregame", age=5):
    from sqlalchemy import select

    from nflpi.models import Game, MarketQuote, MarketSnapshot
    from tests.conftest import CURRENT

    game = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    snap = loaded.scalars(select(MarketSnapshot).where(MarketSnapshot.game_id == game.game_id)
                          .order_by(MarketSnapshot.id.desc())).first()
    now = game.kickoff_utc - timedelta(minutes=minutes_before_kickoff)
    snap.observed_at = now - timedelta(hours=10)
    prob = min(0.98, max(0.02, snap.home_prob_novig + shift))
    loaded.add(MarketQuote(game_id=game.game_id, source="kalshi", kind=kind, home_prob=prob, away_prob=1 - prob,
                           fetched_at=now - timedelta(minutes=age)))
    loaded.commit()
    return game, snap, prob, now


def _newest(loaded, game_id):
    from sqlalchemy import select

    from nflpi.models import Prediction

    newest = select(Prediction).where(Prediction.game_id == game_id).order_by(Prediction.id.desc())
    return loaded.scalars(newest).first()


def test_d1_a_fresh_quote_reaches_the_prediction_and_is_labelled(loaded):
    from nflpi.predictions import engine

    game, _, prob, now = _setup_quote(loaded)
    engine.refresh_predictions(loaded, now=now, game_ids=[game.game_id])
    row = _newest(loaded, game.game_id)
    assert row.market_home_prob == pytest.approx(prob, abs=1e-4)
    assert row.features["market_source"] == "kalshi"
    assert row.features["market_seen_at"] == (now - timedelta(minutes=5)).isoformat()


@pytest.mark.parametrize("case", ["live", "stale", "far"])
def test_d2_live_stale_or_far_off_quotes_leave_the_prediction_on_nflverse(loaded, case):
    from nflpi.predictions import engine

    kw = {"live": {"kind": "live"}, "stale": {"age": 45}, "far": {"shift": 0.30}}[case]
    game, snap, _, now = _setup_quote(loaded, **kw)
    engine.refresh_predictions(loaded, now=now, game_ids=[game.game_id])
    row = _newest(loaded, game.game_id)
    assert "market_source" not in row.features
    assert row.market_home_prob == pytest.approx(snap.home_prob_novig, abs=1e-4)


def test_d3_a_line_only_change_alerts_only_on_a_flip_or_a_points_rank_change(loaded, monkeypatch):
    from nflpi.config import get_settings
    from nflpi.predictions import engine, fresh_line

    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.0)  # any move would alert today
    game, _, _, now = _setup_quote(loaded, shift=0.02)  # same pick, same points rank
    assert engine.refresh_predictions(loaded, now=now, game_ids=[game.game_id]) == []
    first = _newest(loaded, game.game_id)
    assert first.features["market_source"] == "kalshi"
    again = engine.refresh_predictions(loaded, now=now + timedelta(minutes=1), game_ids=[game.game_id])
    assert again == [] and _newest(loaded, game.game_id).id == first.id  # same quote: no new row
    monkeypatch.setattr(fresh_line, "rank_changed", lambda old, new, game_id: True)
    _, _, _, later = _setup_quote(loaded, shift=0.04)
    events = engine.refresh_predictions(loaded, now=later, game_ids=[game.game_id])
    assert [e.game_id for e in events] == [game.game_id]  # a points-rank change is alerted


def test_d3b_a_line_that_flips_the_pick_is_alerted(loaded, monkeypatch):
    from sqlalchemy import select

    from nflpi.config import get_settings
    from nflpi.models import Game, MarketQuote, MarketSnapshot
    from nflpi.predictions import engine
    from tests.conftest import CURRENT

    monkeypatch.setattr(get_settings(), "alert_move_threshold", 0.99)  # only a flip can alert
    games = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).all()
    game = min(games, key=lambda g: abs(_newest(loaded, g.game_id).home_win_prob - 0.5))  # the closest call
    last = _newest(loaded, game.game_id)
    snap = loaded.scalars(select(MarketSnapshot).where(MarketSnapshot.game_id == game.game_id)
                          .order_by(MarketSnapshot.id.desc())).first()
    now = game.kickoff_utc - timedelta(minutes=30)
    snap.observed_at = now - timedelta(hours=10)
    side = -1 if last.home_win_prob >= 0.5 else 1
    prob = snap.home_prob_novig + side * 0.19  # inside the sanity gap, toward the other team
    loaded.add(MarketQuote(game_id=game.game_id, source="kalshi", kind="pregame", home_prob=prob,
                           away_prob=1 - prob, fetched_at=now - timedelta(minutes=2)))
    loaded.commit()
    events = engine.refresh_predictions(loaded, now=now, game_ids=[game.game_id])
    assert _newest(loaded, game.game_id).pick != last.pick  # precondition: the line flipped the pick
    assert [e.game_id for e in events] == [game.game_id]


def test_d4_next_interval_lands_just_after_the_kickoff_targets(session):
    from nflpi import jobs
    from nflpi.models import Game

    session.add(Game(game_id="2026_07_MIA_BUF", season=2026, week=7, game_type="REG", weekday="Sunday",
                     kickoff_utc=NOW + timedelta(minutes=100), away_team="MIA", home_team="BUF",
                     status="scheduled", source="test"))
    session.commit()
    assert jobs.next_interval(session, NOW) == timedelta(minutes=11)
    assert jobs.next_interval(session, NOW + timedelta(minutes=12)) == timedelta(minutes=20)
    assert jobs.next_interval(session, NOW + timedelta(minutes=75)) == timedelta(minutes=6)
