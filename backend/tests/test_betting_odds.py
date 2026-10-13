"""Step 18b spec: odds conversion, raw implied probability, no-vig, market snapshots (brief section 8).

Pure functions: no database. Every test names the frozen clause it guards.
"""

import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from nflpi.betting.odds import (
    BettingError,
    american_to_decimal,
    decimal_to_american,
    no_vig,
    raw_implied_prob,
    to_decimal,
)
from nflpi.betting.snapshot import MarketSnapshot, ensure_fresh, no_vig_probabilities, no_vig_probability
from nflpi.predictions.market import devig_home_prob, implied_prob

T0 = datetime(2026, 10, 18, 16, 0, tzinfo=UTC)


def snap(selection="home", price=-110, *, market="spread", line=-3.5, book="bookA", at=T0, game="g1", fmt="american"):
    if market == "moneyline":
        line = None
    return MarketSnapshot(
        game_id=game,
        sportsbook=book,
        observed_at=at,
        market_type=market,
        selection=selection,
        line=line,
        odds_format=fmt,
        price=price,
    )


# ---- American to decimal ------------------------------------------------------------------


@pytest.mark.parametrize(
    "american, decimal",
    [(150, 2.5), (-200, 1.5), (100, 2.0), (-100, 2.0), (-110, 1 + 100 / 110), (250, 3.5), (-400, 1.25)],
)
def test_american_to_decimal_worked_examples(american, decimal):
    assert american_to_decimal(american) == pytest.approx(decimal, abs=1e-12)


def test_american_positive_uses_one_plus_a_over_100_and_negative_one_plus_100_over_abs_a():
    assert american_to_decimal(+175) == pytest.approx(1 + 175 / 100)
    assert american_to_decimal(-175) == pytest.approx(1 + 100 / 175)


@pytest.mark.parametrize("bad", [0, 0.0, -0.0, float("nan"), float("inf"), float("-inf"), True, False, None, "150", 50, -50, 99.5, -99.9])
def test_american_to_decimal_rejects_invalid_prices(bad):
    with pytest.raises(BettingError):
        american_to_decimal(bad)


def test_betting_error_is_a_value_error():
    assert issubclass(BettingError, ValueError)


@pytest.mark.parametrize("decimal, american", [(2.5, 150), (1.5, -200), (2.0, 100), (1.25, -400), (3.0, 200)])
def test_decimal_to_american_worked_examples(decimal, american):
    assert decimal_to_american(decimal) == pytest.approx(american, abs=1e-9)


@pytest.mark.parametrize("bad", [1.0, 0.99, 0, -2.0, float("nan"), float("inf"), True, None, "2.0"])
def test_decimal_to_american_rejects_invalid(bad):
    with pytest.raises(BettingError):
        decimal_to_american(bad)


def test_to_decimal_dispatches_on_format():
    assert to_decimal(150, "american") == pytest.approx(2.5)
    assert to_decimal(2.5, "decimal") == 2.5
    assert to_decimal(2, "decimal") == 2.0


@pytest.mark.parametrize("price", [1.0, 0.5, 0, -1.5, float("nan"), float("inf"), True, None])
def test_to_decimal_rejects_invalid_decimal_price(price):
    with pytest.raises(BettingError):
        to_decimal(price, "decimal")


@pytest.mark.parametrize("fmt", ["fractional", "AMERICAN", "", None, "dec"])
def test_to_decimal_rejects_unknown_format(fmt):
    with pytest.raises(BettingError):
        to_decimal(150, fmt)


def test_to_decimal_american_zero_is_invalid_via_dispatch():
    with pytest.raises(BettingError):
        to_decimal(0, "american")


# ---- Raw implied probability ---------------------------------------------------------------


def test_raw_implied_prob_is_one_over_decimal():
    assert raw_implied_prob(-110) == pytest.approx(110 / 210, abs=1e-12)
    assert raw_implied_prob(150) == pytest.approx(0.4, abs=1e-12)
    assert raw_implied_prob(2.5, "decimal") == pytest.approx(0.4, abs=1e-12)
    assert raw_implied_prob(-100) == pytest.approx(0.5)


