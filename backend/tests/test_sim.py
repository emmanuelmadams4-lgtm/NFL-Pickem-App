"""Game-score simulator: frozen clauses C1 to C15 of docs/gauntlet/logs/step-18c.md section 2.7."""

import dataclasses
import time

import numpy as np
import pytest

import nflpi.sim.game as game_module
from nflpi.sim import (
    DEFAULT_DISTRIBUTION,
    DISTRIBUTIONS,
    SimParams,
    TeamFeatures,
    learn_params,
    ot_era,
    regulation_scores,
    simulate_game,
)
from nflpi.sim.distributions import sample_regulation
from nflpi.sim.overtime import resolve_overtime

A, B = TeamFeatures(24.0), TeamFeatures(20.0)


def make_params(**override) -> SimParams:
    rng = np.random.default_rng(3)
    shared = rng.normal(0, 6, 4000)
    base = {
        "residual_a": np.round(shared + rng.normal(0, 6, 4000)).astype(int),
        "residual_b": np.round(0.5 * shared + rng.normal(0, 7, 4000)).astype(int),
        "phi_a": 4.0, "phi_b": 4.5, "rho": 0.2, "v": 0.12, "v_shared": 0.03,
        "ot_tie_frac": 0.1, "ot_increments": np.array([3, 3, 6, 7]),
        "ot_era": "modified_10", "ot_era_fallback": False, "n_train": 4000,
    }
    base.update(override)
    return SimParams(**base)


def planted(n: int, v: float, v_shared: float, seed: int = 1):
    """Synthetic regulation scores drawn from the shared-gamma Poisson with known v and v_shared."""
    rng = np.random.default_rng(seed)
    mu_a, mu_b = rng.uniform(17, 28, n), rng.uniform(17, 28, n)
    k_s = v_shared / v**2
    k_e = 1 / v - k_s
    s = rng.gamma(k_s, size=n)
    ga = (s + rng.gamma(k_e, size=n)) / (k_s + k_e)
    gb = (s + rng.gamma(k_e, size=n)) / (k_s + k_e)
    return mu_a, mu_b, rng.poisson(mu_a * ga), rng.poisson(mu_b * gb)


def with_overtime(n_ot: int, tie_frac: float, seasons_ot: np.ndarray, seed: int = 2):
    rng = np.random.default_rng(seed)
    base = rng.integers(14, 28, n_ot)
    inc = rng.choice([3, 3, 6, 7], n_ot)
    a, b = base.copy(), base.copy()
    tied = np.arange(n_ot) < round(tie_frac * n_ot)
    a_wins = rng.random(n_ot) < 0.5
    a = np.where(~tied & a_wins, a + inc, a)
    b = np.where(~tied & ~a_wins, b + inc, b)
    return a, b, seasons_ot


def patched(monkeypatch, a, b):
    monkeypatch.setattr(game_module, "sample_regulation",
                        lambda *args, **kwargs: (np.asarray(a, dtype=np.int64), np.asarray(b, dtype=np.int64)))


# --- C1 output validity ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", DISTRIBUTIONS)
def test_scores_are_nonnegative_integers_and_probabilities_sum_to_one(name):
    r = simulate_game(A, B, 5000, params=make_params(), seed=1, spread=-3.0, total=44.0, distribution=name)
    assert r.a_score.dtype == np.int64 and r.b_score.dtype == np.int64
    assert r.a_score.shape == r.b_score.shape == (5000,) and r.n == 5000
    assert r.a_score.min() >= 0 and r.b_score.min() >= 0
    assert r.p_a_win + r.p_b_win + r.p_tie == pytest.approx(1.0)
    assert r.p_a_cover + r.p_b_cover + r.p_spread_push == pytest.approx(1.0)
    assert r.p_over + r.p_under + r.p_total_push == pytest.approx(1.0)
    assert r.expected_margin == pytest.approx((r.a_score - r.b_score).mean())
    assert r.expected_total == pytest.approx((r.a_score + r.b_score).mean())


