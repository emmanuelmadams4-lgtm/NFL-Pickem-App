"""Step 18d spec: pure pick rules, one test group per frozen clause P1..P25 (docs/model/PICK_RULES.md).

Spread sign: functions take the HOME spread h (home covers when margin + h > 0). Straight-up, ATS, totals and the
confidence pool are separate modes; betting advice is a separate function that cannot touch a pick.
"""

import inspect
import itertools
import math
import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import nflpi
from nflpi.betting.edge import SettlementProbs
from nflpi.betting.settle import settle_moneyline, settle_spread, settle_total
from nflpi.betting.snapshot import MarketSnapshot
from nflpi.picks import (
    Advice,
    GameInputs,
    Pick,
    PicksError,
    PickSet,
    Rubric,
    betting_advice,
    confidence_pool,
    grade_pick,
    home_spread_from_nflverse,
    make_picks,
    pick_ats,
    pick_points,
    pick_straight_up,
    pick_totals,
)

T0 = datetime(2026, 10, 18, 16, 0, tzinfo=UTC)
NOW = T0 + timedelta(minutes=5)
MAX_AGE = timedelta(minutes=30)
ASSUMED_LABEL = "Assumed: straight-up pick'em (pool rules unavailable)"
NAN = float("nan")
INF = float("inf")


def game(**kw) -> GameInputs:
    """A valid game; the away chance is derived from the home and tie chances unless given."""
    kw.setdefault("game_id", "g1")
    home = kw.setdefault("p_home_win", 0.6)
    kw.setdefault("p_away_win", 1 - home - kw.get("p_tie", 0.0))
    return GameInputs(**kw)


def ats_game(home_cover, away_cover, spread=-3.0, **kw) -> GameInputs:
    push = 1 - home_cover - away_cover
    return game(home_spread=spread, p_home_cover=home_cover, p_away_cover=away_cover, p_spread_push=push, **kw)


def total_game(over, under, total=44.5, **kw) -> GameInputs:
    return game(total=total, p_over=over, p_under=under, p_total_push=1 - over - under, **kw)


def one(picks: PickSet) -> Pick:
    assert len(picks.picks) == 1
    return picks.picks[0]


def su(**kw) -> Pick:
    options = {k: kw.pop(k) for k in ("tie_rule", "tie_break", "close_band", "disagree_band") if k in kw}
    return one(pick_straight_up([game(**kw)], **options))


def snap(price=2.0, at=T0) -> MarketSnapshot:
    return MarketSnapshot("g1", "bookA", at, "moneyline", "home", None, "decimal", price)


def ev_probs(ev: float) -> SettlementProbs:
    """Win and loss chances that give exactly this expected value at decimal price 2.0 (binary-exact for k/64)."""
    win = (1 + ev) / 2
    return SettlementProbs(win, 0.0, 1 - win)


def advice(ev=0.2, *, at=T0, rubric=None, qb_missing=False, price=2.0) -> Advice:
    return betting_advice(
        snap(price, at), ev_probs(ev), now=NOW, max_age=MAX_AGE, rubric=rubric, qb_missing=qb_missing
    )


THRESHOLDS = (0.0625, 0.125, 0.1875, 0.25, 0.3125)
VALID = Rubric(THRESHOLDS, validated=True, provisional=False)


# ---- P1 GameInputs validation -----------------------------------------------------------------


def test_p1_accepts_valid_inputs_and_boundary_probabilities():
    assert game(p_home_win=1.0, p_away_win=0.0).p_home_win == 1.0
    assert game(p_home_win=0.0, p_away_win=1.0).p_away_win == 1.0
    assert game(p_home_win=0.45, p_away_win=0.45, p_tie=0.1).p_tie == 0.1
    assert game(p_home_win=0.5, p_away_win=0.5 + 1e-10).p_away_win > 0.5  # inside the 1e-9 tolerance
    assert game(p_home_win=0.4, p_away_win=0.6, home_spread=-3.5, total=44.5).total == 44.5


@pytest.mark.parametrize(
    "kw",
    [
        {"game_id": ""},
        {"p_home_win": -0.1, "p_away_win": 1.1},
        {"p_home_win": 1.1, "p_away_win": -0.1},
        {"p_home_win": NAN, "p_away_win": 0.4},
        {"p_home_win": INF, "p_away_win": 0.4},
        {"p_home_win": 0.5, "p_away_win": 0.5, "p_tie": 1.5},
        {"p_home_win": 0.5, "p_away_win": 0.5, "p_tie": NAN},
        {"p_home_win": 0.5, "p_away_win": 0.5 + 1e-7},
        {"p_home_win": 0.5, "p_away_win": 0.4},
        {"p_home_win": 0.5, "p_away_win": 0.5, "p_tie": 0.1},
    ],
)
def test_p1_rejects_bad_win_tie_inputs(kw):
    with pytest.raises(PicksError):
        GameInputs(**{"game_id": "g1", **kw})


