"""HAG-82 carried LOWs. Clauses L-* in docs/gauntlet/logs/step-lows.md section 2.

Pure tests first, database tests last (PR CI)."""

import ast
import json
import logging
import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

NOW = datetime(2026, 10, 18, 15, 30, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)


# --- simulator (18m) ---------------------------------------------------------------------------------

def _keys():
    from nflpi.sim import keys

    return keys


def _nan_ratio():
    keys = _keys()
    ratio = np.ones(keys.KEY_MAX + 1)
    ratio[:20] = np.nan  # every common margin: the tilt can never converge
    return tuple(ratio)


def test_l_n1_unweighted_draws_are_never_labelled_key_weighted():
    from nflpi.sim.game import simulate_game
    from tests.test_sim import A, B, make_params

    res = simulate_game(A, B, 2000, params=make_params(key_ratio=_nan_ratio(), key_alpha=1.0), seed=2,
                        distribution="key_weighted")
    assert res.distribution == "paired_residual"


def test_l_n1b_key_weight_says_whether_it_weighted():
    keys = _keys()
    rng = np.random.default_rng(4)
    a, b = rng.poisson(26, 5000), rng.poisson(17, 5000)
    ratio = np.ones(keys.KEY_MAX + 1)
    ratio[3] = 3.0
    *_, weighted = keys.key_weight(a, b, np.random.default_rng(1), tuple(ratio), 1.0)
    assert weighted is True
    wa, wb, weighted = keys.key_weight(a, b, np.random.default_rng(1), _nan_ratio(), 1.0)
    assert weighted is False
    np.testing.assert_array_equal(wa, a)
    np.testing.assert_array_equal(wb, b)


def test_l_n2_non_convergence_warns_once_per_process_then_quietly(caplog):
    keys = _keys()
    keys._warned = False  # the once-per-process flag (spec L-N2)
    rng = np.random.default_rng(4)
    a, b = rng.poisson(26, 3000), rng.poisson(17, 3000)
    with caplog.at_level(logging.DEBUG, logger="nflpi.sim.keys"):
        for _ in range(3):
            keys.key_weight(a, b, np.random.default_rng(1), _nan_ratio(), 1.0)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1


def test_l_ess_too_few_effective_draws_leave_the_draws_unweighted():
    keys = _keys()
    rng = np.random.default_rng(4)
    a, b = rng.poisson(26, 5000), rng.poisson(17, 5000)
    ratio = np.full(keys.KEY_MAX + 1, 1e-6)
    ratio[9] = 1.0  # nearly all weight on one rare margin: effective draws far below 10% of n
    wa, wb, weighted = keys.key_weight(a, b, np.random.default_rng(1), tuple(ratio), 1.0)
    assert weighted is False
    np.testing.assert_array_equal(wa, a)
    np.testing.assert_array_equal(wb, b)


def test_l_r1_non_whole_final_scores_are_refused():
    from tests.test_sim import _lumpy_training, make_params

    keys = _keys()
    mu_a, mu_b, sa, sb, *_ = _lumpy_training(n=600)
    sa = sa.astype(float)
    sa[0] += 0.5
    with pytest.raises(ValueError, match="whole"):
        keys.learn_key_ratio(mu_a, mu_b, sa, sb, make_params(), 2009)


def test_l_pools_float_scores_still_give_integer_residual_pools():
    from nflpi.sim.params import learn_params
    from tests.test_sim import _lumpy_training

    cols = list(_lumpy_training(n=3000))
    cols[2], cols[3] = cols[2].astype(float), cols[3].astype(float)
    params = learn_params(*cols, target_season=2009)
    assert params.residual_a.dtype == np.int64 and params.residual_b.dtype == np.int64


def test_l_l3_keys_tune_never_overwrites_its_record(tmp_path):
    from nflpi.analytics import sim_backtest

    path = tmp_path / "keys-tune.json"
    sim_backtest.write_tune(path, {"a": 1})
    with pytest.raises(FileExistsError):
        sim_backtest.write_tune(path, {"a": 2})
    assert json.loads(path.read_text()) == {"a": 1}


# --- value ratings (18l) -----------------------------------------------------------------------------

def test_l_d1_a_non_finite_expected_value_fails_the_schema():
    from pydantic import ValidationError

    from nflpi.api.schemas import ValueRatingOut

    base = {"market_type": "moneyline", "selection": "home", "sportsbook": "b", "line": None, "price": 120,
            "observed_at": NOW, "status": "UNRATED", "stars": None, "reasons": [], "note": "n"}
    ValueRatingOut(**base, expected_value=0.1)
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValidationError):
            ValueRatingOut(**base, expected_value=bad)


