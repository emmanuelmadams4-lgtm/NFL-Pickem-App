"""Step 18g clauses: Pythagorean head-to-head, quarterback rating, travel and time zone, matchup score, verdicts."""

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from nflpi.analytics import backtest as bt
from nflpi.analytics import bench_18g as b
from nflpi.analytics.metrics import paired_gain
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES
from nflpi.predictions.model import LogitModel
from tests.test_model import _flip_scores, lines_frame

SEASONS = [2021, 2022]
BASE0 = datetime(2022, 9, 8, 17, tzinfo=UTC)


def games(rows: list[tuple]) -> pd.DataFrame:
    """rows: (home, away, home_score, away_score); one game a week, kickoff ordered."""
    return pd.DataFrame(
        [
            {
                "game_id": f"g{i}",
                "season": 2022,
                "week": i + 1,
                "kickoff_utc": BASE0 + timedelta(days=7 * i),
                "home_team": h,
                "away_team": a,
                "home_score": hs,
                "away_score": as_,
            }
            for i, (h, a, hs, as_) in enumerate(rows)
        ]
    )


# ---- P: points-based (Pythagorean) head-to-head ----


def test_pythagorean_constants_are_frozen():
    assert b.PYTH_EXPONENT == 2.37 and b.PYTH_HALF_LIVES == (4, 8, 16)


def test_a_teams_log_odds_is_exponent_times_log_of_points_for_over_against_and_the_game_value_is_home_minus_away():
    df = games([("A", "B", 30, 10), ("A", "B", 21, 21)])
    got = b.pythag_diff(df, half_life=4)
    assert np.isnan(got.iloc[0])  # nobody has played
    assert got.iloc[1] == pytest.approx(b.PYTH_EXPONENT * (math.log(30 / 10) - math.log(10 / 30)))


def test_earlier_games_are_decayed_by_half_life_games_of_that_team():
    df = games([("A", "B", 30, 10), ("A", "C", 20, 20), ("A", "B", 17, 17), ("D", "E", 7, 7)])
    d = 0.5 ** (1 / 4)
    got = b.pythag_diff(df, half_life=4)
    pf_a, pa_a = 30 * d + 20, 10 * d + 20  # A after two games
    pf_b, pa_b = 10, 30  # B after one
    assert got.iloc[2] == pytest.approx(b.PYTH_EXPONENT * (math.log(pf_a / pa_a) - math.log(pf_b / pa_b)))
    assert np.isnan(got.iloc[3])  # D and E have no past


def test_swapping_home_and_away_negates_the_value():
    base = games([("A", "B", 30, 10), ("C", "D", 17, 20), ("C", "A", 20, 13)])
    swapped = base.copy()
    swapped.loc[2, ["home_team", "away_team", "home_score", "away_score"]] = ["A", "C", 13, 20]
    assert b.pythag_diff(base, 8).iloc[2] == pytest.approx(-b.pythag_diff(swapped, 8).iloc[2])
    assert b.pythag_diff(base, 8).iloc[2] != 0


def test_a_games_own_score_and_later_games_never_move_its_value():
    df = games([("A", "B", 30, 10), ("A", "B", 21, 14), ("B", "A", 3, 40)])
    got = b.pythag_diff(df, 8)
    other = df.copy()
    other.loc[1:, ["home_score", "away_score"]] = [[0, 50], [50, 0]]
    after = b.pythag_diff(other, 8)
    assert got.iloc[:2].equals(after.iloc[:2]) and got.iloc[2] != after.iloc[2]


def test_a_game_not_played_yet_adds_nothing_to_the_ratings():
    df = games([("A", "B", 30, 10), ("A", "C", np.nan, np.nan), ("A", "B", 21, 14)])
    clean = df.drop(index=1).reset_index(drop=True)
    assert b.pythag_diff(df, 8).iloc[2] == pytest.approx(b.pythag_diff(clean, 8).iloc[1])