@pytest.mark.parametrize(
    "kw",
    [
        {"p_home_cover": 0.5},
        {"p_away_cover": 0.5},
        {"p_spread_push": 0.5},
        {"p_home_cover": 0.5, "p_away_cover": 0.5},  # push missing: a partial set
        {"p_home_cover": 0.5, "p_away_cover": 0.4, "p_spread_push": 0.2},  # sums to 1.1
        {"p_home_cover": 0.5, "p_away_cover": 0.4, "p_spread_push": 0.05},  # sums to 0.95
        {"p_home_cover": 1.2, "p_away_cover": -0.3, "p_spread_push": 0.1},
        {"p_home_cover": NAN, "p_away_cover": 0.5, "p_spread_push": 0.5},
        {"p_over": 0.5},
        {"p_under": 0.5},
        {"p_total_push": 0.5},
        {"p_over": 0.5, "p_under": 0.4, "p_total_push": 0.2},
        {"p_over": 0.5, "p_under": 0.4, "p_total_push": 0.05},
        {"p_over": INF, "p_under": 0.5, "p_total_push": 0.5},
    ],
)
def test_p1_rejects_partial_or_non_summing_cover_and_total_sets(kw):
    with pytest.raises(PicksError):
        game(home_spread=-3.0, total=44.5, **kw)


def test_p1_rejects_chances_without_their_line_and_non_finite_lines():
    with pytest.raises(PicksError):
        game(p_home_cover=0.5, p_away_cover=0.5, p_spread_push=0.0)  # no home_spread
    with pytest.raises(PicksError):
        game(p_over=0.5, p_under=0.5, p_total_push=0.0)  # no total
    for bad in (NAN, INF, -INF):
        with pytest.raises(PicksError):
            game(home_spread=bad)
        with pytest.raises(PicksError):
            game(total=bad)
    assert ats_game(0.5, 0.5).home_spread == -3.0 and total_game(0.5, 0.5).total == 44.5


def test_p1_game_inputs_are_frozen():
    with pytest.raises(AttributeError):
        game().p_home_win = 0.1  # type: ignore[misc]


# ---- P2 / P3 / P4 straight-up ------------------------------------------------------------------


def test_p2_picks_larger_share_for_each_side():
    assert su(p_home_win=0.6).selection == "home"
    assert su(p_home_win=0.4).selection == "away"
    assert su(p_home_win=0.451, p_away_win=0.449, p_tie=0.1, tie_break="second").selection == "home"
    assert su(p_home_win=0.449, p_away_win=0.451, p_tie=0.1, tie_break="first").selection == "away"


def test_p2_share_uses_half_the_tie_chance_or_none_of_it():
    half = su(p_home_win=0.46, p_away_win=0.44, p_tie=0.10, tie_rule="half")
    loss = su(p_home_win=0.46, p_away_win=0.44, p_tie=0.10, tie_rule="loss")
    assert half.selection == loss.selection == "home"
    assert half.probability == pytest.approx(0.51)
    assert loss.probability == pytest.approx(0.46)
    assert su(p_home_win=0.3, p_away_win=0.6, p_tie=0.1).probability == pytest.approx(0.65)  # default is half


@pytest.mark.parametrize("tie_rule", ["half", "loss"])
@pytest.mark.parametrize("tie_break, side", [("first", "home"), ("second", "away")])
def test_p3_exactly_equal_shares_go_to_tie_break(tie_rule, tie_break, side):
    pick = su(p_home_win=0.45, p_away_win=0.45, p_tie=0.1, tie_rule=tie_rule, tie_break=tie_break)
    assert pick.selection == side
    assert "EXACT_TIE_BREAK" in pick.warnings


def test_p3_no_tie_break_warning_when_shares_differ_and_default_is_first():
    assert "EXACT_TIE_BREAK" not in su(p_home_win=0.451, p_away_win=0.449, p_tie=0.1).warnings
    assert su(p_home_win=0.5, p_away_win=0.5).selection == "home"


def test_p4_probability_is_chosen_share_and_expected_points_equal_it():
    for kw in ({"p_home_win": 0.7}, {"p_home_win": 0.3}, {"p_home_win": 0.4, "p_away_win": 0.5, "p_tie": 0.1}):
        pick = su(**kw)
        assert pick.mode == "straight_up"
        assert pick.expected_points == pick.probability
    assert su(p_home_win=0.7).probability == pytest.approx(0.7)
    assert su(p_home_win=0.3).probability == pytest.approx(0.7)
    assert su(p_home_win=0.4, p_away_win=0.5, p_tie=0.1).probability == pytest.approx(0.55)


# ---- P5 warnings -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "home, expect_close",
    [(0.74, True), (0.75, False), (0.76, False), (0.26, True), (0.25, False)],
)
def test_p5_close_call_boundary_at_half_plus_band(home, expect_close):
    pick = su(p_home_win=home, close_band=0.25)
    assert ("CLOSE_CALL" in pick.warnings) is expect_close