def test_spread_and_total_probabilities_are_absent_when_not_asked_for():
    r = simulate_game(A, B, 1000, distribution="poisson", seed=1)
    assert r.p_a_cover is r.p_b_cover is r.p_spread_push is None
    assert r.p_over is r.p_under is r.p_total_push is None


def test_default_distribution_is_one_of_the_distributions():
    assert DEFAULT_DISTRIBUTION in DISTRIBUTIONS
    assert DISTRIBUTIONS[0] == "poisson" and len(DISTRIBUTIONS) >= 3


# --- C2 / C3 conventions ----------------------------------------------------------------------------

def test_spread_convention_covers_when_margin_plus_spread_is_positive(monkeypatch):
    patched(monkeypatch, [10, 10, 10, 10], [7, 6, 13, 10])  # margins 3, 4, -3, 0 (tie stays tied)
    p = make_params(ot_tie_frac=1.0)
    r = simulate_game(A, B, 4, params=p, seed=1, spread=-3.0, distribution="poisson")
    assert (r.p_a_cover, r.p_spread_push, r.p_b_cover) == (0.25, 0.25, 0.5)


def test_half_point_spread_never_pushes_and_zero_spread_pushes_on_a_tie(monkeypatch):
    patched(monkeypatch, [10, 10, 10, 10], [7, 6, 13, 10])
    p = make_params(ot_tie_frac=1.0)
    half = simulate_game(A, B, 4, params=p, seed=1, spread=-3.5, distribution="poisson")
    assert half.p_spread_push == 0.0 and half.p_a_cover == 0.25
    zero = simulate_game(A, B, 4, params=p, seed=1, spread=0.0, distribution="poisson")
    assert (zero.p_a_cover, zero.p_spread_push, zero.p_b_cover) == (0.5, 0.25, 0.25)


def test_total_convention_over_is_strictly_greater(monkeypatch):
    patched(monkeypatch, [10, 10, 10, 10], [7, 6, 13, 10])  # totals 17, 16, 23, 20
    p = make_params(ot_tie_frac=1.0)
    r = simulate_game(A, B, 4, params=p, seed=1, total=17.0, distribution="poisson")
    assert (r.p_over, r.p_total_push, r.p_under) == (0.5, 0.25, 0.25)


# --- C4 reproducibility -----------------------------------------------------------------------------

@pytest.mark.parametrize("name", DISTRIBUTIONS)
def test_same_seed_same_output_and_other_seed_differs(name):
    p = make_params()
    one = simulate_game(A, B, 2000, params=p, seed=11, distribution=name)
    two = simulate_game(A, B, 2000, params=p, seed=11, distribution=name)
    other = simulate_game(A, B, 2000, params=p, seed=12, distribution=name)
    assert np.array_equal(one.a_score, two.a_score) and np.array_equal(one.b_score, two.b_score)
    assert not np.array_equal(one.a_score, other.a_score)


# --- C5 speed ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", DISTRIBUTIONS)
def test_ten_thousand_simulations_take_well_under_100_ms(name):
    p = make_params()
    simulate_game(A, B, params=p, seed=0, distribution=name, spread=-3.5, total=44.5)  # warm up
    times = []
    for i in range(20):
        start = time.perf_counter()
        simulate_game(A, B, 10_000, params=p, seed=i, distribution=name, spread=-3.5, total=44.5)
        times.append(time.perf_counter() - start)
    assert np.median(times) < 0.1


# --- C6 distribution moments ------------------------------------------------------------------------

N = 200_000


def _rng():
    return np.random.default_rng(5)


def test_poisson_mean_and_variance_equal_the_expected_points():
    a, b = sample_regulation("poisson", 24.0, 20.0, N, _rng(), None)
    assert a.mean() == pytest.approx(24.0, abs=4 * np.sqrt(24 / N))
    assert b.var() == pytest.approx(20.0, rel=0.03)
    assert abs(np.corrcoef(a, b)[0, 1]) < 0.01