def test_a_shutout_is_clipped_so_the_value_stays_finite():
    df = games([("A", "B", 30, 0), ("A", "B", 20, 10)])
    got = b.pythag_diff(df, 4)
    cap = math.log(0.99 / 0.01)
    assert got.iloc[1] == pytest.approx(2 * cap) and np.isfinite(got).iloc[1]


def test_kickoffs_out_of_order_are_refused():
    df = games([("A", "B", 30, 10), ("A", "B", 21, 14)]).iloc[::-1]
    with pytest.raises(ValueError, match="kickoff_utc"):
        b.pythag_diff(df, 4)


# ---- column names and labels ----


def test_column_names_and_labels_are_frozen():
    assert b.pythag_column("blend", 8) == "p_pyth_blend_8" and b.pythag_column("base", 4) == "p_pyth_base_4"
    assert b.qb_column("blend", 16) == "p_qb_blend_16" and b.qb_column("base", 32) == "p_qb_base_32"
    assert (
        b.travel_column("blend", "tz") == "p_travel_blend_tz"
        and b.travel_column("base", "both") == "p_travel_base_both"
    )
    assert b.label("p_pyth_blend_8") == "market-informed" and b.label("p_pyth_base_8") == "football-only"
    assert b.label("p_qb_blend_16") == "market-informed" and b.label("p_travel_base_tz") == "football-only"
    assert b.label("p_match_football") == "football-only" and b.label("p_match_market") == "market-informed"
    with pytest.raises(ValueError):
        b.label("p_blend")


# ---- Q: quarterback rating ----


def stat(player, game, pos="QB", pe="2.0", re="0.5", att="20", sk="2", car="3"):
    return {
        "player_id": player,
        "game_id": game,
        "position": pos,
        "passing_epa": pe,
        "rushing_epa": re,
        "attempts": att,
        "sacks_suffered": sk,
        "carries": car,
    }


def test_quarterback_games_sum_epa_and_dropbacks_for_quarterbacks_only():
    rows = [
        stat("q1", "g0"),
        stat("w1", "g0", pos="WR"),
        stat("q2", "g0", pe="NA"),
        stat("q3", "g0", att="0", sk="0", car="0"),
        stat("q4", "g0", re=""),
    ]
    got = b.qb_games(rows)
    assert list(got.columns) == ["game_id", "player_id", "epa", "plays"]
    assert got.to_dict("records") == [{"game_id": "g0", "player_id": "q1", "epa": 2.5, "plays": 25.0}]


def qb_frame(ids: list[tuple]) -> pd.DataFrame:
    df = games([("A", "B", 20, 10)] * len(ids))
    df["home_qb_id"] = [h for h, _ in ids]
    df["away_qb_id"] = [a for _, a in ids]
    return df


def qb_log(*entries) -> pd.DataFrame:
    return pd.DataFrame(entries, columns=["game_id", "player_id", "epa", "plays"])


def test_qb_constants_are_frozen():
    assert (b.QB_HALF_LIVES, b.QB_SHRINK, b.QB_SCALE) == ((8, 16, 32), 150.0, 50.0)


def test_an_unseen_quarterback_rates_zero_and_a_seen_one_is_shrunk_toward_zero():
    df = qb_frame([("h", "a"), ("h", "a")])
    log = qb_log(("g0", "h", 10.0, 30.0), ("g0", "a", -6.0, 30.0))
    got = b.qb_diff(df, log, half_life=8)
    assert got.iloc[0] == 0.0
    assert got.iloc[1] == pytest.approx(b.QB_SCALE * (10 / (30 + 150) - -6 / (30 + 150)))


def test_a_quarterbacks_past_is_decayed_by_his_own_games_and_follows_him_across_teams():
    df = qb_frame([("h", "a"), ("x", "h"), ("h", "a")])
    df.loc[1, ["home_team", "away_team"]] = ["C", "A"]
    log = qb_log(("g0", "h", 10.0, 30.0), ("g1", "h", 4.0, 20.0))
    d = 0.5 ** (1 / 8)
    got = b.qb_diff(df, log, half_life=8)
    rating = (10 * d + 4) / (30 * d + 20 + 150)
    assert got.iloc[2] == pytest.approx(b.QB_SCALE * rating)  # 'a' never played: rating 0