def test_raw_implied_prob_rejects_invalid_price():
    with pytest.raises(BettingError):
        raw_implied_prob(0)


def test_raw_implied_prob_agrees_with_existing_market_module():
    for ml in list(range(-1500, -99, 7)) + list(range(100, 2500, 11)):
        assert raw_implied_prob(ml) == pytest.approx(implied_prob(ml), abs=1e-12)


# ---- Proportional no-vig on plain probabilities --------------------------------------------


def test_no_vig_two_way_worked_example():
    q = [0.6, 1 / 2.3]  # -150 / +130
    got = no_vig(q)
    assert got[0] == pytest.approx(0.6 / (0.6 + 1 / 2.3), abs=1e-12)
    assert got[1] == pytest.approx((1 / 2.3) / (0.6 + 1 / 2.3), abs=1e-12)
    assert sum(got) == pytest.approx(1.0, abs=1e-12)


def test_no_vig_three_way_worked_example():
    q = [1 / 2.2, 1 / 3.0, 1 / 4.0]  # +120, +200, +300
    total = sum(q)
    got = no_vig(q)
    assert got == pytest.approx([x / total for x in q], abs=1e-12)
    assert sum(got) == pytest.approx(1.0, abs=1e-12)


def test_no_vig_even_market_is_unchanged():
    assert no_vig([0.5, 0.5]) == pytest.approx([0.5, 0.5])


@pytest.mark.parametrize("bad", [[], [0.5], [0.5, 0.0], [0.5, -0.1], [0.5, float("nan")], [0.5, float("inf")], [0.5, True]])
def test_no_vig_rejects_incomplete_or_invalid_sets(bad):
    with pytest.raises(BettingError):
        no_vig(bad)


def test_no_vig_generated_sets_sum_to_one_and_keep_order():
    rng = random.Random(18)
    for _ in range(2000):
        n = rng.choice([2, 3])
        q = [rng.uniform(0.05, 0.9) for _ in range(n)]
        got = no_vig(q)
        assert sum(got) == pytest.approx(1.0, abs=1e-12)
        assert all(0 < p < 1 for p in got)
        assert [a < b for a, b in zip(q, q[1:])] == [a < b for a, b in zip(got, got[1:])]


def test_conversion_round_trips():
    for a in list(range(-3000, -99, 13)) + list(range(100, 5000, 17)):
        assert decimal_to_american(american_to_decimal(a)) == pytest.approx(a, rel=1e-9)
    rng = random.Random(7)
    for _ in range(2000):
        d = rng.uniform(1.01, 40)
        assert american_to_decimal(decimal_to_american(d)) == pytest.approx(d, rel=1e-9)


def test_no_vig_matches_existing_devig_on_generated_moneylines():
    rng = random.Random(3)
    for _ in range(1000):
        h = rng.choice([-1, 1]) * rng.randint(100, 900)
        a = rng.choice([-1, 1]) * rng.randint(100, 900)
        got = no_vig([raw_implied_prob(h), raw_implied_prob(a)])[0]
        assert got == pytest.approx(devig_home_prob(h, a), abs=1e-12)


# ---- Snapshot validation -------------------------------------------------------------------


def test_snapshot_carries_the_required_fields():
    s = snap("home", -110)
    assert (s.game_id, s.sportsbook, s.observed_at) == ("g1", "bookA", T0)
    assert (s.market_type, s.selection, s.line, s.odds_format, s.price) == ("spread", "home", -3.5, "american", -110)


def test_snapshot_is_immutable():
    s = snap()
    with pytest.raises(AttributeError):
        s.price = -120  # type: ignore[misc]