def test_paired_residual_mean_matches_the_pool_and_keeps_its_correlation():
    p = make_params()
    a, b = sample_regulation("paired_residual", 30.0, 26.5, N, _rng(), p)
    for scores, mu, pool in ((a, 30.0, p.residual_a), (b, 26.5, p.residual_b)):
        lo, frac = int(np.floor(mu)), mu - np.floor(mu)
        expected = (1 - frac) * np.maximum(0, lo + pool).mean() + frac * np.maximum(0, lo + 1 + pool).mean()
        assert scores.mean() == pytest.approx(expected, abs=4 * scores.std() / np.sqrt(N))
    assert np.corrcoef(a, b)[0, 1] == pytest.approx(np.corrcoef(p.residual_a, p.residual_b)[0, 1], abs=0.02)


def test_bivariate_normal_variance_and_correlation_follow_the_learned_values():
    p = make_params(phi_a=4.0, phi_b=4.5, rho=0.2)
    a, b = sample_regulation("bivariate_normal", 28.0, 24.0, N, _rng(), p)
    assert a.var() == pytest.approx(4.0 * 28.0, rel=0.03)
    assert b.var() == pytest.approx(4.5 * 24.0, rel=0.03)
    assert np.corrcoef(a, b)[0, 1] == pytest.approx(0.2, abs=0.02)


def test_shared_gamma_poisson_has_the_learned_overdispersion_and_correlation():
    p = make_params(v=0.12, v_shared=0.03)
    a, b = sample_regulation("shared_gamma_poisson", 24.0, 20.0, N, _rng(), p)
    assert a.var() == pytest.approx(24.0 + 0.12 * 24.0**2, rel=0.03)
    assert a.mean() == pytest.approx(24.0, abs=4 * a.std() / np.sqrt(N))
    cov = 0.03 * 24.0 * 20.0
    assert np.corrcoef(a, b)[0, 1] == pytest.approx(cov / (a.std() * b.std()), abs=0.01)


# --- C7 learning ------------------------------------------------------------------------------------

def _training(n=40_000, v=0.12, v_shared=0.03):
    mu_a, mu_b, sa, sb = planted(n, v, v_shared)
    seasons = np.full(n, 2008)
    oa, ob, os_ = with_overtime(300, 0.1, np.full(300, 2008))
    return (np.r_[mu_a, np.full(300, 20.0)], np.r_[mu_b, np.full(300, 20.0)], np.r_[sa, oa], np.r_[sb, ob],
            np.r_[np.zeros(n, int), np.ones(300, int)], np.r_[seasons, os_])


def test_learn_params_recovers_planted_dispersion_correlation_and_overtime():
    mu_a, mu_b, sa, sb, ot, seasons = _training()
    p = learn_params(mu_a, mu_b, sa, sb, ot, seasons, target_season=2009)
    assert p.v == pytest.approx(0.12, abs=0.015)
    assert p.v_shared == pytest.approx(0.03, abs=0.01)
    assert p.phi_a == pytest.approx(1 + 0.12 * mu_a.mean(), rel=0.1)
    assert p.ot_tie_frac == pytest.approx(0.1)
    assert set(np.unique(p.ot_increments)) <= {3, 6, 7} and len(p.ot_increments) == 270
    assert p.n_train == len(mu_a)


def test_learn_params_is_invariant_to_row_order():
    cols = _training(n=3000)
    order = np.random.default_rng(9).permutation(len(cols[0]))
    one = learn_params(*cols, target_season=2009)
    two = learn_params(*(c[order] for c in cols), target_season=2009)
    for field in dataclasses.fields(SimParams):
        x, y = getattr(one, field.name), getattr(two, field.name)
        np.testing.assert_allclose(x, y, rtol=1e-12, err_msg=field.name)


def test_learn_params_refuses_too_few_games_or_no_overtime():
    cols = _training(n=100)
    with pytest.raises(ValueError, match="200"):
        learn_params(*(c[:150] for c in cols), target_season=2009)
    mu_a, mu_b, sa, sb, ot, seasons = _training(n=3000)
    with pytest.raises(ValueError, match="overtime"):
        learn_params(mu_a, mu_b, sa, sb, np.zeros_like(ot), seasons, target_season=2009)


