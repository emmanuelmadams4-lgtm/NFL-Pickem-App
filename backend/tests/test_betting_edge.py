"""Step 18b spec: the four edge numbers, expected value and the end-to-end flow (brief sections 8 and 12).

Edge keeps its sign. EV = P(win) x (d - 1) - P(loss); a refunded push adds zero.
"""

import itertools
import random
from datetime import UTC, datetime, timedelta

import pytest

from nflpi.betting.edge import (
    Edge,
    SettlementProbs,
    break_even_probability,
    evaluate,
    expected_value,
    fair_probability_edge,
    point_difference,
    price_edge,
)
from nflpi.betting.odds import BettingError
from nflpi.betting.settle import settle
from nflpi.betting.snapshot import MarketSnapshot

T0 = datetime(2026, 10, 18, 16, 0, tzinfo=UTC)
NOW = T0 + timedelta(minutes=5)
MAX_AGE = timedelta(minutes=30)


def snap(market="moneyline", selection="home", price=-110, line=None, **kw):
    return MarketSnapshot(
        kw.get("game", "g1"), kw.get("book", "bookA"), kw.get("at", T0), market, selection, line, "american", price
    )


# ---- SettlementProbs -----------------------------------------------------------------------


def test_settlement_probs_conditional_win():
    assert SettlementProbs(win=0.45, push=0.10, loss=0.45).conditional_win == pytest.approx(0.5)
    assert SettlementProbs(win=0.3, push=0.0, loss=0.7).conditional_win == pytest.approx(0.3)
    assert SettlementProbs(win=0.6, push=0.2, loss=0.2).conditional_win == pytest.approx(0.75)


def test_settlement_probs_is_immutable():
    p = SettlementProbs(0.5, 0.0, 0.5)
    with pytest.raises(AttributeError):
        p.win = 0.6  # type: ignore[misc]


@pytest.mark.parametrize(
    "win, push, loss",
    [(0.5, 0.0, 0.6), (-0.1, 0.6, 0.5), (0.5, 0.5, 0.5), (1.1, 0.0, -0.1), (float("nan"), 0.5, 0.5), (0.3, 0.3, 0.3)],
)
def test_settlement_probs_must_be_probabilities_summing_to_one(win, push, loss):
    with pytest.raises(BettingError):
        SettlementProbs(win, push, loss)


def test_conditional_win_is_undefined_when_every_outcome_is_a_push():
    with pytest.raises(BettingError):
        _ = SettlementProbs(0.0, 1.0, 0.0).conditional_win


def test_edge_result_is_immutable():
    got = evaluate(snap("moneyline", "home", 150), SettlementProbs(0.5, 0.0, 0.5), now=NOW, max_age=MAX_AGE)
    with pytest.raises(AttributeError):
        got.expected_value = 1.0  # type: ignore[misc]


# ---- Expected value ------------------------------------------------------------------------


def test_expected_value_worked_examples():
    # -110: d = 1.909090...; win 52%, loss 48%
    d = 1 + 100 / 110
    assert expected_value(SettlementProbs(0.52, 0.0, 0.48), d) == pytest.approx(0.52 * (d - 1) - 0.48, abs=1e-12)
    assert expected_value(SettlementProbs(0.5, 0.0, 0.5), 2.0) == pytest.approx(0.0, abs=1e-12)
    assert expected_value(SettlementProbs(0.6, 0.0, 0.4), 2.0) == pytest.approx(0.2, abs=1e-12)
    assert expected_value(SettlementProbs(0.4, 0.0, 0.6), 2.5) == pytest.approx(0.4 * 1.5 - 0.6, abs=1e-12)


def test_a_refunded_push_adds_zero_to_ev():
    d = 1 + 100 / 110
    with_push = expected_value(SettlementProbs(0.45, 0.10, 0.45), d)
    assert with_push == pytest.approx(0.45 * (d - 1) - 0.45, abs=1e-12)
    # moving mass into the push shrinks the loss and the win; EV never counts the push as a win or a loss
    assert expected_value(SettlementProbs(0.0, 1.0, 0.0), d) == 0.0