def test_snapshot_valid_variants_construct():
    snap("home", 150, market="moneyline")
    snap("draw", 800, market="moneyline")
    snap("over", -105, market="total", line=47.5)
    snap("under", 1.95, market="total", line=47.5, fmt="decimal")
    snap("away", -110, market="spread", line=0.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"game": ""},
        {"game": None},
        {"book": ""},
        {"book": "  "},
        {"at": datetime(2026, 10, 18, 16, 0)},  # naive
        {"at": "2026-10-18"},
        {"market": "parlay"},
        {"market": "moneyline", "selection": "over"},
        {"market": "spread", "selection": "over"},
        {"market": "total", "selection": "home", "line": 47.5},
        {"market": "spread", "selection": "draw"},
        {"market": "spread", "line": None},
        {"market": "total", "selection": "over", "line": None},
        {"market": "spread", "line": float("nan")},
        {"market": "total", "selection": "over", "line": float("inf")},
        {"market": "spread", "line": "3.5"},
        {"price": 0},
        {"price": 50},
        {"fmt": "decimal", "price": 1.0},
        {"fmt": "fractional"},
    ],
)
def test_snapshot_rejects_invalid_input(kwargs):
    with pytest.raises(BettingError):
        snap(**kwargs)


def test_snapshot_moneyline_must_not_carry_a_line():
    with pytest.raises(BettingError):
        MarketSnapshot("g1", "bookA", T0, "moneyline", "home", 3.5, "american", 150)


def test_snapshot_exposes_decimal_and_raw_implied_probability():
    s = snap("home", 150, market="moneyline")
    assert s.decimal_odds == pytest.approx(2.5)
    assert s.implied_prob == pytest.approx(0.4)


# ---- Stale odds ----------------------------------------------------------------------------


def test_ensure_fresh_accepts_age_up_to_and_including_the_maximum():
    s = snap()
    ensure_fresh(s, T0 + timedelta(minutes=30), timedelta(minutes=30))
    ensure_fresh(s, T0, timedelta(0))


def test_ensure_fresh_rejects_odds_older_than_the_maximum():
    with pytest.raises(BettingError, match="stale"):
        ensure_fresh(snap(), T0 + timedelta(minutes=30, seconds=1), timedelta(minutes=30))


def test_ensure_fresh_rejects_odds_observed_in_the_future():
    with pytest.raises(BettingError):
        ensure_fresh(snap(), T0 - timedelta(seconds=1), timedelta(hours=1))


@pytest.mark.parametrize("max_age", [timedelta(seconds=-1), 30, None])
def test_ensure_fresh_rejects_bad_max_age(max_age):
    with pytest.raises(BettingError):
        ensure_fresh(snap(), T0, max_age)


def test_ensure_fresh_rejects_naive_now():
    with pytest.raises(BettingError):
        ensure_fresh(snap(), datetime(2026, 10, 18, 16, 5), timedelta(hours=1))


# ---- No-vig inside one complete set from one book, time and line --------------------------


def ml_pair(h=-150, a=130, **kw):
    return [snap("home", h, market="moneyline", **kw), snap("away", a, market="moneyline", **kw)]


def test_two_way_moneyline_no_vig():
    got = no_vig_probabilities(ml_pair())
    expected = no_vig([0.6, 1 / 2.3])
    assert got["home"] == pytest.approx(expected[0], abs=1e-12)
    assert got["away"] == pytest.approx(expected[1], abs=1e-12)
    assert sum(got.values()) == pytest.approx(1.0, abs=1e-12)


def test_order_of_snapshots_does_not_matter():
    a = no_vig_probabilities(ml_pair())
    b = no_vig_probabilities(list(reversed(ml_pair())))
    assert a == pytest.approx(b)


def test_three_way_moneyline_no_vig():
    three = ml_pair(120, 200) + [snap("draw", 300, market="moneyline")]
    got = no_vig_probabilities(three, three_way=True)
    q = [1 / 2.2, 1 / 3.0, 1 / 4.0]
    assert [got["home"], got["away"], got["draw"]] == pytest.approx([x / sum(q) for x in q], abs=1e-12)
    assert sum(got.values()) == pytest.approx(1.0, abs=1e-12)


def test_three_way_without_the_draw_price_is_unavailable_not_a_two_way_guess():
    assert no_vig_probabilities(ml_pair(120, 200), three_way=True) is None


