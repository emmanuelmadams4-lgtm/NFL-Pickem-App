"""Step 18b spec: settlement of moneyline, spread and total with pushes (brief section 8).

Convention: M = home_score - away_score, h = quoted home spread. Home covers when M + h > 0, pushes when
M + h = 0. Total L: over above, under below, equal is a push.
"""

from datetime import UTC, datetime

import pytest

from nflpi.betting.odds import BettingError
from nflpi.betting.settle import settle, settle_moneyline, settle_spread, settle_total
from nflpi.betting.snapshot import MarketSnapshot

T0 = datetime(2026, 10, 18, 16, 0, tzinfo=UTC)
OPPOSITE = {"win": "loss", "loss": "win", "push": "push"}


# ---- Moneyline -----------------------------------------------------------------------------


def test_two_way_moneyline_winner_and_loser():
    assert settle_moneyline("home", 24, 17) == "win"
    assert settle_moneyline("away", 24, 17) == "loss"
    assert settle_moneyline("home", 10, 13) == "loss"
    assert settle_moneyline("away", 10, 13) == "win"


def test_two_way_moneyline_tie_is_a_refunded_push_for_both_sides():
    assert settle_moneyline("home", 20, 20) == "push"
    assert settle_moneyline("away", 20, 20) == "push"


def test_three_way_moneyline_tie_pays_the_draw_only():
    assert settle_moneyline("draw", 20, 20, three_way=True) == "win"
    assert settle_moneyline("home", 20, 20, three_way=True) == "loss"
    assert settle_moneyline("away", 20, 20, three_way=True) == "loss"


def test_three_way_moneyline_decisive_game_loses_the_draw():
    assert settle_moneyline("draw", 24, 17, three_way=True) == "loss"
    assert settle_moneyline("home", 24, 17, three_way=True) == "win"
    assert settle_moneyline("away", 24, 17, three_way=True) == "loss"
    assert settle_moneyline("away", 10, 13, three_way=True) == "win"


def test_two_way_moneyline_has_no_draw_selection():
    with pytest.raises(BettingError):
        settle_moneyline("draw", 20, 20)


@pytest.mark.parametrize("sel", ["over", "under", "", None, "HOME"])
def test_moneyline_rejects_unknown_selection(sel):
    with pytest.raises(BettingError):
        settle_moneyline(sel, 20, 10)


# ---- Spread --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "h, hs, as_, home, away",
    [
        (-3.5, 27, 23, "win", "loss"),  # M=4, M+h=0.5
        (-3.5, 26, 23, "loss", "win"),  # M=3, M+h=-0.5
        (-3.0, 26, 23, "push", "push"),  # M=3, M+h=0
        (-3.0, 27, 23, "win", "loss"),
        (-3.0, 25, 23, "loss", "win"),
        (3.0, 20, 23, "push", "push"),  # home +3 loses by 3
        (3.5, 20, 23, "win", "loss"),  # underdog home +3.5 loses by 3
        (7.0, 17, 24, "push", "push"),
        (-7.0, 30, 24, "loss", "win"),  # favourite wins by 6, does not cover -7
        (0.0, 21, 21, "push", "push"),  # pick'em tie
        (0.0, 24, 21, "win", "loss"),
        (0.0, 21, 24, "loss", "win"),
    ],
)
def test_spread_settlement_worked_examples(h, hs, as_, home, away):
    assert settle_spread("home", h, hs, as_) == home
    assert settle_spread("away", h, hs, as_) == away


def test_spread_convention_exhaustive_loop():
    for h2 in range(-60, 61):  # half-point steps
        h = h2 / 2
        for hs in range(0, 50, 3):
            for as_ in range(0, 50, 5):
                m = (hs - as_) + h
                home = settle_spread("home", h, hs, as_)
                away = settle_spread("away", h, hs, as_)
                assert home == ("win" if m > 0 else "push" if m == 0 else "loss")
                assert not (home == "win" and away == "win")
                assert away == OPPOSITE[home]


@pytest.mark.parametrize("sel", ["over", "draw", "", None])
def test_spread_rejects_unknown_selection(sel):
    with pytest.raises(BettingError):
        settle_spread(sel, -3.5, 20, 10)


@pytest.mark.parametrize("line", [None, float("nan"), float("inf"), "3.5", True])
def test_spread_rejects_invalid_line(line):
    with pytest.raises(BettingError):
        settle_spread("home", line, 20, 10)


# ---- Total ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line, hs, as_, over, under",
    [
        (47.5, 28, 20, "win", "loss"),  # 48 > 47.5
        (47.5, 27, 20, "loss", "win"),  # 47 < 47.5
        (47.0, 27, 20, "push", "push"),  # 47 == 47
        (47.0, 28, 20, "win", "loss"),
        (47.0, 26, 20, "loss", "win"),
        (0.5, 0, 0, "loss", "win"),
        (0.0, 0, 0, "push", "push"),
    ],
)
def test_total_settlement_worked_examples(line, hs, as_, over, under):
    assert settle_total("over", line, hs, as_) == over
    assert settle_total("under", line, hs, as_) == under


def test_total_exhaustive_loop_over_and_under_never_both_win():
    for l2 in range(0, 241):
        line = l2 / 2
        for hs in range(0, 50, 4):
            for as_ in range(0, 50, 7):
                over = settle_total("over", line, hs, as_)
                under = settle_total("under", line, hs, as_)
                assert over == ("win" if hs + as_ > line else "push" if hs + as_ == line else "loss")
                assert under == OPPOSITE[over]


@pytest.mark.parametrize("sel", ["home", "away", "draw", None])
def test_total_rejects_unknown_selection(sel):
    with pytest.raises(BettingError):
        settle_total(sel, 47.5, 20, 10)


@pytest.mark.parametrize("line", [None, float("nan"), float("-inf"), "47.5"])
def test_total_rejects_invalid_line(line):
    with pytest.raises(BettingError):
        settle_total("over", line, 20, 10)


# ---- Scores are validated ------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-1, 20.5, True, None, "20", float("nan")])
def test_scores_must_be_non_negative_integers(bad):
    with pytest.raises(BettingError):
        settle_moneyline("home", bad, 10)
    with pytest.raises(BettingError):
        settle_moneyline("home", 10, bad)
    with pytest.raises(BettingError):
        settle_spread("home", -3.5, bad, 10)
    with pytest.raises(BettingError):
        settle_total("over", 47.5, 10, bad)


def test_whole_number_float_scores_are_accepted():
    assert settle_moneyline("home", 24.0, 17.0) == "win"


# ---- Settle a snapshot ---------------------------------------------------------------------


def make(market, selection, line=None):
    price = 150 if market == "moneyline" else -110
    return MarketSnapshot("g1", "bookA", T0, market, selection, line, "american", price)


def test_settle_dispatches_on_market_type():
    assert settle(make("moneyline", "home"), 24, 17) == "win"
    assert settle(make("moneyline", "home"), 20, 20) == "push"
    assert settle(make("moneyline", "draw"), 20, 20, three_way=True) == "win"
    assert settle(make("spread", "home", -3.0), 26, 23) == "push"
    assert settle(make("spread", "away", -3.5), 26, 23) == "win"
    assert settle(make("total", "over", 47.5), 28, 20) == "win"
    assert settle(make("total", "under", 47.0), 27, 20) == "push"


def test_one_point_margin_decides_a_moneyline():
    assert settle_moneyline("home", 24, 23) == "win"
    assert settle_moneyline("away", 24, 23) == "loss"
    assert settle_moneyline("home", 23, 24) == "loss"
    assert settle_moneyline("away", 23, 24) == "win"