# --- fresh line (19a) --------------------------------------------------------------------------------

def _fl():
    from nflpi.predictions import fresh_line

    return fresh_line


def test_l_19a_l1_churn_does_not_keep_a_previous_quote_older_than_thirty_minutes():
    fl = _fl()
    old_quote = fl.Line(0.6400, "kalshi", NOW - timedelta(minutes=45))
    nflverse = fl.Line(0.6420, "nflverse", NOW - timedelta(hours=10))
    line, _ = fl.choose_line(nflverse, [], old_quote, now=NOW, kickoff=KICKOFF)
    assert line == nflverse  # the stale quote is not carried forward
    fresh = fl.Line(0.6400, "kalshi", NOW - timedelta(minutes=12))
    line, _ = fl.choose_line(nflverse, [], fresh, now=NOW, kickoff=KICKOFF)
    assert line == fresh  # F4 unchanged for a fresh previous quote


def test_l_19a_l6_a_nan_nflverse_line_counts_as_missing():
    from nflpi.predictions.market import novig_home_prob

    assert novig_home_prob(math.nan, -120) is None
    assert novig_home_prob(-120, math.nan) is None


def test_l_19a_dead_term_the_non_line_alert_branch_reads_as_specified():
    from nflpi.predictions import engine

    src = ast.unparse(ast.parse(open(engine.__file__).read()))
    assert "prev.pick != pick or line_only" not in src


# --- layering gate (13b) -----------------------------------------------------------------------------

def test_l_gate_relative_imports_and_getattr_reaching_a_private_name_are_caught():
    from tests.test_layering import private_reaches

    rel = ("ai", "x")
    assert private_reaches(rel, ast.parse("from ..api import _helper\n"))
    assert private_reaches(rel, ast.parse("from ..predictions.engine import _thing\n"))
    assert private_reaches(rel, ast.parse("from nflpi.predictions import engine\ngetattr(engine, '_x')\n"))
    assert not private_reaches(rel, ast.parse("from . import _own\nfrom ..api import views\n"))


# --- points bench (19b) ------------------------------------------------------------------------------

def test_l_19b_report_is_never_overwritten_and_never_holds_nan(tmp_path):
    from nflpi.analytics import points_bench

    path = tmp_path / "out.json"
    points_bench.write_report(path, {"x": 1.0})
    assert json.loads(path.read_text()) == {"x": 1.0}
    with pytest.raises(FileExistsError):
        points_bench.write_report(path, {"x": 2.0})
    with pytest.raises(ValueError):
        points_bench.write_report(tmp_path / "nan.json", {"x": math.nan})
    assert not (tmp_path / "nan.json").exists()


def test_l_19b_model_summaries_are_guarded_by_d72():
    import pandas as pd

    from nflpi.analytics import points_bench

    frame = pd.DataFrame([{"season": 2025, "week": 1, "game_id": "g", "home_win": 1.0, "p_blend": 0.6,
                           "kickoff_utc": datetime(2026, 10, 15, 17, 0, tzinfo=UTC)}])
    with pytest.raises(Exception, match="D72"):
        points_bench._summary(frame, "p_blend", range(2025, 2026))


# --- database (PR CI; the Mac test database is off) --------------------------------------------------

def test_l_l1_l4_stored_key_ratio_loads_as_a_tuple_and_a_bad_one_is_dropped(session, caplog):
    from nflpi.models import AppSetting
    from nflpi.predictions import engine
    from tests.test_sim import make_params

    good = make_params(key_ratio=tuple([1.0] * 61), key_alpha=1.0)
    engine.save_sim_params(session, 2026, good)
    session.commit()
    loaded = engine.load_sim_params(session, 2026)
    assert isinstance(loaded.key_ratio, tuple) and loaded.key_ratio == good.key_ratio
    row = session.get(AppSetting, "sim_params_2026")
    row.value = {**row.value, "key_ratio": [1.0, -2.0, 3.0]}  # wrong length and a negative entry
    session.commit()
    with caplog.at_level(logging.WARNING):
        bad = engine.load_sim_params(session, 2026)
    assert bad is not None and bad.key_ratio == () and "key_ratio" in caplog.text