# --- C8 overtime and ties ---------------------------------------------------------------------------

def test_playoff_games_never_end_tied_even_when_regular_season_ties_are_likely():
    reg = np.full(20_000, 17, dtype=np.int64)
    a, b = resolve_overtime(reg, reg.copy(), np.random.default_rng(1), make_params(ot_tie_frac=0.9), playoff=True)
    assert (a != b).all()


def test_zero_tie_probability_never_ties_and_adds_a_pool_increment_to_one_side():
    reg = np.full(20_000, 17, dtype=np.int64)
    p = make_params(ot_tie_frac=0.0, ot_increments=np.array([3, 6, 7]))
    a, b = resolve_overtime(reg, reg.copy(), np.random.default_rng(1), p, playoff=False)
    diff = np.abs(a - b)
    assert set(np.unique(diff)) == {3, 6, 7} and np.minimum(a, b).min() == 17
    assert (a > b).mean() == pytest.approx(0.5, abs=0.02)


def test_regulation_ties_stay_tied_at_the_learned_rate_and_other_games_are_untouched():
    a0 = np.array([17] * 20_000 + [20, 10], dtype=np.int64)
    b0 = np.array([17] * 20_000 + [13, 24], dtype=np.int64)
    a, b = resolve_overtime(a0, b0, np.random.default_rng(2), make_params(ot_tie_frac=0.1), playoff=False)
    assert (a[:20_000] == b[:20_000]).mean() == pytest.approx(0.1, abs=0.01)
    assert (a[-2:] == a0[-2:]).all() and (b[-2:] == b0[-2:]).all()


def test_playoff_flag_reaches_simulate_game():
    r = simulate_game(A, B, 20_000, params=make_params(ot_tie_frac=0.9), seed=3, distribution="poisson", playoff=True)
    assert r.p_tie == 0.0


# --- C9 eras ----------------------------------------------------------------------------------------

def test_overtime_eras_follow_the_rule_changes():
    assert [ot_era(s) for s in (2002, 2011, 2012, 2016, 2017, 2025)] == [
        "sudden_death_15", "sudden_death_15", "modified_15", "modified_15", "modified_10", "modified_10"]


def _era_training():
    """200 games of 2012 to 2016 overtime with no ties, 60 of 2017 to 2021 with 20% ties."""
    n = 3000
    mu_a, mu_b, sa, sb = planted(n, 0.12, 0.03)
    seasons = np.full(n, 2014)
    parts = [with_overtime(200, 0.0, np.full(200, 2014), 5), with_overtime(60, 0.2, np.full(60, 2019), 6)]
    oa, ob, os_ = (np.concatenate([p[i] for p in parts]) for i in range(3))
    mu = np.full(len(oa), 20.0)
    return (np.r_[mu_a, mu], np.r_[mu_b, mu], np.r_[sa, oa], np.r_[sb, ob],
            np.r_[np.zeros(n, int), np.ones(len(oa), int)], np.r_[seasons, os_])


def test_overtime_rates_come_from_the_same_era_when_there_are_enough_games():
    p = learn_params(*_era_training(), target_season=2022)
    assert p.ot_era == "modified_10" and not p.ot_era_fallback
    assert p.ot_tie_frac == pytest.approx(0.2) and len(p.ot_increments) == 48


def test_overtime_falls_back_to_all_training_games_when_the_era_has_under_30():
    cols = _era_training()
    p = learn_params(*cols, target_season=2017)  # 60 modified_10 games exist ...
    assert p.ot_era == "modified_10" and not p.ot_era_fallback
    few = tuple(c[:-40] for c in cols)  # ... and only 20 of them once 40 rows are cut
    q = learn_params(*few, target_season=2022)
    assert q.ot_era_fallback and q.ot_era == "modified_10"
    assert q.ot_tie_frac == pytest.approx(12 / 220)  # all 12 ties survive the cut, none in the 2014 games


# --- C10 intervals ----------------------------------------------------------------------------------

