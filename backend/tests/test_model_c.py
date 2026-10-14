"""Step 14c clauses: boosted trees, stacked blend, margin model, explosive plays, confidence points."""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from nflpi.analytics import backtest as bt
from nflpi.analytics import model_c as mc
from nflpi.analytics.metrics import log_loss, paired_gain
from nflpi.predictions.features import BLEND_FEATURES
from nflpi.predictions.scores import BLEND_FEATURES as LINE_FEATURES
from nflpi.predictions.scores import STATS_FEATURES, ScoreModel
from nflpi.predictions.sheet import Ranked, order
from tests.test_model import _flip_scores, lines_frame

SMALL_GRID = ((2, 2), (3, 2))  # leaves of 2: the fixture seasons have 15 games
SEASONS = [2021, 2022]


def tree_columns(grid=SMALL_GRID) -> list[str]:
    return [mc.tree_column(s, d, leaf) for s in ("core", "wide") for d, leaf in grid]


# ---- T: boosted trees ----


def test_tree_names_and_sets_are_frozen():
    assert mc.TREE_GRID == ((2, 30), (2, 80), (3, 30), (3, 80))
    assert (mc.TREE_LEARNING_RATE, mc.TREE_MAX_ITER) == (0.05, 300)
    assert mc.TREE_SETS["core"] == BLEND_FEATURES
    assert mc.TREE_SETS["wide"] == [*BLEND_FEATURES, "spread_line", "total_line", "rest_diff", "roof_indoor",
                                    "temp_f", "wind_mph", "div_flag"]
    assert mc.tree_column("wide", 3, 80) == "p_tree_wide_d3_l80"


def test_tree_inputs_code_the_roof_and_the_division_flag_without_touching_the_frame():
    df = pd.DataFrame({"roof": ["dome", "closed", "outdoors", "open", None],
                       "div_game": [True, False, True, False, True]})
    before = df.copy()
    out = mc.tree_inputs(df)
    assert out["roof_indoor"].tolist()[:4] == [1.0, 1.0, 0.0, 0.0] and np.isnan(out["roof_indoor"].iloc[4])
    assert out["div_flag"].tolist() == [1.0, 0.0, 1.0, 0.0, 1.0]
    assert list(df.columns) == list(before.columns)  # the input frame is not changed


def test_a_tree_model_stops_early_on_the_last_training_season_and_refits_on_all(monkeypatch):
    rng = np.random.default_rng(5)
    rows = []
    for season in (2015, 2016, 2017):
        x = rng.uniform(-2, 2, 120)
        rows.append(pd.DataFrame({"season": season, "x": x, "home_win": (x**2 > 1.2).astype(float)}))
    train = pd.concat(rows, ignore_index=True)
    fits = []
    real = HistGradientBoostingClassifier.fit

    def spy(self, X, y, *args, **kwargs):
        fits.append((len(X), self.get_params()["max_iter"]))
        return real(self, X, y, *args, **kwargs)

    monkeypatch.setattr(HistGradientBoostingClassifier, "fit", spy)
    model = mc.TreeModel.fit_early(train, ["x"], depth=2, leaf=5)
    assert fits == [(240, mc.TREE_MAX_ITER), (360, model.n_iter)]  # first fit leaves 2017 out, second uses all
    assert 1 <= model.n_iter <= mc.TREE_MAX_ITER
    test = pd.DataFrame({"x": [-1.8, 0.0, 1.8]})
    p = model.predict(test)
    assert p[0] > 0.7 and p[2] > 0.7 and p[1] < 0.3  # it learned a shape a straight line cannot


def test_early_stopping_picks_the_tree_count_from_the_last_season_and_ignores_unplayed_games():
    rng = np.random.default_rng(6)
    rows = []
    for season in (2015, 2016, 2017):
        x = rng.uniform(-2, 2, 120)
        win = (x > 0).astype(float) if season < 2017 else (x < 0).astype(float)  # the last season runs the other way
        rows.append(pd.DataFrame({"season": season, "x": x, "home_win": win}))
    train = pd.concat(rows, ignore_index=True)
    train.loc[len(train)] = {"season": 2017, "x": 0.1, "home_win": np.nan}  # a game not played yet
    model = mc.TreeModel.fit_early(train, ["x"], depth=2, leaf=5)
    assert model.n_iter < 10 < mc.TREE_MAX_ITER  # more trees only fit the wrong way for 2017, so it stops at once