def test_l_r2_no_stored_simulator_parameters_is_logged(session, caplog):
    from nflpi.predictions import engine

    with caplog.at_level(logging.WARNING):
        assert engine.load_sim_params(session, 2031) is None
    assert "2031" in caplog.text


def test_l_19a_l4_a_quote_read_error_falls_back_to_the_nflverse_line(loaded, monkeypatch, caplog):
    from nflpi.predictions import engine, fresh_line

    def boom(*_a, **_k):
        raise RuntimeError("quotes table unreadable")

    monkeypatch.setattr(fresh_line, "pregame_quotes", boom)
    with caplog.at_level(logging.WARNING):
        frame = engine.load_frame(loaded, NOW)
    assert len(frame) > 0 and "market_source" not in frame.columns
    assert "quotes" in caplog.text


def test_l_19a_l7_a_bad_stored_seen_at_does_not_break_the_frame(loaded):
    from sqlalchemy import select

    from nflpi.models import Game, Prediction
    from nflpi.predictions import engine
    from tests.conftest import CURRENT

    game = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    newest = loaded.scalars(select(Prediction).where(Prediction.game_id == game.game_id)
                            .order_by(Prediction.id.desc())).first()
    newest.features = {**newest.features, "market_seen_at": "not a time", "market_source": "kalshi",
                       "market_prob": 0.6}
    loaded.commit()
    assert len(engine.load_frame(loaded, game.kickoff_utc - timedelta(hours=1))) > 0


def test_l_dup_read_a_week_summary_reads_predictions_once(loaded):
    from sqlalchemy import event, select

    from nflpi.api import readmodels
    from nflpi.models import Game
    from tests.conftest import CURRENT

    games = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).all()
    before = readmodels.summaries(loaded, games, NOW)
    seen = []

    def count(conn, cursor, statement, *a):
        if "FROM predictions" in statement:
            seen.append(statement)

    engine_ = loaded.get_bind()
    event.listen(engine_, "before_cursor_execute", count)
    try:
        after = readmodels.summaries(loaded, games, NOW)
    finally:
        event.remove(engine_, "before_cursor_execute", count)
    assert len(seen) == 1
    assert [x.model_dump() for x in after] == [x.model_dump() for x in before]


def test_l_l2_load_snapshots_reads_only_the_newest_complete_pair_per_book(session):
    from nflpi import value
    from tests.test_value_api import GAME, seed
    from tests.test_value_api import NOW as VNOW

    seed(session)
    for minutes in (50, 40, 30, 20, 10):  # five complete snapshots over time
        at = VNOW - timedelta(minutes=minutes)
        value.save_prices(session, GAME, "bookone", at, at,
                          [{"market_type": "moneyline", "selection": s, "line": None, "price": p}
                           for s, p in (("home", 100 + minutes), ("away", -140))])
    at = VNOW - timedelta(minutes=5)  # a newer lone side: never paired, so the 10-minute pair still wins
    value.save_prices(session, GAME, "bookone", at, at,
                      [{"market_type": "moneyline", "selection": "home", "line": None, "price": 199}])
    session.commit()
    rows_read = []
    real = session.scalars

    def spy(stmt, *a, **k):
        result = list(real(stmt, *a, **k))
        rows_read.append(len(result))
        return result

    session.scalars = spy
    try:
        got = value.load_snapshots(session, GAME, "moneyline", as_of=VNOW)
    finally:
        session.scalars = real
    assert {(r.selection, r.price) for r in got} == {("home", 110), ("away", -140)}
    assert sum(rows_read) == 2  # the chosen pair only, not all eleven stored rows


def test_l_d2_a_rating_that_cannot_be_computed_warns_once_per_process(session, monkeypatch, caplog):
    from nflpi import value
    from nflpi.api import readmodels
    from tests.test_value_api import GAME, prices, seed
    from tests.test_value_api import NOW as VNOW

    monkeypatch.setattr(readmodels, "now_utc", lambda: VNOW)
    seed(session)
    prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140)])

    def broken(*_a, **_k):
        raise ValueError("bad stored run")

    monkeypatch.setattr(value, "rate_price", broken)
    monkeypatch.setattr(readmodels, "_warned_ratings", set(), raising=False)
    with caplog.at_level(logging.DEBUG, logger="nflpi.api.readmodels"):
        for _ in range(3):
            readmodels.game_detail(session, GAME)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "value rating" in r.getMessage()]
    assert len(warnings) == 2  # once per (game, market, side): home and away, not once per read