def test_ev_keeps_its_sign():
    assert expected_value(SettlementProbs(0.3, 0.0, 0.7), 2.0) < 0
    assert expected_value(SettlementProbs(0.7, 0.0, 0.3), 2.0) > 0


@pytest.mark.parametrize("d", [1.0, 0.5, 0, -2.0, float("nan"), float("inf"), True, None])
def test_expected_value_rejects_invalid_decimal_odds(d):
    with pytest.raises(BettingError):
        expected_value(SettlementProbs(0.5, 0.0, 0.5), d)


def test_ev_is_zero_at_the_break_even_probability():
    rng = random.Random(5)
    for _ in range(2000):
        d = rng.uniform(1.05, 12)
        push = rng.choice([0.0, rng.uniform(0, 0.3)])
        c = break_even_probability(d)
        probs = SettlementProbs(win=(1 - push) * c, push=push, loss=(1 - push) * (1 - c))
        assert expected_value(probs, d) == pytest.approx(0.0, abs=1e-12)
        assert price_edge(probs, d) == pytest.approx(0.0, abs=1e-12)


def test_ev_is_linear_in_win_probability_above_and_below_break_even():
    d = 2.2
    c = 1 / d
    assert expected_value(SettlementProbs(c + 0.05, 0.0, 1 - c - 0.05), d) > 0
    assert expected_value(SettlementProbs(c - 0.05, 0.0, 1 - c + 0.05), d) < 0


# ---- The four numbers, separately ----------------------------------------------------------


def test_break_even_probability_is_one_over_decimal():
    assert break_even_probability(2.5) == pytest.approx(0.4)
    assert break_even_probability(1 + 100 / 110) == pytest.approx(110 / 210)


@pytest.mark.parametrize("d", [1.0, 0.0, float("nan"), True])
def test_break_even_probability_rejects_invalid(d):
    with pytest.raises(BettingError):
        break_even_probability(d)


def test_fair_probability_edge_is_model_minus_market_and_keeps_its_sign():
    assert fair_probability_edge(0.55, 0.50) == pytest.approx(0.05)
    assert fair_probability_edge(0.45, 0.52) == pytest.approx(-0.07)
    assert fair_probability_edge(0.5, 0.5) == 0.0


def test_fair_probability_edge_is_none_when_the_market_probability_is_unavailable():
    assert fair_probability_edge(0.55, None) is None


@pytest.mark.parametrize("model, market", [(1.2, 0.5), (-0.1, 0.5), (0.5, 1.5), (0.5, -0.2), (float("nan"), 0.5)])
def test_fair_probability_edge_rejects_non_probabilities(model, market):
    with pytest.raises(BettingError):
        fair_probability_edge(model, market)


def test_price_edge_is_conditional_win_minus_break_even():
    d = 2.0
    assert price_edge(SettlementProbs(0.55, 0.0, 0.45), d) == pytest.approx(0.05)
    assert price_edge(SettlementProbs(0.45, 0.10, 0.45), d) == pytest.approx(0.0)  # conditional 0.5 vs 0.5
    assert price_edge(SettlementProbs(0.40, 0.0, 0.60), d) == pytest.approx(-0.10)


@pytest.mark.parametrize(
    "market, selection, line, forecast, expected",
    [
        ("spread", "home", -3.0, 6.0, 3.0),  # forecast home by 6, home covers -3 by 3
        ("spread", "away", -3.0, 6.0, -3.0),  # same game, away side is 3 points worse
        ("spread", "home", 3.5, -7.0, -3.5),  # forecast home loses by 7, home +3.5
        ("spread", "away", 3.5, -7.0, 3.5),
        ("total", "over", 47.5, 50.0, 2.5),
        ("total", "under", 47.5, 50.0, -2.5),
        ("total", "over", 47.5, 44.0, -3.5),
        ("total", "under", 47.5, 44.0, 3.5),
    ],
)
def test_point_difference_is_signed_from_the_selections_side(market, selection, line, forecast, expected):
    assert point_difference(market, selection, line, forecast) == pytest.approx(expected)