def test_a_relief_quarterback_who_threw_but_did_not_start_is_rated_next_time():
    df = qb_frame([("h", "a"), ("sub", "a")])
    log = qb_log(("g0", "h", 1.0, 10.0), ("g0", "sub", 6.0, 30.0), ("g0", "a", 0.0, 10.0))
    assert b.qb_diff(df, log, 8).iloc[1] == pytest.approx(b.QB_SCALE * (6 / 180))


def test_a_missing_quarterback_id_gives_a_missing_value():
    df = qb_frame([("h", "a"), (None, "a"), ("h", np.nan)])
    got = b.qb_diff(df, qb_log(), 8)
    assert got.iloc[0] == 0.0 and got.iloc[1:].isna().all()


def test_a_games_own_quarterback_numbers_and_later_games_never_move_its_value():
    df = qb_frame([("h", "a"), ("h", "a"), ("h", "a")])
    log = qb_log(("g0", "h", 10.0, 30.0), ("g1", "h", 4.0, 20.0), ("g2", "h", 9.0, 40.0))
    bumped = qb_log(("g0", "h", 10.0, 30.0), ("g1", "h", 99.0, 20.0), ("g2", "h", -9.0, 40.0))
    a, c = b.qb_diff(df, log, 8), b.qb_diff(df, bumped, 8)
    assert a.iloc[:2].equals(c.iloc[:2]) and a.iloc[2] != c.iloc[2]


def test_quarterback_ratings_need_ordered_kickoffs():
    with pytest.raises(ValueError, match="kickoff_utc"):
        b.qb_diff(qb_frame([("h", "a"), ("h", "a")]).iloc[::-1], qb_log(), 8)


# ---- T: travel and time zone ----

COORDS = {"SEA00": (47.60, -122.33), "MIA00": (25.96, -80.24), "PHO00": (33.53, -112.26), "LON00": (51.56, -0.28)}
ZONES = {
    "SEA00": "America/Los_Angeles",
    "MIA00": "America/New_York",
    "PHO00": "America/Phoenix",
    "LON00": "Europe/London",
}


def trip_frame(rows: list[tuple]) -> pd.DataFrame:
    """rows: (home, away, stadium_id, neutral, kickoff)."""
    return pd.DataFrame(
        [
            {
                "game_id": f"t{i}",
                "season": 2022,
                "week": i + 1,
                "kickoff_utc": k,
                "home_team": h,
                "away_team": a,
                "stadium_id": s,
                "neutral_site": n,
            }
            for i, (h, a, s, n, k) in enumerate(rows)
        ]
    )


def test_great_circle_distance_matches_a_known_pair():
    assert b.great_circle_km((40.71, -74.01), (34.05, -118.24)) == pytest.approx(3936, rel=0.01)
    assert b.great_circle_km((10.0, 20.0), (10.0, 20.0)) == 0.0


def test_the_away_side_travels_from_its_own_home_stadium_and_the_hosts_do_not():
    sep, dec = datetime(2022, 9, 25, 17, tzinfo=UTC), datetime(2022, 12, 4, 18, tzinfo=UTC)
    df = trip_frame(
        [
            ("MIA", "SEA", "MIA00", False, sep - timedelta(days=14)),
            ("SEA", "MIA", "SEA00", False, sep),
            ("PHO", "SEA", "PHO00", False, sep + timedelta(days=1)),
            ("SEA", "PHO", "SEA00", False, dec),
        ]
    )
    got = b.travel_features(df, COORDS, ZONES)
    km = b.great_circle_km(COORDS["MIA00"], COORDS["SEA00"]) / 1000
    assert got["travel_km_diff"].iloc[1] == pytest.approx(km)
    assert got["tz_diff"].iloc[1] == pytest.approx(-3.0)  # the visitor lives three hours east: it travelled west
    assert got["tz_diff"].iloc[0] == pytest.approx(3.0)  # Miami hosting Seattle: Seattle travelled east
    assert got["tz_diff"].iloc[2] == pytest.approx(0.0)  # Phoenix keeps standard time, Seattle is on daylight time
    assert got["tz_diff"].iloc[3] == pytest.approx(
        -1.0
    )  # in December Seattle is an hour behind Phoenix: Phoenix went west