def test_p5_close_call_default_band_is_five_points():
    assert "CLOSE_CALL" in su(p_home_win=0.54).warnings
    assert "CLOSE_CALL" not in su(p_home_win=0.56).warnings
    assert "CLOSE_CALL" in su(p_home_win=0.6, close_band=0.2).warnings


def test_p5_qb_and_stale_flags_each_add_their_warning_only():
    plain = su(p_home_win=0.8).warnings
    assert "QB_MISSING" not in plain and "STALE_INPUTS" not in plain
    qb = su(p_home_win=0.8, qb_missing=True).warnings
    assert "QB_MISSING" in qb and "STALE_INPUTS" not in qb
    stale = su(p_home_win=0.8, stale_inputs=True).warnings
    assert "STALE_INPUTS" in stale and "QB_MISSING" not in stale


@pytest.mark.parametrize(
    "home, market, warns",
    [(0.75, 0.50, True), (0.75, 0.51, False), (0.75, 0.45, True), (0.25, 0.50, True), (0.25, 0.49, False)],
)
def test_p5_market_disagreement_at_or_above_band(home, market, warns):
    pick = su(p_home_win=home, market_home_win=market, disagree_band=0.25)
    assert ("MODEL_DISAGREES_WITH_MARKET" in pick.warnings) is warns


def test_p5_market_disagreement_defaults_and_missing_market():
    assert "MODEL_DISAGREES_WITH_MARKET" in su(p_home_win=0.7, market_home_win=0.5).warnings
    assert "MODEL_DISAGREES_WITH_MARKET" not in su(p_home_win=0.6, market_home_win=0.5).warnings
    assert "MODEL_DISAGREES_WITH_MARKET" not in su(p_home_win=0.9).warnings


# ---- P6 / P7 ATS -----------------------------------------------------------------------------


def ats(g: GameInputs, **options) -> Pick:
    return one(pick_ats([g], **options))


def test_p6_picks_larger_cover_chance_and_values_pushes():
    home = ats(ats_game(0.45, 0.40))
    away = ats(ats_game(0.30, 0.55))
    assert (home.selection, away.selection) == ("home", "away")
    assert home.mode == "ats"
    assert home.expected_points == pytest.approx(0.45)  # default push_rule gives push no points
    assert away.expected_points == pytest.approx(0.55)


def test_p6_push_rule_half_adds_half_the_push_chance():
    g = ats_game(0.45, 0.40)
    assert ats(g, push_rule="no_points").expected_points == pytest.approx(0.45)
    assert ats(g, push_rule="half").expected_points == pytest.approx(0.45 + 0.5 * 0.15)
    assert ats(ats_game(0.30, 0.55), push_rule="half").expected_points == pytest.approx(0.55 + 0.5 * 0.15)


@pytest.mark.parametrize("push_rule", ["no_points", "half"])
@pytest.mark.parametrize("tie_break, side", [("first", "home"), ("second", "away")])
def test_p6_equal_expected_points_go_to_tie_break(push_rule, tie_break, side):
    assert ats(ats_game(0.45, 0.45), push_rule=push_rule, tie_break=tie_break).selection == side


def test_p6_just_either_side_of_equal_ignores_tie_break():
    assert ats(ats_game(0.451, 0.449), tie_break="second").selection == "home"
    assert ats(ats_game(0.449, 0.451), tie_break="first").selection == "away"


def test_p7_records_spread_as_line_with_model_basis():
    for spread in (-3.0, 0.0, 7.5):
        pick = ats(ats_game(0.6, 0.3, spread=spread))
        assert pick.line == spread
        assert pick.basis == "model"
        assert "NO_COVER_MODEL" not in pick.warnings


# ---- P8 / P9 ATS fallbacks ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "margin, spread, side",
    [(3.0, -2.5, "home"), (2.0, -2.5, "away"), (-4.0, 3.0, "away"), (-2.0, 3.0, "home"), (0.1, 0.0, "home")],
)
def test_p8_margin_plus_spread_decides_the_fallback(margin, spread, side):
    pick = ats(game(expected_margin=margin, home_spread=spread, p_home_win=0.2))
    assert pick.selection == side
    assert pick.basis == "margin_fallback"
    assert "NO_COVER_MODEL" in pick.warnings
    assert pick.line == spread


@pytest.mark.parametrize("tie_break, side", [("first", "home"), ("second", "away")])
def test_p8_margin_plus_spread_exactly_zero_goes_to_tie_break(tie_break, side):
    pick = ats(game(expected_margin=2.5, home_spread=-2.5), tie_break=tie_break)
    assert (pick.selection, pick.basis) == (side, "margin_fallback")