def test_point_difference_has_no_meaning_for_a_moneyline():
    with pytest.raises(BettingError):
        point_difference("moneyline", "home", None, 3.0)


@pytest.mark.parametrize("forecast", [None, float("nan"), float("inf"), "3", True])
def test_point_difference_rejects_invalid_forecast(forecast):
    with pytest.raises(BettingError):
        point_difference("spread", "home", -3.0, forecast)


# ---- evaluate: the four numbers together ---------------------------------------------------


def test_evaluate_returns_all_four_numbers():
    me = snap("spread", "home", -110, line=-3.0)
    opp = snap("spread", "away", -110, line=-3.0)
    probs = SettlementProbs(win=0.50, push=0.06, loss=0.44)
    got = evaluate(me, probs, now=NOW, max_age=MAX_AGE, opposing=[opp], forecast=6.0)
    assert isinstance(got, Edge)
    d = 1 + 100 / 110
    assert got.fair_probability_edge == pytest.approx(0.50 / 0.94 - 0.5, abs=1e-12)
    assert got.price_edge == pytest.approx(0.50 / 0.94 - 1 / d, abs=1e-12)
    assert got.expected_value == pytest.approx(0.50 * (d - 1) - 0.44, abs=1e-12)
    assert got.point_difference == pytest.approx(3.0)


def test_evaluate_missing_opposing_price_leaves_fair_edge_unavailable_but_computes_ev():
    me = snap("moneyline", "home", 150)
    probs = SettlementProbs(0.45, 0.0, 0.55)
    got = evaluate(me, probs, now=NOW, max_age=MAX_AGE)
    assert got.fair_probability_edge is None
    assert got.point_difference is None
    assert got.expected_value == pytest.approx(0.45 * 1.5 - 0.55, abs=1e-12)
    assert got.price_edge == pytest.approx(0.45 - 0.4, abs=1e-12)


def test_evaluate_edge_keeps_its_sign_against_the_selection():
    me = snap("moneyline", "home", -150)
    opp = snap("moneyline", "away", 130)
    got = evaluate(me, SettlementProbs(0.50, 0.0, 0.50), now=NOW, max_age=MAX_AGE, opposing=[opp])
    assert got.fair_probability_edge < 0
    assert got.expected_value < 0


def test_evaluate_three_way_moneyline():
    home = snap("moneyline", "home", 120)
    opp = [snap("moneyline", "away", 200), snap("moneyline", "draw", 300)]
    q = [1 / 2.2, 1 / 3.0, 1 / 4.0]
    got = evaluate(home, SettlementProbs(0.5, 0.0, 0.5), now=NOW, max_age=MAX_AGE, opposing=opp, three_way=True)
    assert got.fair_probability_edge == pytest.approx(0.5 - q[0] / sum(q), abs=1e-12)


def test_evaluate_three_way_without_draw_is_unavailable():
    home = snap("moneyline", "home", 120)
    got = evaluate(
        home, SettlementProbs(0.5, 0.0, 0.5), now=NOW, max_age=MAX_AGE, opposing=[snap("moneyline", "away", 200)],
        three_way=True,
    )
    assert got.fair_probability_edge is None


def test_evaluate_rejects_stale_odds():
    me = snap("moneyline", "home", 150)
    with pytest.raises(BettingError, match="stale"):
        evaluate(me, SettlementProbs(0.5, 0.0, 0.5), now=T0 + MAX_AGE + timedelta(seconds=1), max_age=MAX_AGE)


def test_evaluate_rejects_stale_opposing_odds_too():
    me = snap("moneyline", "home", -150, at=T0 + timedelta(minutes=29))
    opp = snap("moneyline", "away", 130, at=T0 + timedelta(minutes=29))
    # both are fresh at NOW; make the opposing side differ in time -> mismatched set rejected, never averaged
    with pytest.raises(BettingError):
        evaluate(
            me, SettlementProbs(0.5, 0.0, 0.5), now=NOW + timedelta(minutes=30), max_age=timedelta(minutes=45),
            opposing=[snap("moneyline", "away", 130, at=T0)],
        )
    evaluate(me, SettlementProbs(0.5, 0.0, 0.5), now=NOW + timedelta(minutes=29), max_age=MAX_AGE, opposing=[opp])