@pytest.mark.parametrize("name", DISTRIBUTIONS)
def test_predictive_intervals_are_nested_hold_their_level_and_contain_the_median(name):
    r = simulate_game(A, B, 10_000, params=make_params(), seed=4, distribution=name)
    for samples, intervals in ((r.a_score - r.b_score, r.margin_intervals), (r.a_score + r.b_score, r.total_intervals)):
        assert set(intervals) == {0.5, 0.8, 0.95}
        med = np.median(samples)
        for level, (lo, hi) in intervals.items():
            assert lo <= med <= hi
            assert ((samples >= lo) & (samples <= hi)).mean() >= level - 1e-9
        assert intervals[0.5][0] >= intervals[0.8][0] >= intervals[0.95][0]
        assert intervals[0.5][1] <= intervals[0.8][1] <= intervals[0.95][1]


# --- C11 sampling error -----------------------------------------------------------------------------

def test_sampling_error_is_binomial_and_labelled_as_sampling_error_only():
    r = simulate_game(A, B, 10_000, params=make_params(), seed=4, distribution="poisson", spread=-3.5, total=44.5)
    se = r.sampling_error
    assert se["p_a_win"] == pytest.approx(np.sqrt(r.p_a_win * (1 - r.p_a_win) / 10_000))
    assert se["p_over"] == pytest.approx(np.sqrt(r.p_over * (1 - r.p_over) / 10_000))
    assert se["expected_margin"] == pytest.approx((r.a_score - r.b_score).std() / np.sqrt(10_000))
    label = se["label"].lower()
    assert "sampling error only" in label and "not" in label and "uncertainty" in label


# --- C12 validation ---------------------------------------------------------------------------------

@pytest.mark.parametrize("n", [0, -5, 2.5, True, 10_000_001])
def test_bad_simulation_counts_are_rejected(n):
    with pytest.raises(ValueError, match="n_simulations"):
        simulate_game(A, B, n, distribution="poisson")


@pytest.mark.parametrize("points", [float("nan"), float("inf"), 0.0, -3.0, 100.5])
def test_bad_expected_points_are_rejected(points):
    with pytest.raises(ValueError, match="expected_points"):
        TeamFeatures(points)


def test_unknown_distribution_and_missing_params_and_bad_lines_are_rejected():
    with pytest.raises(ValueError, match="distribution"):
        simulate_game(A, B, 100, distribution="bogus")
    for name in DISTRIBUTIONS[1:]:
        with pytest.raises(ValueError, match="params"):
            simulate_game(A, B, 100, distribution=name)
    for kwargs in ({"spread": float("nan")}, {"total": float("inf")}, {"total": -1.0}):
        with pytest.raises(ValueError):
            simulate_game(A, B, 100, distribution="poisson", **kwargs)


def test_poisson_baseline_runs_without_learned_parameters():
    r = simulate_game(A, B, 1000, seed=1, distribution="poisson")
    assert r.distribution == "poisson"


# --- C13 neutral site -------------------------------------------------------------------------------

def test_neutral_site_is_recorded_and_does_not_change_the_samples():
    p = make_params()
    home = simulate_game(A, B, 1000, params=p, seed=8, distribution="poisson", neutral_site=False)
    neutral = simulate_game(A, B, 1000, params=p, seed=8, distribution="poisson", neutral_site=True)
    assert neutral.neutral_site and not home.neutral_site
    assert np.array_equal(home.a_score, neutral.a_score)


# --- C14 / C15 --------------------------------------------------------------------------------------

def test_team_features_are_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        A.expected_points = 3.0  # type: ignore[misc]


def test_regulation_score_of_an_overtime_game_is_the_loser_s_score():
    a = np.array([23, 20, 17, 30])
    b = np.array([20, 20, 24, 27])
    ot = np.array([1, 1, 1, 0])
    reg_a, reg_b = regulation_scores(a, b, ot)
    assert reg_a.tolist() == [20, 20, 17, 30] and reg_b.tolist() == [20, 20, 17, 27]