def test_p9_without_margin_falls_back_to_the_straight_up_pick():
    away = ats(game(p_home_win=0.3, home_spread=-3.0))
    assert (away.selection, away.basis) == ("away", "straight_up_fallback")
    assert "NO_COVER_MODEL" in away.warnings and "NO_SPREAD" not in away.warnings
    assert ats(game(p_home_win=0.8, home_spread=-3.0)).selection == "home"


def test_p9_missing_spread_adds_no_spread_even_with_a_margin():
    for kw in ({}, {"expected_margin": 6.0}):
        pick = ats(game(p_home_win=0.3, **kw))
        assert (pick.selection, pick.basis) == ("away", "straight_up_fallback")
        assert {"NO_COVER_MODEL", "NO_SPREAD"} <= set(pick.warnings)


# ---- P10 totals ------------------------------------------------------------------------------


def tot(g: GameInputs, **options) -> Pick:
    return one(pick_totals([g], **options))


def test_p10_picks_larger_over_or_under_chance_with_line_and_model_basis():
    over = tot(total_game(0.55, 0.35))
    under = tot(total_game(0.30, 0.60))
    assert (over.selection, under.selection) == ("over", "under")
    assert over.mode == "totals" and over.line == 44.5 and over.basis == "model"
    assert over.expected_points == pytest.approx(0.55)
    assert tot(total_game(0.55, 0.35), push_rule="half").expected_points == pytest.approx(0.55 + 0.5 * 0.10)
    assert "NO_TOTAL_MODEL" not in over.warnings


@pytest.mark.parametrize("tie_break, side", [("first", "over"), ("second", "under")])
def test_p10_equal_chances_go_to_tie_break_side(tie_break, side):
    assert tot(total_game(0.45, 0.45), tie_break=tie_break).selection == side
    assert tot(total_game(0.45, 0.45), tie_break=tie_break, push_rule="half").selection == side
    assert tot(total_game(0.451, 0.449), tie_break="second").selection == "over"


@pytest.mark.parametrize("expected, side", [(47.0, "over"), (44.4, "under"), (44.6, "over"), (30.0, "under")])
def test_p10_expected_total_against_line_fallback(expected, side):
    pick = tot(game(total=44.5, expected_total=expected))
    assert (pick.selection, pick.basis, pick.line) == (side, "margin_fallback", 44.5)
    assert "NO_TOTAL_MODEL" in pick.warnings


@pytest.mark.parametrize("tie_break, side", [("first", "over"), ("second", "under")])
def test_p10_expected_total_equal_to_line_goes_to_tie_break(tie_break, side):
    assert tot(game(total=44.5, expected_total=44.5), tie_break=tie_break).selection == side


@pytest.mark.parametrize("tie_break, side", [("first", "over"), ("second", "under")])
def test_p10_nothing_to_go_on_defaults_to_tie_break_side(tie_break, side):
    pick = tot(game(total=44.5), tie_break=tie_break)
    assert (pick.selection, pick.basis, pick.line) == (side, "default", 44.5)
    assert tot(game(), tie_break=tie_break).selection == side  # no total at all


# ---- P11 coin-flip label -----------------------------------------------------------------------


def test_p11_every_ats_and_totals_pick_carries_the_label():
    games = [
        ats_game(0.6, 0.3),
        game(expected_margin=3.0, home_spread=-1.0),
        game(p_home_win=0.7),
        total_game(0.6, 0.3),
        game(total=44.5, expected_total=50.0),
        game(),
    ]
    for g in games:
        assert "NOT_SHOWN_TO_BEAT_COIN_FLIP" in one(pick_ats([g])).warnings
        assert "NOT_SHOWN_TO_BEAT_COIN_FLIP" in one(pick_totals([g])).warnings


# ---- P12 one pick per game ---------------------------------------------------------------------


def _mixed_game(idx: int, flags) -> GameInputs:
    tie, spread, cover, total, over, margin = flags
    kw: dict = {"game_id": f"g{idx:02d}", "p_home_win": 0.3 + 0.01 * (idx % 50)}
    kw["p_tie"] = 0.04 if tie else 0.0
    kw["p_away_win"] = 1 - kw["p_home_win"] - kw["p_tie"]
    if spread or cover:
        kw["home_spread"] = -3.0 + idx % 5
    if cover:
        kw.update(p_home_cover=0.5, p_away_cover=0.3, p_spread_push=0.2)
    if total or over:
        kw["total"] = 40.5 + idx % 7
    if over:
        kw.update(p_over=0.3, p_under=0.6, p_total_push=0.1)
    if margin:
        kw.update(expected_margin=2.5, expected_total=48.0)
    return GameInputs(**kw)


MODES = [pick_straight_up, pick_ats, pick_totals, confidence_pool]