def test_a_neutral_site_makes_both_teams_travel():
    k = datetime(2022, 10, 2, 13, 30, tzinfo=UTC)
    df = trip_frame(
        [
            ("MIA", "SEA", "MIA00", False, k - timedelta(days=14)),
            ("SEA", "MIA", "SEA00", False, k - timedelta(days=7)),
            ("MIA", "SEA", "LON00", True, k),
        ]
    )
    got = b.travel_features(df, COORDS, ZONES)
    d_mia = b.great_circle_km(COORDS["MIA00"], COORDS["LON00"])
    d_sea = b.great_circle_km(COORDS["SEA00"], COORDS["LON00"])
    assert got["travel_km_diff"].iloc[2] == pytest.approx((d_sea - d_mia) / 1000)
    assert got["tz_diff"].iloc[2] == pytest.approx((1 - -7) - (1 - -4) + 0.0)  # BST +1; Seattle -7, Miami -4 in October


def test_a_stadium_or_home_venue_that_is_unknown_gives_missing_values_not_zero():
    k = datetime(2022, 9, 25, 17, tzinfo=UTC)
    df = trip_frame(
        [
            ("MIA", "SEA", "MIA00", False, k - timedelta(days=7)),
            ("SEA", "MIA", "SEA00", False, k),  # SEA has no home game earlier in the frame? it does: this one
            ("SEA", "PHO", "SEA00", False, k + timedelta(days=1)),  # PHO has no home game: no home venue
            ("MIA", "SEA", "ZZZ99", False, k + timedelta(days=2)),
        ]
    )  # stadium not in the table
    got = b.travel_features(df, COORDS, ZONES)
    assert got.iloc[1].notna().all()
    assert got.iloc[2].isna().all() and got.iloc[3].isna().all()


def test_the_home_venue_is_the_stadium_a_team_uses_most_at_home_that_season():
    k = datetime(2022, 9, 25, 17, tzinfo=UTC)
    df = trip_frame(
        [
            ("SEA", "MIA", "SEA00", False, k),
            ("SEA", "MIA", "SEA00", False, k + timedelta(days=7)),
            ("SEA", "MIA", "PHO00", False, k + timedelta(days=14)),
            ("MIA", "SEA", "MIA00", False, k + timedelta(days=21)),
        ]
    )
    got = b.travel_features(df, COORDS, ZONES)
    # row 3: SEA travels to MIA from SEA00 (its usual home), not from PHO00
    assert got["travel_km_diff"].iloc[3] == pytest.approx(b.great_circle_km(COORDS["SEA00"], COORDS["MIA00"]) / 1000)


def test_every_listed_stadium_has_a_coordinate_and_a_time_zone():
    from zoneinfo import ZoneInfo

    from nflpi.ingestion.weather import STADIUMS

    assert set(STADIUMS) <= set(b.STADIUM_COORDS) and set(b.STADIUM_COORDS) == set(b.STADIUM_ZONES)
    assert all(ZoneInfo(z) for z in b.STADIUM_ZONES.values())
    assert all(b.STADIUM_COORDS[k] == v for k, v in STADIUMS.items())  # one copy of the existing numbers
    assert b.STADIUM_ZONES["PHO00"] == "America/Phoenix" and b.STADIUM_COORDS["OAK00"] != b.STADIUM_COORDS["SFO01"]