def test_the_trees_are_fitted_on_the_coded_roof_and_division_flag(monkeypatch):
    df = lines_frame()
    df.loc[df.index[::3], "roof"] = "dome"
    trains = []
    real = mc.TreeModel.fit_early.__func__

    def spy(cls, train, features, depth, leaf):
        trains.append(train)
        return real(cls, train, features, depth, leaf)

    monkeypatch.setattr(mc.TreeModel, "fit_early", classmethod(spy))
    mc.tree_preds(df, [2022], window=3, grid=SMALL_GRID[:1])
    assert trains and all(set(t["roof_indoor"].dropna()) == {0.0, 1.0} and (t["div_flag"] == 1.0).all() for t in trains)


def test_tree_preds_carry_the_blend_and_eight_variants_for_the_bench_games():
    df = lines_frame()
    base = bt.candidate_preds(df, SEASONS, window=3)
    got = mc.tree_preds(df, SEASONS, window=3, grid=SMALL_GRID)
    assert list(got["game_id"]) == list(base["game_id"]) and np.allclose(got["p_blend"], base["p_blend"])
    cols = tree_columns()
    assert len(cols) == 4 and all(c in got and got[c].between(0, 1).all() for c in cols)


def test_tree_preds_fit_only_on_the_window_before_the_test_season(monkeypatch):
    seen = []
    real = mc.TreeModel.fit_early.__func__

    def spy(cls, train, features, depth, leaf):
        seen.append((set(train["season"]), list(features)))
        return real(cls, train, features, depth, leaf)

    monkeypatch.setattr(mc.TreeModel, "fit_early", classmethod(spy))
    mc.tree_preds(lines_frame(), SEASONS, window=3, grid=SMALL_GRID)
    assert seen and all(s <= {2018, 2019, 2020} or s <= {2019, 2020, 2021} for s, _ in seen)
    half = len(seen) // 2
    assert all(max(s) < 2022 for s, _ in seen[half:]) and all(max(s) < 2021 for s, _ in seen[:half])
    assert {tuple(f) for _, f in seen} == {tuple(mc.TREE_SETS["core"]), tuple(mc.TREE_SETS["wide"])}


def test_tree_preds_never_use_a_result_from_the_test_week_or_later():
    df = lines_frame()
    got = mc.tree_preds(df, [2022], window=3, grid=SMALL_GRID)
    week4 = df.loc[(df["season"] == 2022) & (df["week"] == 4), "kickoff_utc"].min()
    after = mc.tree_preds(_flip_scores(df, df["kickoff_utc"] >= week4), [2022], window=3, grid=SMALL_GRID)
    early = (got["week"] < 4).to_numpy()
    assert early.any() and list(after["game_id"]) == list(got["game_id"])
    assert all(np.allclose(got.loc[early, c], after.loc[early, c]) for c in tree_columns())
    earlier = mc.tree_preds(_flip_scores(df, df["season"] == 2021), [2022], window=3, grid=SMALL_GRID)
    assert all(not np.allclose(got[c], earlier[c]) for c in tree_columns())


def test_a_tree_keeps_a_game_with_missing_weather_and_uses_it():
    df = lines_frame()
    df["temp_f"] = np.where(df.index % 4 == 0, np.nan, df["temp_f"])  # missing weather is normal (domes)
    got = mc.tree_preds(df, [2022], window=3, grid=SMALL_GRID)
    assert got[tree_columns()].notna().all().all() and len(got) > 0


# ---- S: stacked blend ----