def test_p12_every_mode_returns_one_pick_per_game_in_order_for_every_mix_of_data():
    games = [_mixed_game(i, flags) for i, flags in enumerate(itertools.product([False, True], repeat=6))]
    rng = random.Random(18)
    batches = [games, games[:1], games[::-1], *(rng.sample(games, rng.randint(2, 20)) for _ in range(10))]
    batches += [[g] for g in games]
    for batch in batches:
        ids = [g.game_id for g in batch]
        for mode in MODES:
            result = mode(batch)
            assert [p.game_id for p in result.picks] == ids
            assert all(p.selection in ("home", "away", "over", "under") for p in result.picks)
            assert all("NO_BET" not in str(p.selection) for p in result.picks)


def test_p12_empty_list_returns_an_empty_set_and_duplicates_raise():
    for mode in MODES:
        assert len(mode([]).picks) == 0
        with pytest.raises(PicksError):
            mode([game(game_id="x"), game(game_id="y"), game(game_id="x")])


# ---- P13 make_picks ----------------------------------------------------------------------------


def test_p13_no_mode_is_straight_up_assumed_with_label():
    result = make_picks([game(p_home_win=0.3)])
    assert result.mode == "straight_up"
    assert result.mode_assumed is True
    assert result.label == ASSUMED_LABEL
    assert one(result).selection == "away"


@pytest.mark.parametrize(
    "mode, sample",
    [
        ("straight_up", game()),
        ("ats", ats_game(0.5, 0.4)),
        ("totals", total_game(0.5, 0.4)),
        ("confidence_pool", game()),
    ],
)
def test_p13_explicit_mode_is_not_flagged_and_dispatches(mode, sample):
    result = make_picks([sample], mode)
    assert result.mode == mode
    assert result.mode_assumed is False
    assert result.label != ASSUMED_LABEL
    assert all(p.mode == mode for p in result.picks)


def test_p13_options_pass_through_and_unknown_mode_raises():
    tied = game(p_home_win=0.5, p_away_win=0.5)
    assert one(make_picks([tied], "straight_up", tie_break="second")).selection == "away"
    for bad in ("bogus", "", "STRAIGHT_UP"):
        with pytest.raises(PicksError):
            make_picks([tied], bad)


def test_p13_direct_call_is_not_assumed_unless_told():
    assert pick_straight_up([game()]).mode_assumed is False
    assert pick_straight_up([game()], mode_assumed=True).mode_assumed is True


# ---- P14 pool weights --------------------------------------------------------------------------


def pool_games(homes):
    return [game(game_id=f"g{i}", p_home_win=h) for i, h in enumerate(homes)]


def test_p14_default_weights_are_one_to_n_unique():
    for n in (1, 2, 5, 16):
        picks = confidence_pool(pool_games([0.5 + 0.02 * i for i in range(n)])).picks
        assert sorted(p.weight for p in picks) == list(range(1, n + 1))


def test_p14_custom_weights_must_be_n_unique_positive_integers():
    games = pool_games([0.9, 0.7, 0.6])
    assert sorted(p.weight for p in confidence_pool(games, weights=[10, 20, 30]).picks) == [10, 20, 30]
    assert [p.weight for p in confidence_pool(games, weights=[30, 10, 20]).picks] == [30, 20, 10]
    for bad in ([1, 2], [1, 2, 3, 4], [1, 1, 2], [0, 1, 2], [-1, 1, 2], [1.5, 2, 3], [1, 2, None]):
        with pytest.raises(PicksError):
            confidence_pool(games, weights=bad)


# ---- P15 pool maximizes expected points --------------------------------------------------------


def shares_of(games, tie_rule="half"):
    out = []
    for g in games:
        t = g.p_tie / 2 if tie_rule == "half" else 0.0
        out.append(max(g.p_home_win + t, g.p_away_win + t))
    return out


def test_p15_worked_example_matches_brute_force_over_all_permutations():
    games = [
        game(game_id="a", p_home_win=0.62),
        game(game_id="b", p_home_win=0.25),  # away 0.75
        game(game_id="c", p_home_win=0.55),
        game(game_id="d", p_home_win=0.46, p_away_win=0.44, p_tie=0.10),  # share 0.51
        game(game_id="e", p_home_win=0.18),  # away 0.82
    ]
    result = confidence_pool(games)
    shares = shares_of(games)
    best = max(sum(w * s for w, s in zip(perm, shares, strict=True)) for perm in itertools.permutations(range(1, 6)))
    assert result.expected_points == pytest.approx(best)
    by_id = {p.game_id: p for p in result.picks}
    assert {k: v.weight for k, v in by_id.items()} == {"e": 5, "b": 4, "a": 3, "c": 2, "d": 1}
    assert sum(p.weight * p.probability for p in result.picks) == pytest.approx(result.expected_points)
    assert [by_id[k].selection for k in "abcde"] == ["home", "away", "home", "home", "away"]
    assert by_id["d"].probability == pytest.approx(0.51)


