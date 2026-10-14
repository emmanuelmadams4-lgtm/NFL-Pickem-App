"""Simulator bench: frozen clauses B1 to B9 of docs/gauntlet/logs/step-18c.md section 2.7."""

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nflpi.analytics import sim_backtest as bench
from nflpi.sim import DEFAULT_DISTRIBUTION, DISTRIBUTIONS, SimParams

TEAMS = [f"T{i:02d}" for i in range(32)]


def synthetic_rows(first: int = 2003, last: int = 2024, seed: int = 1) -> list[dict[str, str]]:
    """nflverse-shaped schedule rows with made-up teams, scores, lines and overtime."""
    rng = np.random.default_rng(seed)
    strength = rng.normal(0, 3, 32)
    rows = []
    for season in range(first, last + 1):
        start = date(season, 9, 7)
        for week in range(1, 18):
            order = rng.permutation(32)
            for k in range(16):
                h, a = int(order[2 * k]), int(order[2 * k + 1])
                mu_h = 22 + 0.4 * (strength[h] - strength[a]) + 1.0
                mu_a = 22 - 0.4 * (strength[h] - strength[a]) - 1.0
                hs, as_ = int(rng.poisson(mu_h)), int(rng.poisson(mu_a))
                overtime = 0
                if hs == as_:
                    overtime = 1
                    if rng.random() < 0.9:
                        if rng.random() < 0.5:
                            hs += 3
                        else:
                            as_ += 3
                day = start + timedelta(days=7 * (week - 1))
                rows.append({
                    "game_id": f"{season}_{week:02d}_{TEAMS[a]}_{TEAMS[h]}", "season": str(season), "week": str(week),
                    "game_type": "REG", "gameday": day.isoformat(), "gametime": "13:00", "weekday": "Sunday",
                    "away_team": TEAMS[a], "home_team": TEAMS[h], "away_score": str(as_), "home_score": str(hs),
                    "location": "Home", "div_game": "0", "roof": "outdoors", "surface": "grass", "stadium": "S",
                    "stadium_id": "S1", "away_rest": "7", "home_rest": "7", "away_qb_name": "", "home_qb_name": "",
                    "away_coach": "", "home_coach": "", "temp": "", "wind": "",
                    "home_moneyline": "-150", "away_moneyline": "130",
                    "spread_line": str(round((mu_h - mu_a) * 2) / 2), "total_line": str(round(mu_h + mu_a)),
                    "overtime": str(overtime),
                })
    return rows


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    return bench.build_table(bench.load_games(synthetic_rows()))


def scrambled_from(frame: pd.DataFrame, season: int) -> pd.DataFrame:
    """Results and expected points of every game from `season` on, shuffled among those games."""
    out = frame.copy()
    later = out["season"] >= season
    perm = np.random.default_rng(0).permutation(int(later.sum()))
    for column in ("home_score", "away_score", "fb_home", "fb_away", "mk_home", "mk_away", "overtime"):
        out.loc[later, column] = out.loc[later, column].to_numpy()[perm]
    return out


# --- B1 CRPS and the default rule ----------------------------------------------------------------

def test_sample_crps_matches_hand_computed_values():
    assert bench.crps(np.array([0, 2]), 1.0) == pytest.approx(0.5)
    assert bench.crps(np.array([5] * 10), 5.0) == pytest.approx(0.0)
    assert bench.crps(np.array([0, 0, 4, 4]), 0.0) == pytest.approx(1.0)


def test_default_is_the_lowest_pooled_score_and_ties_go_to_the_earlier_distribution():
    assert bench.pick_default({"poisson": 3.0, "paired_residual": 2.0, "bivariate_normal": 2.5,
                               "shared_gamma_poisson": 4.0}) == "paired_residual"
    assert bench.pick_default({"poisson": 2.0, "paired_residual": 2.0, "bivariate_normal": 2.0,
                               "shared_gamma_poisson": 2.0}) == DISTRIBUTIONS[0]


# --- B2 the tune run never reads the confirm seasons -----------------------------------------------

def test_tune_gives_the_same_answer_without_or_with_scrambled_confirm_seasons(table):
    kwargs = {"seasons": [2020, 2021], "n_simulations": 300}
    full = bench.tune(table, **kwargs)
    removed = bench.tune(table[table["season"] < 2022], **kwargs)
    scrambled = bench.tune(scrambled_from(table, 2022), **kwargs)
    assert full == removed == scrambled
    assert full["default"] in DISTRIBUTIONS
    assert set(full["pooled_crps"]) == set(DISTRIBUTIONS)