def test_stack_weight_is_the_grid_weight_with_the_lowest_log_loss():
    y = np.array([1.0, 0.0] * 10)
    blend = np.where(y == 1, 0.55, 0.45)
    perfect = np.where(y == 1, 0.9, 0.1)
    garbage = np.where(y == 1, 0.1, 0.9)
    assert mc.STACK_GRID[0] == 0.0 and mc.STACK_GRID[-1] == 1.0 and len(mc.STACK_GRID) == 21
    assert mc.stack_weight(blend, perfect, y) == 1.0
    assert mc.stack_weight(blend, garbage, y) == 0.0
    assert mc.stack_weight(blend, blend, y) == 0.0  # a tie goes to the smaller weight (the blend itself)
    half = mc.stack_weight(np.where(y == 1, 0.8, 0.2), np.where(y == 1, 0.5, 0.5), y)
    assert 0.0 <= half <= 1.0 and half == min(mc.STACK_GRID, key=lambda w: log_loss(
        (1 - w) * np.where(y == 1, 0.8, 0.2) + w * 0.5, y) + 1e-12 * w)


def _stack_rows() -> pd.DataFrame:
    rng = np.random.default_rng(9)
    rows = []
    for season in (2019, 2020, 2021, 2022):
        truth = rng.uniform(0.2, 0.8, 300)
        y = (rng.uniform(size=300) < truth).astype(float)
        blend = np.clip(truth + rng.normal(0, 0.15, 300), 0.05, 0.95)
        tree = np.clip(truth + rng.normal(0, 0.05, 300), 0.05, 0.95)
        rows.append(pd.DataFrame({"season": season, "home_win": y, "p_blend": blend, "p_t": tree}))
    return pd.concat(rows, ignore_index=True)


def test_stacked_uses_earlier_seasons_only_and_leaves_the_first_season_missing():
    preds = _stack_rows()
    got = mc.stacked(preds, "p_t")
    season = preds["season"]
    assert list(got.index) == list(preds.index) and got[season == 2019].isna().all()
    w = mc.stack_weight(preds.loc[season == 2019, "p_blend"].to_numpy(), preds.loc[season == 2019, "p_t"].to_numpy(),
                        preds.loc[season == 2019, "home_win"].to_numpy())
    cur = preds[season == 2020]
    assert np.allclose(got[season == 2020], (1 - w) * cur["p_blend"] + w * cur["p_t"])
    flipped = preds.assign(home_win=np.where(season >= 2021, 1 - preds["home_win"], preds["home_win"]))
    after = mc.stacked(flipped, "p_t")
    assert np.allclose(got[season == 2021], after[season == 2021])  # its own and later results: no effect
    worse = preds.assign(p_t=np.where(season < 2022, 1 - preds["p_t"], preds["p_t"]))  # the tree failed before 2022
    earlier = mc.stacked(worse, "p_t")
    assert not np.allclose(got[season == 2022], earlier[season == 2022])  # earlier results do teach 2022


# ---- G: margin model turned into a win chance ----


def test_margin_to_prob_is_the_normal_cdf_and_needs_a_positive_spread():
    assert mc.margin_to_prob(np.array([0.0]), 13.0)[0] == pytest.approx(0.5)
    p = mc.margin_to_prob(np.array([-7.0, 0.0, 7.0, 14.0]), 13.0)
    assert (np.diff(p) > 0).all() and p[2] == pytest.approx(0.7054, abs=1e-3)  # Phi(7 / 13)
    assert np.isnan(mc.margin_to_prob(np.array([np.nan]), 13.0)[0])
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            mc.margin_to_prob(np.array([1.0]), bad)