def test_p15_custom_weights_and_random_cases_are_optimal():
    rng = random.Random(15)
    for _ in range(25):
        n = rng.randint(2, 6)
        games = [game(game_id=f"g{i}", p_home_win=rng.uniform(0.05, 0.95)) for i in range(n)]
        weights = rng.sample(range(1, 40), n)
        result = confidence_pool(games, weights=weights)
        shares = shares_of(games)
        best = max(sum(w * s for w, s in zip(perm, shares, strict=True)) for perm in itertools.permutations(weights))
        assert result.expected_points == pytest.approx(best)
        assert sorted(p.weight for p in result.picks) == sorted(weights)


def test_p15_win_tie_rule_loss_uses_win_chance_alone():
    games = [game(game_id="a", p_home_win=0.46, p_away_win=0.44, p_tie=0.10)]
    assert confidence_pool(games).picks[0].probability == pytest.approx(0.51)
    assert confidence_pool(games, win_tie_rule="loss").picks[0].probability == pytest.approx(0.46)
    assert confidence_pool(games, win_tie_rule="loss").expected_points == pytest.approx(0.46)


# ---- P16 pool tie ordering ---------------------------------------------------------------------


def test_p16_equal_shares_ordered_by_game_id_or_input_order():
    games = [game(game_id=i, p_home_win=0.7) for i in ("b", "c", "a")]
    by_id = {p.game_id: p.weight for p in confidence_pool(games, tie_rule="game_id").picks}
    assert by_id == {"a": 3, "b": 2, "c": 1}
    by_input = {p.game_id: p.weight for p in confidence_pool(games, tie_rule="input_order").picks}
    assert by_input == {"b": 3, "c": 2, "a": 1}
    assert by_id != by_input
    assert {p.game_id: p.weight for p in confidence_pool(games).picks} == by_id  # default is game_id


def test_p16_ties_sit_inside_the_share_ordering_and_runs_are_identical():
    games = [game(game_id="z", p_home_win=0.9), game(game_id="b", p_home_win=0.6), game(game_id="a", p_home_win=0.6),
             game(game_id="c", p_home_win=0.3)]  # fmt: skip
    first = confidence_pool(games)
    weights = {p.game_id: p.weight for p in first.picks}
    assert weights["z"] == 4 and weights["c"] == 1 and (weights["a"], weights["b"]) == (3, 2)
    assert confidence_pool(games) == first
    assert confidence_pool(list(games)).picks == first.picks


# ---- P17 grading -------------------------------------------------------------------------------


def hpick(mode, selection, line=None) -> Pick:
    return Pick("g1", mode, selection, 0.5, 0.5, "model", line, ())


@pytest.mark.parametrize(
    "selection, home, away, result",
    [("home", 24, 21, "win"), ("home", 21, 24, "loss"), ("away", 21, 24, "win"), ("away", 24, 21, "loss"),
     ("home", 20, 20, "push"), ("away", 20, 20, "push")],
)  # fmt: skip
def test_p17_straight_up_grades_and_a_tie_is_a_push(selection, home, away, result):
    assert grade_pick(hpick("straight_up", selection), home, away) == result
    assert grade_pick(hpick("confidence_pool", selection), home, away) == result


@pytest.mark.parametrize(
    "selection, home, away, result",
    [("home", 24, 21, "push"), ("away", 24, 21, "push"), ("home", 25, 21, "win"), ("home", 23, 21, "loss"),
     ("away", 25, 21, "loss"), ("away", 23, 21, "win")],
)  # fmt: skip
def test_p17_spread_pushes_exactly_when_margin_plus_spread_is_zero(selection, home, away, result):
    assert grade_pick(hpick("ats", selection, -3.0), home, away) == result


@pytest.mark.parametrize(
    "selection, home, away, result",
    [("over", 24, 21, "push"), ("under", 24, 21, "push"), ("over", 24, 22, "win"), ("over", 24, 20, "loss"),
     ("under", 24, 22, "loss"), ("under", 24, 20, "win")],
)  # fmt: skip
def test_p17_total_pushes_exactly_when_the_sum_equals_the_line(selection, home, away, result):
    assert grade_pick(hpick("totals", selection, 45.0), home, away) == result


def test_p17_matches_settlement_module_on_random_scores():
    rng = random.Random(17)
    for _ in range(300):
        home, away = rng.randint(0, 45), rng.randint(0, 45)
        spread, line = rng.choice([-7.0, -3.5, -3.0, 0.0, 2.5, 6.0]), rng.choice([37.0, 44.5, 47.0])
        for sel in ("home", "away"):
            assert grade_pick(hpick("ats", sel, spread), home, away) == settle_spread(sel, spread, home, away)
            assert grade_pick(hpick("straight_up", sel), home, away) == settle_moneyline(sel, home, away)
        for sel in ("over", "under"):
            assert grade_pick(hpick("totals", sel, line), home, away) == settle_total(sel, line, home, away)