def test_tune_refuses_confirm_seasons(table):
    with pytest.raises(ValueError, match="confirm"):
        bench.tune(table, seasons=[2021, 2022], n_simulations=100)


def test_expected_points_for_tuning_seasons_do_not_use_later_results():
    rows = synthetic_rows()
    clean = bench.build_table(bench.load_games(rows))
    broken_rows = [dict(r) for r in rows]
    rng = np.random.default_rng(1)
    for r in broken_rows:
        if int(r["season"]) >= 2022:
            r["home_score"], r["away_score"] = str(int(rng.integers(0, 50))), str(int(rng.integers(0, 50)))
            r["overtime"] = "0"
    broken = bench.build_table(bench.load_games(broken_rows))
    cols = ["game_id", "fb_home", "fb_away", "mk_home", "mk_away"]
    before = lambda t: t[t["season"] < 2022][cols].reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(before(clean), before(broken))


# --- B3 walk-forward parameters --------------------------------------------------------------------

def test_parameters_for_a_season_use_only_the_ten_seasons_before_it(table):
    season = 2015
    params = bench.learn_for_season(table, season, "football_only")
    assert isinstance(params, SimParams)
    window = table[(table["season"] >= season - 10) & (table["season"] <= season - 1)]
    assert params.n_train == len(window)
    changed = bench.learn_for_season(scrambled_from(table, season), season, "football_only")
    for field in ("residual_a", "residual_b", "phi_a", "phi_b", "rho", "v", "v_shared", "ot_tie_frac",
                  "ot_increments", "n_train"):
        np.testing.assert_array_equal(getattr(params, field), getattr(changed, field), err_msg=field)


def test_the_training_window_starts_no_earlier_than_2004(table):
    params = bench.learn_for_season(table, 2008, "market_informed")
    assert params.n_train == len(table[(table["season"] >= 2004) & (table["season"] <= 2007)])


# --- B4 / B5 identical games, one code path ----------------------------------------------------------

def test_every_variant_scores_the_same_games_and_the_bench_calls_simulate_game_once_each(table, monkeypatch):
    calls = []
    real = bench.simulate_game

    def spy(*args, **kwargs):
        calls.append(kwargs.get("distribution"))
        return real(*args, **kwargs)

    monkeypatch.setattr(bench, "simulate_game", spy)
    rows = bench.simulate_table(table, [2015], n_simulations=200)
    games = table[table["season"] == 2015]
    assert len(calls) == len(games) * len(DISTRIBUTIONS) * len(bench.SOURCES)
    ids = {key: set(group["game_id"]) for key, group in rows.groupby(["source", "distribution"])}
    assert len(ids) == len(DISTRIBUTIONS) * len(bench.SOURCES)
    assert all(v == set(games["game_id"]) for v in ids.values())


def test_eligible_games_are_regular_season_finals_with_lines_and_finite_expected_points(table):
    assert not table[["fb_home", "fb_away", "mk_home", "mk_away", "spread_line", "total_line"]].isna().any().any()
    assert (table["game_type"] == "REG").all() and table["season"].min() >= 2004
    assert table["game_id"].is_unique


# --- B6 spread sign -----------------------------------------------------------------------------------

def test_bench_spread_is_the_negative_of_the_nflverse_line():
    assert bench.home_spread_from_nflverse(3.0) == -3.0  # home favoured by 3: home covers when margin - 3 > 0
    assert bench.home_spread_from_nflverse(-2.5) == 2.5
    margin, line = 7, 3.0
    assert margin + bench.home_spread_from_nflverse(line) > 0


def test_bench_uses_the_one_data_layer_spread_conversion():
    # AUDIT A13, step 18h: one named conversion, nflpi.data.asof.home_spread_from_nflverse; the bench negates nothing.
    import inspect
    import re

    from nflpi.data import asof

    assert bench.home_spread_from_nflverse is asof.home_spread_from_nflverse
    assert not hasattr(bench, "quoted_home_spread")
    src = inspect.getsource(bench)
    assert not re.search(r"-\s*\w+\[\"spread_line\"\]|-\s*spread_line|-\s*\w+\.spread_line", src)
    assert "home_spread_from_nflverse(" in inspect.getsource(bench._variant)
    assert "home_spread_from_nflverse(" in inspect.getsource(bench._game_row)


# --- B7 metric helpers --------------------------------------------------------------------------------