def _margin_train(shift_last: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    rows = []
    for season in (2015, 2016, 2017, 2018):
        x = rng.normal(0, 1, 200)
        shift = shift_last if season == 2018 else 0.0
        rows.append(pd.DataFrame({"season": season, "status": "final", "x": x,
                                  "home_score": 20 + 3 * x + shift + rng.normal(0, 4, 200), "away_score": 20.0}))
    return pd.concat(rows, ignore_index=True)


def test_margin_sigma_is_the_spread_of_misses_on_seasons_the_fit_did_not_see():
    train = _margin_train()
    assert mc.margin_sigma(train, ["x"]) == pytest.approx(4.0, abs=0.5)
    shifted = _margin_train(shift_last=10.0)
    x = np.column_stack((shifted["x"], np.ones(len(shifted))))
    margin = (shifted["home_score"] - shifted["away_score"]).to_numpy()
    in_sample = float(np.std(margin - x @ np.linalg.lstsq(x, margin, rcond=None)[0]))
    assert mc.margin_sigma(shifted, ["x"]) > in_sample + 1.0  # a season held out shows the real miss


def test_margin_preds_have_five_variants_fitted_on_earlier_seasons_with_no_leak(monkeypatch):
    df = lines_frame()
    base = bt.candidate_preds(df, SEASONS, window=3)
    seen = []
    real = ScoreModel.fit.__func__

    def spy(cls, train, features):
        seen.append((set(train["season"]), list(features)))
        return real(cls, train, features)

    monkeypatch.setattr(ScoreModel, "fit", classmethod(spy))
    got = mc.margin_preds(df, SEASONS, window=3)
    monkeypatch.undo()
    assert list(got["game_id"]) == list(base["game_id"]) and np.allclose(got["p_blend"], base["p_blend"])
    cols = ["p_m_stats", "p_m_line", "p_m_in_stats", "p_m_in_stats_total", "p_m_in_line"]
    assert all(got[c].between(0, 1).all() for c in cols)
    assert {tuple(f) for _, f in seen} == {tuple(STATS_FEATURES), tuple(LINE_FEATURES)}
    assert all(max(s) <= 2021 for s, _ in seen) and any(max(s) == 2020 for s, _ in seen)
    assert {"m_margin_stats", "m_total_stats", "m_margin_line"} <= set(got.columns)


def test_margin_preds_never_use_a_result_from_the_test_week_or_later():
    df = lines_frame()
    got = mc.margin_preds(df, [2022], window=3)
    week4 = df.loc[(df["season"] == 2022) & (df["week"] == 4), "kickoff_utc"].min()
    after = mc.margin_preds(_flip_scores(df, df["kickoff_utc"] >= week4), [2022], window=3)
    early = (got["week"] < 4).to_numpy()
    cols = ["p_m_stats", "p_m_line", "p_m_in_stats", "p_m_in_stats_total", "p_m_in_line"]
    assert early.any() and list(after["game_id"]) == list(got["game_id"])
    assert all(np.allclose(got.loc[early, c], after.loc[early, c]) for c in cols)
    earlier = mc.margin_preds(_flip_scores(df, df["season"] == 2021), [2022], window=3)
    assert all(not np.allclose(got[c], earlier[c]) for c in cols)


def test_margin_chances_use_the_held_out_season_spread_and_the_frozen_scales(monkeypatch):
    assert (mc.MARGIN_SCALE, mc.TOTAL_CENTER, mc.TOTAL_SCALE) == (7, 45, 10)
    monkeypatch.setattr(mc, "_miss_sigma", lambda *args: 5.0)
    got = mc.margin_preds(lines_frame(), [2022], window=3)
    want = mc.margin_to_prob(got["m_margin_stats"], 5.0)
    assert np.allclose(got["p_m_stats"], want)


def test_the_line_input_is_scored_by_the_line_model_not_the_stats_model(monkeypatch):
    seen = []
    real = mc.LogitModel.fit.__func__

    def spy(cls, train, features, *args, **kwargs):
        seen.append((list(features), train.copy()))
        return real(cls, train, features, *args, **kwargs)

    monkeypatch.setattr(mc.LogitModel, "fit", classmethod(spy))
    mc.margin_preds(lines_frame(), [2022], window=3)
    rows = next(t for f, t in seen if "in_margin_line" in f and "in_margin_stats" not in f)
    both = next(t for f, t in seen if "in_margin_stats" in f)
    assert not np.allclose(rows["in_margin_line"], both["in_margin_stats"])


def test_margin_variants_that_need_a_line_keep_the_blend_when_the_line_is_missing():
    df = lines_frame()
    week1 = df[(df["season"] == 2022) & (df["week"] == 1)].index
    df.loc[week1[0], "spread_line"] = np.nan
    got = mc.margin_preds(df, [2022], window=3).set_index("game_id")
    row = got.loc[df.loc[week1[0], "game_id"]]
    for col in ("p_m_line", "p_m_in_line"):  # never an invented line
        assert row[col] == row["p_blend"]
    assert row["p_m_stats"] != row["p_blend"]


# ---- E: explosive plays ----


def _plays(game_id: str, team: str, plays: float, explosive: float) -> dict:
    return {"game_id": game_id, "team": team, "plays": plays, "explosive": explosive}


def test_explosive_net_is_a_teams_own_rate_minus_its_opponents_in_the_same_game():
    rows = [_plays("g1", "BUF", 50, 5), _plays("g1", "MIA", 40, 2),
            _plays("g2", "BUF", 60, 6), _plays("g3", "NE", 0, 0), _plays("g3", "NYJ", 30, 3),
            _plays("g4", "KC", 10, 1), _plays("g4", "KC", 10, 1)]
    out = mc.explosive_net(rows)
    assert out.columns.tolist() == ["game_id", "team", "net_epa"]  # the column the rating code already reads
    got = {(r.game_id, r.team): r.net_epa for r in out.itertuples()}
    assert got == {("g1", "BUF"): pytest.approx(0.10 - 0.05), ("g1", "MIA"): pytest.approx(0.05 - 0.10)}


def _explosive_fixture(df: pd.DataFrame) -> list[dict]:
    rows = []
    for r in df.itertuples():
        rows += [_plays(r.game_id, r.home_team, 60, 4 + (r.Index % 5)),
                 _plays(r.game_id, r.away_team, 60, 3 + (r.Index % 3))]
    return rows


def test_explosive_preds_use_pregame_ratings_fit_on_earlier_seasons_and_fall_back_without_one(monkeypatch):
    df = lines_frame()
    explosive = mc.explosive_net(_explosive_fixture(df))
    assert mc.EXPLOSIVE_HALF_LIVES == (4, 8, 16) and mc.EXPLOSIVE_SCALE == 50
    got = mc.explosive_preds(df, [2022], explosive, window=3)
    assert all(f"p_expl_{h}" in got and got[f"p_expl_{h}"].between(0, 1).all() for h in (4, 8, 16))
    week4 = df.loc[(df["season"] == 2022) & (df["week"] == 4), "kickoff_utc"].min()
    flipped = df.copy()
    flipped.loc[flipped["kickoff_utc"] >= week4, "home_score"] += 7
    after = mc.explosive_preds(flipped, [2022], explosive, window=3)
    early = (got["week"] < 4).to_numpy()
    assert early.any() and all(
        np.allclose(got.loc[early, f"p_expl_{h}"], after.loc[early, f"p_expl_{h}"]) for h in (4, 8, 16))


# ---- P: confidence points ----


def _week(probs, wins, season=2022, week=1, market=None) -> pd.DataFrame:
    n = len(probs)
    return pd.DataFrame({"season": season, "week": week, "game_id": [f"g{i}" for i in range(n)],
                         "kickoff_utc": pd.date_range("2022-09-11 17:00", periods=n, freq="1h", tz="UTC"),
                         "p_blend": probs, "p_market": market if market is not None else probs, "home_win": wins})


def test_points_go_from_the_week_size_down_to_one_in_the_order_given():
    week = _week([0.9, 0.4, 0.7], [1.0, 1.0, 0.0])  # picks: home 0.9, away 0.6, home 0.7; outcomes: right, wrong, wrong
    sort = mc.week_points(week, "sort")
    assert sort == {"expected": pytest.approx(3 * 0.9 + 2 * 0.7 + 1 * 0.6), "actual": 3.0}
    assert mc.week_points(week, "reverse") == {"expected": pytest.approx(1 * 0.9 + 2 * 0.7 + 3 * 0.6), "actual": 1.0}
    assert mc.week_points(week, "kickoff")["actual"] == 3.0  # g0 first kickoff gets the most points
    oracle = mc.week_points(week, "oracle")
    assert oracle["actual"] == 3.0 and oracle["expected"] <= sort["expected"]
    with pytest.raises(ValueError):
        mc.week_points(week, "alphabetical")


def test_ties_are_broken_by_game_id_and_a_half_is_an_away_pick():
    week = _week([0.5, 0.5], [0.0, 1.0])
    assert mc.week_points(week, "sort")["actual"] == 2.0  # g0 away (right) gets 2; g1 away (wrong) gets 1


def test_todays_pick_sheet_without_ai_evidence_is_the_probability_sort():
    rng = np.random.default_rng(4)
    probs = rng.uniform(0.05, 0.95, 16)
    week = _week(probs, (rng.uniform(size=16) < probs).astype(float))
    pick = np.maximum(week["p_blend"], 1 - week["p_blend"])
    sheet = order([Ranked(g, p) for g, p in zip(week["game_id"], pick, strict=True)], {})
    assert sheet == mc.points_order(week, "sort")


def test_swap_ceiling_counts_what_the_sheets_tie_rule_could_cost_at_most():
    week = _week([0.700, 0.695, 0.60, 0.595, 0.80], [1.0] * 5)
    # sorted picks: 0.80, 0.700, 0.695, 0.60, 0.595 -> the rule swaps (0.700, 0.695), then (0.60, 0.595)
    assert mc.swap_ceiling(week) == pytest.approx(0.005 + 0.005)


def test_a_pick_joins_only_one_swap_and_a_gap_at_the_band_is_not_a_swap():
    chain = _week([0.700, 0.695, 0.692], [1.0] * 3)
    assert mc.swap_ceiling(chain) == pytest.approx(0.005)  # (0.700, 0.695) swap; 0.692 is not paired again
    apart = _week([0.80, 0.785], [1.0] * 2)
    assert mc.swap_ceiling(apart) == 0.0  # 0.015 is outside the 0.01 band


def test_points_report_has_every_order_per_week_and_a_paired_interval_for_the_gap():
    rng = np.random.default_rng(8)
    rows = []
    for season in (2022, 2023):
        for week in range(1, 11):
            p = rng.uniform(0.2, 0.9, 14)
            rows.append(_week(p, (rng.uniform(size=14) < p).astype(float), season, week))
    preds = pd.concat(rows, ignore_index=True)
    rep = mc.points_report(preds)
    assert rep["weeks"] == 20 and set(rep["orders"]) == {"sort", "market", "kickoff", "reverse", "oracle"}
    sort, rev, oracle = (rep["orders"][k] for k in ("sort", "reverse", "oracle"))
    assert rev["expected_per_week"] < oracle["expected_per_week"] <= sort["expected_per_week"]
    assert rev["actual_per_week"] < sort["actual_per_week"] <= oracle["actual_per_week"]
    gap = rep["orders"]["kickoff"]["sort_minus_order_actual"]
    assert gap["mean"] > 0 and gap["ci"][0] < gap["mean"] < gap["ci"][1]
    assert "swap_ceiling_per_week" in rep and rep["by_season"][0]["season"] == 2022


# ---- C: the report keeps the ship rule and shows every variant's gap ----


def test_evaluate_c_keeps_the_ship_rule_and_adds_every_variants_confirm_gain_and_gap():
    rows = []
    for season, a, b in ((2019, 0.9, 0.9), (2020, 0.8, 0.55), (2021, 0.55, 0.8)):
        for i in range(40):
            y = float(i % 2)
            side = 1.0 if y == 1 else -1.0
            rows.append({"season": season, "week": 1 + i % 4, "home_win": y, "p_blend": 0.5 + 0.1 * side,
                         "p_a": 0.5 + (a - 0.5) * side, "p_b": 0.5 + (b - 0.5) * side})
    preds = pd.DataFrame(rows)
    plain = bt.evaluate(preds, {"x": ["p_a", "p_b"]}, tune=[2020], confirm=[2021], cluster=["season", "week"])[0]
    got = mc.evaluate_c(preds, {"x": ["p_a", "p_b"]}, tune=[2020], confirm=[2021], cluster=["season", "week"])[0]
    assert {k: got[k] for k in plain} == plain  # nothing the rule reads changes
    confirm = preds[preds["season"] == 2021]
    for row in got["all_variants"]:
        gain = paired_gain(confirm[row["variant"]].to_numpy(), confirm["p_blend"].to_numpy(),
                           confirm["home_win"].to_numpy())
        assert row["confirm_gain"] == pytest.approx(gain["log_loss_gain"])
        assert row["gap"] == pytest.approx(row["tune_gain"] - row["confirm_gain"])
    assert [r["variant"] for r in got["all_variants"]] == ["p_a", "p_b"]
    with pytest.raises(ValueError):
        mc.evaluate_c(preds, {"x": ["p_a"]}, tune=[2020, 2021], confirm=[2021])