def test_p17_grades_picks_made_by_the_pick_functions_and_needs_a_line():
    spread_pick = one(pick_ats([ats_game(0.6, 0.3, spread=-3.0)]))
    assert grade_pick(spread_pick, 24, 21) == "push"
    assert grade_pick(one(pick_straight_up([game(p_home_win=0.8)])), 24, 21) == "win"
    for mode, sel in (("ats", "home"), ("totals", "over")):
        with pytest.raises(PicksError):
            grade_pick(hpick(mode, sel, None), 24, 21)


# ---- P18 points --------------------------------------------------------------------------------


def test_p18_points_for_win_loss_and_push_under_each_rule():
    assert pick_points("win") == 1.0 and pick_points("loss") == 0.0
    assert pick_points("push") == 0.0 and pick_points("push", "no_points") == 0.0
    assert pick_points("push", "half") == 0.5
    assert pick_points("win", "half") == 1.0 and pick_points("loss", "half") == 0.0


# ---- P19 spread sign ---------------------------------------------------------------------------


def test_p19_home_spread_is_the_negated_nflverse_line():
    assert home_spread_from_nflverse(-3.0) == 3.0
    assert home_spread_from_nflverse(3.5) == -3.5
    assert home_spread_from_nflverse(0.0) == 0.0
    assert home_spread_from_nflverse(-10) == 10.0
    assert math.isclose(home_spread_from_nflverse(-6.5), 6.5)


def test_p19_conversion_appears_only_inside_that_one_function():
    files = sorted((Path(nflpi.__file__).parent / "picks").glob("*.py"))
    assert files, "nflpi.picks has no source files"
    text = "\n".join(f.read_text() for f in files)
    assert len(re.findall(r"def home_spread_from_nflverse\b", text)) == 1
    function = re.compile(r"^def home_spread_from_nflverse\b.*?(?=^\S|\Z)", re.S | re.M)
    assert function.search(text) and "-spread_line" in function.search(text).group(0)
    rest = function.sub("", text)
    rest = "\n".join(line for line in rest.splitlines() if not line.lstrip().startswith("#"))
    assert "spread_line" not in rest
    assert not re.search(r"\*\s*-\s*1\b|\*\s*\(\s*-1\s*\)|\b-1\s*\*", rest)


# ---- P20..P24 betting advice -------------------------------------------------------------------


def test_p20_stale_or_future_price_is_no_bet_even_with_big_value():
    stale = advice(0.5, at=NOW - MAX_AGE - timedelta(seconds=1), rubric=VALID)
    future = advice(0.5, at=NOW + timedelta(seconds=1), rubric=VALID)
    for result in (stale, future):
        assert result.status == "NO_BET" and "STALE_PRICE" in result.reasons
        assert result.stars is None


def test_p20_price_exactly_max_age_old_is_still_fresh():
    result = advice(0.5, at=NOW - MAX_AGE, rubric=VALID)
    assert result.status == "RATED" and "STALE_PRICE" not in result.reasons
    assert advice(0.5, at=NOW).status == "UNRATED"  # observed exactly now is not the future


def test_p20_nonpositive_expected_value_is_no_bet_at_and_below_zero():
    for ev in (0.0, -0.2, -1.0):
        result = advice(ev, rubric=VALID)
        assert result.status == "NO_BET" and "NONPOSITIVE_EV" in result.reasons
        assert result.expected_value == pytest.approx(ev)
    assert advice(1 / 64).status == "UNRATED"  # just above zero is no longer a no-bet
    assert advice(1 / 64).expected_value == pytest.approx(1 / 64)


def test_p20_no_bet_reasons_win_over_every_other_reason():
    both = advice(-0.2, at=NOW - MAX_AGE * 2, rubric=VALID, qb_missing=True)
    assert both.status == "NO_BET" and {"STALE_PRICE", "NONPOSITIVE_EV"} <= set(both.reasons)
    stale_qb = advice(0.5, at=NOW - MAX_AGE * 2, rubric=VALID, qb_missing=True)
    assert stale_qb.status == "NO_BET" and "STALE_PRICE" in stale_qb.reasons
    flat_qb = advice(0.0, rubric=VALID, qb_missing=True)
    assert flat_qb.status == "NO_BET" and "NONPOSITIVE_EV" in flat_qb.reasons
    assert both.stars is None and stale_qb.stars is None and flat_qb.stars is None


def test_p21_positive_value_without_a_validated_rubric_is_unrated():
    unvalidated = Rubric(THRESHOLDS)
    assert unvalidated.validated is False and unvalidated.provisional is True
    for rubric in (None, unvalidated, Rubric(THRESHOLDS, validated=False, provisional=False)):
        result = advice(0.5, rubric=rubric)
        assert result.status == "UNRATED"
        assert "NO_VALIDATION_HISTORY" in result.reasons
        assert result.stars is None
        assert result.expected_value == pytest.approx(0.5)