def test_travel_variant_columns_are_frozen():
    assert b.TRAVEL_VARIANTS == {"travel": ["travel_km_diff"], "tz": ["tz_diff"], "both": ["travel_km_diff", "tz_diff"]}


# ---- walk-forward predictions ----


def spy_fits(monkeypatch):
    seen = []
    real = LogitModel.fit.__func__

    def spy(cls, train, features, weights=None):
        seen.append((list(features), set(train["season"])))
        return real(cls, train, features) if weights is None else real(cls, train, features, weights=weights)

    monkeypatch.setattr(LogitModel, "fit", classmethod(spy))
    return seen


def test_a_variant_falls_back_to_the_named_baseline_when_its_input_is_missing():
    rng = np.random.default_rng(1)
    x = rng.normal(size=200)
    train = pd.DataFrame({"x": x, "home_win": (x + rng.normal(size=200) > 0).astype(float)})
    test = pd.DataFrame({"x": [0.5, np.nan], "p_blend": [0.3, 0.3], "p_logistic": [0.8, 0.8]})
    got = b.variant_preds(train, test, ["x"], "p_logistic")
    assert 0 < got.iloc[0] < 1 and got.iloc[0] != 0.8 and got.iloc[1] == 0.8


def test_pythagorean_preds_are_six_variants_on_the_bench_games_fitted_on_the_window_only(monkeypatch):
    df = lines_frame()
    base = bt.candidate_preds(df, SEASONS, window=3)
    seen = spy_fits(monkeypatch)
    got = b.pythag_preds(df, SEASONS, window=3)
    monkeypatch.undo()
    assert list(got["game_id"]) == list(base["game_id"]) and np.allclose(got["p_blend"], base["p_blend"])
    assert {"p_logistic"} <= set(got) and np.allclose(got["p_logistic"], base["p_logistic"])
    cols = [b.pythag_column(k, h) for k in ("blend", "base") for h in b.PYTH_HALF_LIVES]
    assert all(got[c].between(0, 1).all() for c in cols) and not any(np.allclose(got[c], got["p_blend"]) for c in cols)
    used = {tuple(f) for f, _ in seen}
    assert (*BLEND_FEATURES, "pyth_diff") in used and (*BASE_FEATURES, "pyth_diff") in used
    assert all(max(s) < 2022 for f, s in seen if "pyth_diff" in f)


def test_pythagorean_preds_never_use_a_result_from_the_test_week_or_later():
    df = lines_frame()
    got = b.pythag_preds(df, [2022], window=3)
    week4 = df.loc[(df["season"] == 2022) & (df["week"] == 4), "kickoff_utc"].min()
    after = b.pythag_preds(_flip_scores(df, df["kickoff_utc"] >= week4), [2022], window=3)
    early = (got["week"] < 4).to_numpy()
    cols = [b.pythag_column(k, h) for k in ("blend", "base") for h in b.PYTH_HALF_LIVES]
    assert early.any() and all(np.allclose(got.loc[early, c], after.loc[early, c]) for c in cols)
    earlier = b.pythag_preds(_flip_scores(df, df["season"] == 2021), [2022], window=3)
    assert all(not np.allclose(got[c], earlier[c]) for c in cols)