def test_two_way_with_a_draw_price_is_rejected():
    with pytest.raises(BettingError):
        no_vig_probabilities(ml_pair(120, 200) + [snap("draw", 300, market="moneyline")])


def test_spread_pair_with_the_same_home_line():
    got = no_vig_probabilities([snap("home", -110), snap("away", -110)])
    assert got == pytest.approx({"home": 0.5, "away": 0.5})
    got = no_vig_probabilities([snap("home", -120), snap("away", 100)])
    assert got["home"] == pytest.approx((120 / 220) / (120 / 220 + 0.5), abs=1e-12)


def test_total_pair_over_under():
    got = no_vig_probabilities([snap("over", -115, market="total", line=47.5), snap("under", -105, market="total", line=47.5)])
    q_o, q_u = 115 / 215, 105 / 205
    assert got["over"] == pytest.approx(q_o / (q_o + q_u), abs=1e-12)
    assert got["under"] == pytest.approx(q_u / (q_o + q_u), abs=1e-12)


def test_mixed_odds_formats_inside_one_set_are_fine():
    got = no_vig_probabilities([snap("home", -110), snap("away", 1.909090909090909, fmt="decimal")])
    assert got == pytest.approx({"home": 0.5, "away": 0.5})


@pytest.mark.parametrize(
    "other",
    [
        {"book": "bookB"},
        {"at": T0 + timedelta(seconds=1)},
        {"game": "g2"},
    ],
)
def test_mixed_book_time_or_game_is_rejected_not_averaged(other):
    with pytest.raises(BettingError):
        no_vig_probabilities([snap("home", -110), snap("away", -110, **other)])


def test_mixed_line_is_rejected():
    with pytest.raises(BettingError):
        no_vig_probabilities([snap("home", -110, line=-3.5), snap("away", -110, line=-3.0)])
    with pytest.raises(BettingError):
        no_vig_probabilities(
            [snap("over", -110, market="total", line=47.5), snap("under", -110, market="total", line=48.0)]
        )


def test_mixed_market_type_is_rejected():
    with pytest.raises(BettingError):
        no_vig_probabilities([snap("home", -110, market="moneyline"), snap("away", -110, market="spread")])


def test_mismatch_is_rejected_even_when_the_set_is_also_incomplete():
    with pytest.raises(BettingError):
        no_vig_probabilities([snap("home", -110), snap("home", -110, book="bookB")])


def test_duplicate_selection_is_rejected():
    with pytest.raises(BettingError):
        no_vig_probabilities([snap("home", -110), snap("home", -105)])


def test_empty_input_is_rejected():
    with pytest.raises(BettingError):
        no_vig_probabilities([])


def test_missing_opposing_price_gives_none_never_zero():
    assert no_vig_probabilities([snap("home", -110)]) is None
    assert no_vig_probabilities([snap("over", -110, market="total", line=47.5)]) is None


def test_no_vig_probability_for_one_selection():
    me = snap("home", -150, market="moneyline")
    other = snap("away", 130, market="moneyline")
    assert no_vig_probability(me, [other]) == pytest.approx(0.6 / (0.6 + 1 / 2.3), abs=1e-12)
    assert no_vig_probability(me, []) is None
    assert no_vig_probability(me, None) is None


def test_no_vig_probability_rejects_mismatched_or_duplicate_opposing():
    me = snap("home", -150, market="moneyline")
    with pytest.raises(BettingError):
        no_vig_probability(me, [snap("away", 130, market="moneyline", book="bookB")])
    with pytest.raises(BettingError):
        no_vig_probability(me, [snap("home", 130, market="moneyline")])


def test_snapshot_no_vig_agrees_with_existing_devig_on_generated_pairs():
    rng = random.Random(11)
    for _ in range(500):
        h = rng.choice([-1, 1]) * rng.randint(100, 800)
        a = rng.choice([-1, 1]) * rng.randint(100, 800)
        got = no_vig_probabilities(ml_pair(h, a))
        assert got["home"] == pytest.approx(devig_home_prob(h, a), abs=1e-12)
        assert math.isclose(got["home"] + got["away"], 1.0, abs_tol=1e-12)