@pytest.mark.parametrize(
    "ev_64ths, stars",
    [(1, None), (3, None), (4, 1), (5, 1), (7, 1), (8, 2), (9, 2), (11, 2), (12, 3), (15, 3), (16, 4), (19, 4),
     (20, 5), (21, 5), (64, 5)],
)  # fmt: skip
def test_p22_stars_count_thresholds_reached_with_equality_counting(ev_64ths, stars):
    result = advice(ev_64ths / 64, rubric=VALID)
    if stars is None:
        assert result.status == "UNRATED" and "BELOW_FIRST_THRESHOLD" in result.reasons
        assert not result.stars
    else:
        assert result.status == "RATED" and result.stars == stars
        assert "BELOW_FIRST_THRESHOLD" not in result.reasons


def test_p22_provisional_follows_the_rubric():
    assert advice(0.25, rubric=Rubric(THRESHOLDS, validated=True, provisional=True)).provisional is True
    assert advice(0.25, rubric=Rubric(THRESHOLDS, validated=True, provisional=False)).provisional is False
    assert advice(0.25, rubric=Rubric(THRESHOLDS, validated=True)).provisional is True  # default


def test_p23_missing_qb_with_positive_value_is_never_rated():
    result = advice(0.9, rubric=VALID, qb_missing=True)
    assert result.status == "UNRATED" and "QB_MISSING" in result.reasons
    assert result.stars is None
    assert advice(0.9, rubric=VALID).status == "RATED"
    assert advice(0.9, qb_missing=True).status == "UNRATED"  # no rubric either


@pytest.mark.parametrize(
    "thresholds",
    [(0.1, 0.2, 0.3, 0.4), (0.1, 0.2, 0.3, 0.4, 0.5, 0.6), (), (0.0, 0.1, 0.2, 0.3, 0.4), (-0.1, 0.1, 0.2, 0.3, 0.4),
     (0.1, 0.2, 0.2, 0.4, 0.5), (0.1, 0.3, 0.2, 0.4, 0.5), (0.5, 0.4, 0.3, 0.2, 0.1), (0.1, 0.2, NAN, 0.4, 0.5),
     (0.1, 0.2, 0.3, 0.4, INF)],
)  # fmt: skip
def test_p24_rubric_rejects_bad_thresholds(thresholds):
    with pytest.raises(PicksError):
        Rubric(thresholds, validated=True)


def test_p24_rubric_accepts_five_increasing_positive_finite_thresholds():
    assert Rubric((0.001, 0.002, 0.003, 0.004, 0.005)).ev_thresholds == (0.001, 0.002, 0.003, 0.004, 0.005)
    assert Rubric(THRESHOLDS, validated=True).validated is True
    with pytest.raises(AttributeError):
        Rubric(THRESHOLDS).validated = True  # type: ignore[misc]


# ---- P25 advice cannot change picks ------------------------------------------------------------


def test_p25_picks_are_identical_whatever_advice_says():
    games = [game(game_id="a", p_home_win=0.7, qb_missing=True), ats_game(0.5, 0.4, game_id="b"), game(game_id="c")]
    outcomes = [
        dict(ev=0.5, at=NOW - MAX_AGE * 2),  # NO_BET stale
        dict(ev=-0.3),  # NO_BET nonpositive
        dict(ev=0.2),  # UNRATED
        dict(ev=0.25, rubric=VALID),  # RATED
        dict(ev=0.9, rubric=VALID, qb_missing=True),  # UNRATED, qb
    ]
    for mode in (None, "straight_up", "ats", "totals", "confidence_pool"):
        before = make_picks(games, mode)
        statuses = []
        for outcome in outcomes:
            statuses.append(advice(**outcome).status)
            after = make_picks(games, mode)
            assert after == before
            assert len(after.picks) == len(games)
        assert statuses == ["NO_BET", "NO_BET", "UNRATED", "RATED", "UNRATED"]


def test_p25_no_bet_leaves_one_pick_per_game_and_the_two_sides_share_no_parameters():
    games = [game(game_id=f"g{i}", p_home_win=0.4 + 0.05 * i) for i in range(6)]
    assert advice(-0.5).status == "NO_BET"
    for mode in MODES:
        assert len(mode(games).picks) == len(games)
    advice_params = set(inspect.signature(betting_advice).parameters)
    picks_params = set(inspect.signature(make_picks).parameters)
    assert not advice_params & {"pick", "picks", "pick_set", "games"}
    assert not picks_params & {"advice", "snapshot", "probs", "rubric", "now", "max_age"}
    assert {"snapshot", "probs", "now", "max_age"} <= advice_params


def test_p25_pick_results_are_frozen_values():
    result = make_picks([game()])
    with pytest.raises(AttributeError):
        one(result).selection = "away"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.mode = "ats"  # type: ignore[misc]