def with_quarterbacks(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One quarterback per team and season; his game numbers follow the score margin."""
    out = df.copy()
    out["home_qb_id"] = out["home_team"] + out["season"].astype(str)
    out["away_qb_id"] = out["away_team"] + out["season"].astype(str)
    rows = []
    for r in out.itertuples():
        margin = float(r.home_score - r.away_score)
        rows += [(r.game_id, r.home_qb_id, margin / 4, 30.0), (r.game_id, r.away_qb_id, -margin / 4, 30.0)]
    return out, qb_log(*rows)


def test_quarterback_preds_replace_the_change_flags_and_fit_on_the_window_only(monkeypatch):
    df, log = with_quarterbacks(lines_frame())
    base = bt.candidate_preds(df, SEASONS, window=3)
    seen = spy_fits(monkeypatch)
    got = b.qb_preds(df, SEASONS, log, window=3)
    monkeypatch.undo()
    assert list(got["game_id"]) == list(base["game_id"]) and np.allclose(got["p_blend"], base["p_blend"])
    cols = [b.qb_column(k, h) for k in ("blend", "base") for h in b.QB_HALF_LIVES]
    assert all(got[c].between(0, 1).all() for c in cols)
    used = {tuple(f) for f, _ in seen}
    assert ("market_logit", "elo_diff", "home_field", "qb_diff") in used and (
        "elo_diff",
        "home_field",
        "qb_diff",
    ) in used
    assert all(max(s) < 2022 for f, s in seen if "qb_diff" in f)


def test_quarterback_preds_never_use_a_result_from_the_test_week_or_later():
    df, log = with_quarterbacks(lines_frame())
    got = b.qb_preds(df, [2022], log, window=3)
    week4 = df.loc[(df["season"] == 2022) & (df["week"] == 4), "kickoff_utc"].min()
    flipped = _flip_scores(df, df["kickoff_utc"] >= week4)
    flipped_df, flipped_log = with_quarterbacks(flipped)
    after = b.qb_preds(flipped_df, [2022], flipped_log, window=3)
    early = (got["week"] < 4).to_numpy()
    cols = [b.qb_column(k, h) for k in ("blend", "base") for h in b.QB_HALF_LIVES]
    assert early.any() and all(np.allclose(got.loc[early, c], after.loc[early, c]) for c in cols)


def with_stadiums(df: pd.DataFrame) -> pd.DataFrame:
    ids = sorted(b.STADIUM_COORDS)
    teams = sorted(set(df["home_team"]) | set(df["away_team"]))
    out = df.copy()
    out["stadium_id"] = out["home_team"].map({t: ids[i % len(ids)] for i, t in enumerate(teams)})
    out["neutral_site"] = False
    return out


def test_travel_preds_are_six_variants_fitted_on_the_window_only(monkeypatch):
    df = with_stadiums(lines_frame())
    base = bt.candidate_preds(df, SEASONS, window=3)
    seen = spy_fits(monkeypatch)
    got = b.travel_preds(df, SEASONS, window=3)
    monkeypatch.undo()
    assert list(got["game_id"]) == list(base["game_id"]) and np.allclose(got["p_blend"], base["p_blend"])
    cols = [b.travel_column(k, v) for k in ("blend", "base") for v in b.TRAVEL_VARIANTS]
    assert all(got[c].between(0, 1).all() for c in cols)
    used = {tuple(f) for f, _ in seen}
    for extra in b.TRAVEL_VARIANTS.values():
        assert (*BLEND_FEATURES, *extra) in used and (*BASE_FEATURES, *extra) in used
    assert all(max(s) < 2022 for f, s in seen if "tz_diff" in f or "travel_km_diff" in f)


def test_a_game_at_an_unknown_stadium_keeps_the_blends_number_in_travel_preds():
    df = with_stadiums(lines_frame())
    df.loc[df["season"] == 2022, "stadium_id"] = "ZZZ99"
    got = b.travel_preds(df, [2022], window=3)
    cols = [b.travel_column("blend", v) for v in b.TRAVEL_VARIANTS]
    assert all(np.allclose(got[c], got["p_blend"]) for c in cols)
    assert all(np.allclose(got[b.travel_column("base", v)], got["p_logistic"]) for v in b.TRAVEL_VARIANTS)


# ---- M: matchup score ----


def test_matchup_preds_are_the_fixed_formula_with_nothing_fitted(monkeypatch):
    pytest.importorskip("nflpi.data.matchup")
    from nflpi.data.matchup import matchup_score

    df = lines_frame()
    base = bt.candidate_preds(df, SEASONS, window=3)
    seen = spy_fits(monkeypatch)
    got = b.matchup_preds(df, SEASONS, window=3)
    monkeypatch.undo()
    assert list(got["game_id"]) == list(base["game_id"]) and np.allclose(got["p_blend"], base["p_blend"])
    assert np.allclose(got["p_match_football"], matchup_score(got, include_market=False) / 100)
    assert np.allclose(got["p_match_market"], matchup_score(got, include_market=True) / 100)
    assert not np.allclose(got["p_match_football"], got["p_match_market"])
    assert all(max(s) < 2022 for _, s in seen)  # only the baselines are fitted, on the window


def test_matchup_as_a_blend_input_adds_nothing_the_blend_does_not_already_have():
    pytest.importorskip("nflpi.data.matchup")
    gap = b.matchup_input_gap(lines_frame(), SEASONS, window=3)
    assert isinstance(gap, float) and 0 <= gap < 0.02


# ---- E: judging ----


def judged_frame() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for season in range(2012, 2026):
        p = rng.uniform(0.2, 0.8, 120)
        y = (rng.uniform(size=120) < p).astype(float)
        rows.append(
            pd.DataFrame(
                {
                    "season": season,
                    "week": np.arange(120) % 17 + 1,
                    "home_win": y,
                    "p_blend": np.clip(p + rng.normal(0, 0.08, 120), 0.02, 0.98),
                    "p_logistic": np.full(120, 0.55),
                    "good": p,
                    "bad": 1 - p,
                    "meh": p * 0.5 + 0.25,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


TUNE, CONFIRM = list(range(2012, 2022)), list(range(2022, 2026))


def test_evaluate_vs_chooses_on_tune_only_and_judges_the_chosen_variant_once_on_confirm_against_the_baseline():
    df = judged_frame()
    out = b.evaluate_vs(df, {"c": ["bad", "good", "meh"]}, TUNE, CONFIRM, "p_logistic", cluster=["season", "week"])
    row = out[0]
    assert row["candidate"] == "c" and row["chosen"] == "good" and row["baseline"] == "p_logistic"
    rows = df[df["season"].isin(CONFIRM)]
    ref = paired_gain(rows["good"].to_numpy(), rows["p_logistic"].to_numpy(), rows["home_win"].to_numpy())
    assert row["confirm"]["log_loss_gain"] == pytest.approx(ref["log_loss_gain"]) and row["confirm"]["ships"] is True
    assert "log_loss_gain_ci_cluster" in row["confirm"]
    by_variant = {v["variant"]: v for v in row["all_variants"]}
    assert set(by_variant) == {"bad", "good", "meh"}
    v = by_variant["bad"]
    assert v["gap"] == pytest.approx(v["tune_gain"] - v["confirm_gain"]) and v["confirm_gain"] < 0


def test_evaluate_vs_refuses_overlapping_tune_and_confirm_seasons():
    with pytest.raises(ValueError, match="overlap"):
        b.evaluate_vs(judged_frame(), {"c": ["good"]}, TUNE, [2021, 2022], "p_blend")


def test_a_variant_chosen_on_tune_is_not_the_one_with_the_best_confirm_number():
    df = judged_frame()
    flip = df["season"].isin(CONFIRM)
    df.loc[flip, ["good", "bad"]] = df.loc[flip, ["bad", "good"]].to_numpy()  # the tune favourite fails on confirm
    row = b.evaluate_vs(df, {"c": ["bad", "good"]}, TUNE, CONFIRM, "p_blend")[0]
    assert row["chosen"] == "good" and row["confirm"]["ships"] is False


def test_the_verdict_follows_the_ship_rule_and_flags_a_split_between_the_two_intervals():
    assert b.verdict({"ships": True, "ships_cluster": True}) == "ships"
    assert b.verdict({"ships": False, "ships_cluster": False}) == "does not ship"
    assert b.verdict({"ships": True, "ships_cluster": False}) == "needs the owner"
    assert b.verdict({"ships": False, "ships_cluster": True}) == "needs the owner"
    assert b.verdict({"ships": True}) == "ships" and b.verdict({"ships": False}) == "does not ship"