def test_evaluate_rejects_mixed_book_opposing():
    me = snap("moneyline", "home", -150)
    with pytest.raises(BettingError):
        evaluate(
            me, SettlementProbs(0.5, 0.0, 0.5), now=NOW, max_age=MAX_AGE,
            opposing=[snap("moneyline", "away", 130, book="bookB")],
        )


def test_evaluate_forecast_on_a_moneyline_is_rejected():
    with pytest.raises(BettingError):
        evaluate(snap("moneyline", "home", 150), SettlementProbs(0.5, 0.0, 0.5), now=NOW, max_age=MAX_AGE, forecast=3.0)


# ---- End to end on a small offline fixture -------------------------------------------------

# Joint distribution of (home_score, away_score): a tiny made-up game, probabilities sum to 1.
FIXTURE = {
    (27, 20): 0.20,  # home by 7, total 47
    (24, 21): 0.15,  # home by 3, total 45
    (20, 24): 0.15,  # away by 4, total 44
    (17, 20): 0.10,  # away by 3, total 37
    (23, 23): 0.05,  # tie, total 46
    (31, 17): 0.15,  # home by 14, total 48
    (14, 27): 0.10,  # away by 13, total 41
    (21, 14): 0.10,  # home by 7, total 35
}
PROFIT = {"win": lambda d: d - 1, "loss": lambda d: -1.0, "push": lambda d: 0.0}


def probs_for(snapshot, three_way=False):
    tally = {"win": 0.0, "push": 0.0, "loss": 0.0}
    for (hs, as_), p in FIXTURE.items():
        tally[settle(snapshot, hs, as_, three_way=three_way)] += p
    return SettlementProbs(tally["win"], tally["push"], tally["loss"])


@pytest.mark.parametrize(
    "market, selection, line, price",
    list(itertools.chain(
        [("moneyline", s, None, p) for s, p in [("home", -140), ("away", 120)]],
        [("spread", s, -3.0, -110) for s in ("home", "away")],
        [("spread", s, 3.5, -105) for s in ("home", "away")],
        [("total", s, 45.0, -112) for s in ("over", "under")],
        [("total", s, 46.5, 100) for s in ("over", "under")],
    )),
)
def test_end_to_end_ev_equals_the_probability_weighted_realised_profit(market, selection, line, price):
    s = snap(market, selection, price, line)
    probs = probs_for(s)
    assert probs.win + probs.push + probs.loss == pytest.approx(1.0)
    realised = sum(p * PROFIT[settle(s, hs, as_)](s.decimal_odds) for (hs, as_), p in FIXTURE.items())
    assert expected_value(probs, s.decimal_odds) == pytest.approx(realised, abs=1e-12)


def test_end_to_end_full_chain_from_snapshots_to_edge():
    home = snap("spread", "home", -110, -3.0)
    away = snap("spread", "away", -110, -3.0)
    probs = probs_for(home)
    assert probs.push == pytest.approx(0.15 + 0.0)  # (24,21) lands exactly on the -3 number
    mean_margin = sum((hs - as_) * p for (hs, as_), p in FIXTURE.items())
    got = evaluate(home, probs, now=NOW, max_age=MAX_AGE, opposing=[away], forecast=mean_margin)
    assert got.fair_probability_edge == pytest.approx(probs.conditional_win - 0.5, abs=1e-12)
    assert got.point_difference == pytest.approx(mean_margin - 3.0, abs=1e-12)
    away_got = evaluate(away, probs_for(away), now=NOW, max_age=MAX_AGE, opposing=[home], forecast=mean_margin)
    # the two sides of one fair market have opposite fair edges and opposite point differences
    assert away_got.fair_probability_edge == pytest.approx(-got.fair_probability_edge, abs=1e-12)
    assert away_got.point_difference == pytest.approx(-got.point_difference, abs=1e-12)