def test_reliability_table_brier_and_flat_brier():
    p = np.array([0.05, 0.05, 0.95, 0.95])
    y = np.array([0, 1, 1, 1])
    rows = bench.reliability_table(p, y, bins=10)
    assert [r["n"] for r in rows] == [2, 2]
    assert rows[0]["mean_pred"] == pytest.approx(0.05) and rows[0]["observed"] == pytest.approx(0.5)
    assert rows[1]["observed"] == pytest.approx(1.0)
    brier, flat = bench.brier_vs_flat(p, y)
    assert brier == pytest.approx(np.mean((p - y) ** 2)) and flat == pytest.approx(0.25)


def test_key_number_rate_and_win_gap_and_interval_coverage():
    assert bench.key_number_rate(np.array([3, -3, 7, 0, 10]), 3) == pytest.approx(0.4)
    gap = bench.win_gap(np.array([0.6, 0.5, 0.9]), np.array([0.5, 0.5, 0.6]))
    assert gap["mean_abs"] == pytest.approx((0.1 + 0 + 0.3) / 3)
    assert gap["max_abs"] == pytest.approx(0.3) and gap["n_above_0.10"] == 1
    assert bench.interval_coverage(np.array([1, 0, 1, 1])) == pytest.approx(0.75)


# --- B8 / B9 confirm: once, and complete -------------------------------------------------------------

def blend_for(table: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    p = 1 / (1 + np.exp(-(table["fb_home"] - table["fb_away"]) / 6))
    return pd.DataFrame({"game_id": table["game_id"], "p_blend": np.clip(p + rng.normal(0, 0.02, len(p)), 0.02, 0.98),
                         "p_market": np.clip(p, 0.02, 0.98)})


def test_confirm_needs_the_tune_record_and_runs_only_once(table, tmp_path):
    tune_path, out_path = tmp_path / "tune.json", tmp_path / "confirm.json"
    kwargs = {"seasons": [2016], "n_simulations": 200}
    with pytest.raises(FileNotFoundError):
        bench.confirm(table, blend_for(table), tune_path=tune_path, out_path=out_path, **kwargs)
    bench.write_tune(tune_path, bench.tune(table, seasons=[2014], n_simulations=200))
    report = bench.confirm(table, blend_for(table), tune_path=tune_path, out_path=out_path, **kwargs)
    assert out_path.exists() and json.loads(out_path.read_text()) == json.loads(json.dumps(report))
    with pytest.raises(FileExistsError):
        bench.confirm(table, blend_for(table), tune_path=tune_path, out_path=out_path, **kwargs)


def test_confirm_reports_every_variant_with_every_requested_metric(table, tmp_path):
    tune_path, out_path = tmp_path / "tune.json", tmp_path / "confirm.json"
    bench.write_tune(tune_path, bench.tune(table, seasons=[2014], n_simulations=200))
    report = bench.confirm(table, blend_for(table), tune_path=tune_path, out_path=out_path,
                           seasons=[2016], n_simulations=200)
    json.dumps(report, allow_nan=False)  # every number finite
    assert report["default_distribution"] == json.loads(tune_path.read_text())["default"]
    assert len(report["variants"]) == len(DISTRIBUTIONS) * len(bench.SOURCES)
    n = len(table[table["season"] == 2016])
    for v in report["variants"]:
        assert v["games"] == n and v["source"] in bench.SOURCES and v["distribution"] in DISTRIBUTIONS
        assert {"margin_mae", "margin_rmse", "total_mae", "total_rmse"} <= set(v)
        assert set(v["coverage"]["margin"]) == {"0.5", "0.8", "0.95"} == set(v["coverage"]["total"])
        for kind in ("cover", "over"):
            c = v["calibration"][kind]
            assert {"table", "brier", "brier_flat_half"} <= set(c) and c["table"]
        assert {"sim", "real"} <= set(v["tie_rate"])
        assert {"3", "7"} == set(v["key_numbers"]) and {"sim", "real"} <= set(v["key_numbers"]["3"])
        assert {"mean_abs", "max_abs", "n_above_0.10", "largest"} <= set(v["win_gap_vs_blend"])
        w = v["win_probability"]
        assert {"log_loss", "accuracy", "blend_log_loss", "market_log_loss", "log_loss_gain_vs_blend",
                "log_loss_gain_ci"} <= set(w) and len(w["log_loss_gain_ci"]) == 2
    assert report["sources_note"].lower().count("by construction") >= 1


def test_default_distribution_is_the_one_recorded_by_the_tune_run():
    path = Path(__file__).resolve().parents[2] / "docs/gauntlet/logs/step-18c-evidence/tune-result.json"
    recorded = json.loads(path.read_text())
    assert recorded["seasons"] == bench.TUNE_SEASONS and max(recorded["seasons"]) < bench.CONFIRM_SEASONS[0]
    assert recorded["default"] == DEFAULT_DISTRIBUTION
