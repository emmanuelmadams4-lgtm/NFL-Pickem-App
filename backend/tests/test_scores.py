"""Step 9: tiebreaker scores. Every expected number here is worked out by hand in the comments.

Clause ids (S1 ...) are the frozen criteria in docs/gauntlet/logs/step-9.md section 2.
"""

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nflpi.analytics import score_backtest as sb
from nflpi.analytics.metrics import bootstrap_ci
from nflpi.ingestion import nflverse
from nflpi.predictions import scores
from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import games_frame
from tests.conftest import schedule_rows


def frame() -> pd.DataFrame:
    games = nflverse.parse_games(schedule_rows(), 2018)
    for g in games:
        g["home_ml"], g["away_ml"] = g.pop("_home_ml"), g.pop("_away_ml")
        g["spread_line"], g["total_line"] = g.pop("_spread"), g.pop("_total")
    return games_frame(games)


def mini(rows: list[tuple]) -> pd.DataFrame:
    """rows: (home, away, home_score, away_score, status), already in kickoff order."""
    return pd.DataFrame(rows, columns=["home_team", "away_team", "home_score", "away_score", "status"])


def preds(actual: list[tuple], **by_method: list[tuple]) -> pd.DataFrame:
    out = pd.DataFrame(actual, columns=["home_score", "away_score"]).astype(float)
    for method, pairs in by_method.items():
        out[f"pred_{method}_home"] = [float(h) for h, _ in pairs]
        out[f"pred_{method}_away"] = [float(a) for _, a in pairs]
    return out


# ---- S1: line-implied score ----


def test_s1_implied_score_splits_the_total_by_the_spread_home_favoured_when_positive():
    assert scores.implied_score(3, 45.5) == (24.25, 21.25)  # (45.5 + 3) / 2, (45.5 - 3) / 2
    assert scores.implied_score(-7, 40) == (16.5, 23.5)  # road team favoured by 7
    assert scores.implied_score(0, 41) == (20.5, 20.5)
    assert scores.implied_score(40, 40) == (40.0, 0.0)  # spread as large as the total is still a real score


@pytest.mark.parametrize(
    ("spread", "total"),
    [
        (None, 45.5),
        (3, None),
        (float("nan"), 45.5),
        (3, float("nan")),
        (float("inf"), 45.5),
        (3, float("inf")),
        (3, 0),
        (0, 0),
        (3, -45.5),
        (46, 45.5),  # would give the road team a negative score
        (-46, 45.5),
    ],
)
def test_s1_implied_score_is_missing_when_the_line_is_missing_or_impossible(spread, total):
    assert scores.implied_score(spread, total) is None


# ---- S2: the whole number that is typed into Yahoo ----


def test_s2_entry_rounds_half_up_and_never_goes_below_zero():
    assert scores.entry(24.25) == 24
    assert scores.entry(23.75) == 24
    assert scores.entry(23.5) == 24
    assert scores.entry(22.5) == 23  # Python's round() would give 22
    assert scores.entry(0.49) == 0
    assert scores.entry(-0.2) == 0
    assert scores.entry(-12.0) == 0
    assert isinstance(scores.entry(24.25), int)


def test_s2_entry_pair_keeps_a_whole_number_total_when_both_halves_end_in_point_five():
    assert scores.entry_pair(24.25, 21.25) == (24, 21)
    assert scores.entry_pair(23.75, 23.75) == (24, 24)
    assert scores.entry_pair(23.5, 20.25) == (24, 20)  # only one half: plain rounding
    assert scores.entry_pair(20.25, 23.5) == (20, 24)
    # both halves: the home team rounds up, the road team rounds down, so 44 stays 44
    assert scores.entry_pair(23.5, 20.5) == (24, 20)
    assert scores.entry_pair(21.5, 23.5) == (22, 23)  # home rounds up even as the underdog
    assert scores.entry_pair(22.5, 22.5) == (23, 22)
    assert scores.entry_pair(0.5, 0.5) == (1, 0)
    assert scores.entry_pair(-3.0, 50.2) == (0, 50)
    assert all(isinstance(v, int) for v in scores.entry_pair(23.5, 20.5))


# ---- S3: the answer the app gives today ----


def test_s3_tiebreak_score_is_the_rounded_line_implied_score_and_says_so():
    assert scores.tiebreak_score(3, 45.5) == {"home": 24, "away": 21, "method": "line_implied"}
    assert scores.tiebreak_score(-2, 45) == {"home": 22, "away": 23, "method": "line_implied"}  # 21.5, 23.5
    assert scores.tiebreak_score(3, 44) == {"home": 24, "away": 20, "method": "line_implied"}  # 23.5, 20.5
    assert scores.tiebreak_score(None, 45.5) is None
    assert scores.tiebreak_score(3, float("nan")) is None


# ---- S4, S5: scoring form (points for and against before kickoff) ----

FORM_ROWS = [
    ("A", "B", 20, 10, "final"),
    ("B", "A", 30, 14, "final"),
    ("A", "C", 7, 3, "final"),
    ("C", "A", None, None, "scheduled"),
    ("A", "B", 40, 0, "final"),
]


def test_s4_scoring_form_is_the_mean_of_points_for_and_against_in_earlier_finished_games():
    form = scores.scoring_form(mini(FORM_ROWS))
    assert set(form) == {"home_pf", "home_pa", "away_pf", "away_pa"}
    # game 1: nobody has played
    assert all(math.isnan(form[k][0]) for k in form)
    # game 2: B (home) scored 10 and allowed 20; A (away) scored 20 and allowed 10
    assert [form[k][1] for k in ("home_pf", "home_pa", "away_pf", "away_pa")] == [10, 20, 20, 10]
    # game 3: A scored 20 and 14 (mean 17), allowed 10 and 30 (mean 20); C has not played
    assert (form["home_pf"][2], form["home_pa"][2]) == (17, 20)
    assert math.isnan(form["away_pf"][2]) and math.isnan(form["away_pa"][2])
    # game 4: C scored 3 and allowed 7; A scored 20, 14, 7 (41/3) and allowed 10, 30, 3 (43/3)
    assert (form["home_pf"][3], form["home_pa"][3]) == (3, 7)
    assert form["away_pf"][3] == pytest.approx(41 / 3) and form["away_pa"][3] == pytest.approx(43 / 3)
    # game 5: the unplayed game 4 adds nothing. B scored 10 and 30 (20), allowed 20 and 14 (17)
    assert form["home_pf"][4] == pytest.approx(41 / 3) and form["home_pa"][4] == pytest.approx(43 / 3)
    assert (form["away_pf"][4], form["away_pa"][4]) == (20, 17)


def test_s4_scoring_form_uses_only_the_last_n_games_and_n_is_16():
    assert scores.FORM_GAMES == 16
    form = scores.scoring_form(mini(FORM_ROWS), games=2)
    # A's last two finished games before game 5: scored 14 and 7 (10.5), allowed 30 and 3 (16.5)
    assert (form["home_pf"][4], form["home_pa"][4]) == (10.5, 16.5)


def test_s4_a_final_game_with_a_missing_score_is_not_counted():
    rows = [*FORM_ROWS]
    rows[2] = ("A", "C", 7, None, "final")
    form = scores.scoring_form(mini(rows))
    assert (form["home_pf"][4], form["home_pa"][4]) == (17, 20)  # games 1 and 2 only
    assert math.isnan(form["home_pf"][3])  # C still has no counted game


def test_s4_a_scheduled_game_that_carries_scores_is_not_counted():
    rows = [*FORM_ROWS]
    rows[0] = ("A", "B", 20, 10, "scheduled")
    form = scores.scoring_form(mini(rows))
    # Before game 3, A's scheduled result is ignored; only the final B-over-A game counts.
    assert (form["home_pf"][2], form["home_pa"][2]) == (14, 30)
    assert math.isnan(form["away_pf"][2]) and math.isnan(form["away_pa"][2])
    # Before game 2, B has only the scheduled game, so its form is missing.
    assert math.isnan(form["home_pf"][1]) and math.isnan(form["home_pa"][1])


def test_s5_scoring_form_never_sees_its_own_or_later_results():
    df = frame()
    base = scores.add_score_features(df, EloParams())
    i = len(df) // 2
    changed = df.copy()
    changed.loc[i:, ["home_score", "away_score"]] = changed.loc[i:, ["home_score", "away_score"]] + 9
    after = scores.add_score_features(changed, EloParams())
    cols = ["home_pf", "home_pa", "away_pf", "away_pa"]
    assert np.allclose(base.loc[:i, cols], after.loc[:i, cols], equal_nan=True)
    assert not np.allclose(base.loc[i + 1 :, cols], after.loc[i + 1 :, cols], equal_nan=True)


# ---- S6: feature frame ----


def test_s6_add_score_features_adds_the_implied_score_and_keeps_missing_missing():
    df = frame()
    df.loc[0, "spread_line"] = -7.0
    df.loc[0, "total_line"] = 40.0
    df.loc[1, "spread_line"] = np.nan
    df.loc[2, "total_line"] = np.nan
    f = scores.add_score_features(df, EloParams())
    assert (f.loc[0, "implied_home"], f.loc[0, "implied_away"]) == (16.5, 23.5)
    assert (f.loc[3, "implied_home"], f.loc[3, "implied_away"]) == (24.25, 21.25)  # fixture line: 3 and 45.5
    assert f.loc[[1, 2], ["implied_home", "implied_away"]].isna().all().all()
    for col in (*scores.STATS_FEATURES, *scores.BLEND_FEATURES):
        assert col in f.columns
    assert scores.BLEND_FEATURES == ["implied_home", "implied_away", *scores.STATS_FEATURES]
    assert scores.STATS_FEATURES == [
        "elo_diff", "home_field", "home_qb_change", "away_qb_change", "home_pf", "home_pa", "away_pf", "away_pa"
    ]


# ---- S7: the score model ----


def linear_rows() -> pd.DataFrame:
    xs = [(0, 0), (1, 0), (0, 1), (2, 1), (1, 3), (4, 2)]
    df = pd.DataFrame(xs, columns=["x", "z"]).astype(float)
    df["home_score"] = 2 * df["x"] + 3 * df["z"] + 1
    df["away_score"] = -df["x"] + 0.5 * df["z"] + 20
    df["status"] = "final"
    return df


def test_s7_score_model_fits_home_and_away_points_by_least_squares():
    m = scores.ScoreModel.fit(linear_rows(), ["x", "z"])
    assert m.features == ["x", "z"]
    assert m.home_coef == pytest.approx([2, 3]) and m.home_intercept == pytest.approx(1)
    assert m.away_coef == pytest.approx([-1, 0.5]) and m.away_intercept == pytest.approx(20)
    home, away = m.predict(pd.DataFrame({"x": [1.0, 3.0], "z": [2.0, 0.0]}))
    assert home == pytest.approx([9, 7]) and away == pytest.approx([20, 17])


def test_s7_fit_ignores_rows_that_are_not_finished_or_have_a_missing_value():
    df = linear_rows()
    extra = pd.DataFrame(
        {
            "x": [5.0, np.nan, 3.0, 2.0],
            "z": [5.0, 1.0, 3.0, 2.0],
            "home_score": [999.0, 50.0, np.nan, 77.0],
            "away_score": [999.0, 50.0, 60.0, np.nan],
            "status": ["scheduled", "final", "final", "final"],
        }
    )
    m = scores.ScoreModel.fit(pd.concat([df, extra], ignore_index=True), ["x", "z"])
    assert m.home_coef == pytest.approx([2, 3]) and m.home_intercept == pytest.approx(1)
    assert m.away_coef == pytest.approx([-1, 0.5]) and m.away_intercept == pytest.approx(20)


def test_s7_a_missing_feature_gives_a_missing_prediction_not_a_number():
    m = scores.ScoreModel.fit(linear_rows(), ["x", "z"])
    home, away = m.predict(pd.DataFrame({"x": [1.0, np.nan], "z": [2.0, 2.0]}))
    assert home[0] == pytest.approx(9) and away[0] == pytest.approx(20)
    assert math.isnan(home[1]) and math.isnan(away[1])


def test_s7_fit_refuses_fewer_rows_than_it_has_numbers_to_find():
    with pytest.raises(ValueError, match="rows"):
        scores.ScoreModel.fit(linear_rows().head(2), ["x", "z"])  # 2 rows, 3 unknowns
    assert scores.ScoreModel.fit(linear_rows().head(3), ["x", "z"]).features == ["x", "z"]  # 3 rows is enough


# ---- S8: walk-forward ----


def test_s8_walk_forward_fits_only_on_the_seasons_before_the_test_season(monkeypatch):
    seen = []
    real_fit = scores.ScoreModel.fit.__func__

    def spy(cls, df, features):
        seen.append((set(df["season"]), list(features)))
        return real_fit(cls, df, features)

    monkeypatch.setattr(scores.ScoreModel, "fit", classmethod(spy))
    f = scores.add_score_features(frame(), EloParams())
    test = sb.predict_season(f, 2021, window=2)
    assert [s for s, _ in seen] == [{2019, 2020}, {2019, 2020}]
    assert sorted(feats for _, feats in seen) == sorted([scores.STATS_FEATURES, scores.BLEND_FEATURES])
    assert set(test["season"]) == {2021}


def test_s8_only_finished_regular_season_games_are_tested():
    df = frame()
    f = scores.add_score_features(df, EloParams())
    full = sb.predict_season(f, 2021, window=2)
    assert len(full) == int(((df["season"] == 2021) & (df["status"] == "final")).sum())
    playoff = df.copy()
    target = playoff[playoff["season"] == 2021].index[-1]
    playoff.loc[target, "game_type"] = "WC"
    fewer = sb.predict_season(scores.add_score_features(playoff, EloParams()), 2021, window=2)
    assert len(fewer) == len(full) - 1 and playoff.loc[target, "game_id"] not in set(fewer["game_id"])
    # 2023 in the fixture: weeks 1-3 are final, weeks 4-5 are not played
    current = sb.predict_season(f, 2023, window=3)
    assert set(current["week"]) == {1, 2, 3} and (current["status"] == "final").all()


def test_s9_predictions_are_whole_number_entries_and_the_line_row_is_the_rounded_implied_score():
    f = scores.add_score_features(frame(), EloParams())
    test = sb.predict_season(f, 2021, window=2)
    assert sb.METHODS == ["implied", "stats", "blend"]
    for method in sb.METHODS:
        for side in ("home", "away"):
            col = test[f"pred_{method}_{side}"]
            assert col.notna().all() and (col == col.round()).all() and (col >= 0).all()
    assert (test["pred_implied_home"] == 24).all() and (test["pred_implied_away"] == 21).all()  # 24.25, 21.25
    # the stats model never reads the line: changing every line leaves its entries alone
    moved = frame()
    moved["spread_line"], moved["total_line"] = -6.0, 38.0
    other = sb.predict_season(scores.add_score_features(moved, EloParams()), 2021, window=2)
    assert (other["pred_stats_home"].to_numpy() == test["pred_stats_home"].to_numpy()).all()
    assert (other["pred_stats_away"].to_numpy() == test["pred_stats_away"].to_numpy()).all()
    assert (other["pred_implied_home"] == 16).all() and (other["pred_implied_away"] == 22).all()  # 16, 22
    moved["spread_line"], moved["total_line"] = 3.0, 44.0  # 23.5 and 20.5: the pair rule keeps the total at 44
    halves = sb.predict_season(scores.add_score_features(moved, EloParams()), 2021, window=2)
    assert (halves["pred_implied_home"] == 24).all() and (halves["pred_implied_away"] == 20).all()


# ---- S10, S11: the error table and the ship rule ----

ACTUAL = [(20, 20), (30, 10), (17, 24), (27, 24)]
IMPLIED = [(22, 18), (27, 14), (20, 21), (24, 23)]
STATS = [(21, 21), (30, 10), (17, 24), (27, 24)]
BLEND = [(20, 20), (28, 12), (18, 23), (26, 24)]


def test_s10_summary_reports_team_score_error_and_total_points_error_by_hand():
    report = sb.summary(preds(ACTUAL, implied=IMPLIED, stats=STATS, blend=BLEND))
    assert report["games"] == 4
    rows = {r["method"]: r for r in report["methods"]}
    assert list(rows) == ["implied", "stats", "blend"]
    assert all(isinstance(r["label"], str) and r["label"] for r in rows.values())
    # team error per game = (home miss + road miss) / 2
    # implied: 2, 3.5, 3, 2 -> 2.625; totals 40/41/41/47 against 40/40/41/51 -> 0, 1, 0, 4 -> 1.25
    assert (rows["implied"]["team_mae"], rows["implied"]["total_mae"]) == (2.625, 1.25)
    # stats: 1, 0, 0, 0 -> 0.25; total misses 2, 0, 0, 0 -> 0.5
    assert (rows["stats"]["team_mae"], rows["stats"]["total_mae"]) == (0.25, 0.5)
    # blend: 0, 2, 1, 0.5 -> 0.875; total misses 0, 0, 0, 1 -> 0.25
    assert (rows["blend"]["team_mae"], rows["blend"]["total_mae"]) == (0.875, 0.25)
    comp = {c["candidate"]: c for c in report["comparisons"]}
    assert list(comp) == ["stats", "blend"]
    # gain = line error - candidate error, so a positive gain means the candidate was closer
    assert (comp["stats"]["team_mae_gain"], comp["stats"]["total_mae_gain"]) == (2.375, 0.75)
    assert (comp["blend"]["team_mae_gain"], comp["blend"]["total_mae_gain"]) == (1.75, 1.0)
    assert comp["stats"]["team_ci"] == list(bootstrap_ci(np.array([1, 3.5, 3, 2])))
    assert comp["stats"]["total_ci"] == list(bootstrap_ci(np.array([-2.0, 1, 0, 4])))
    assert comp["blend"]["team_ci"] == list(bootstrap_ci(np.array([2, 1.5, 2, 1.5])))
    # both are closer in every game, but four games are far too few to ship anything (S11)
    assert comp["stats"]["wins"] is False and comp["blend"]["wins"] is False
    assert sb.pick_winner(report["comparisons"]) is None


def test_s11_with_enough_games_both_candidates_win_and_the_bigger_team_gain_is_picked():
    k = 50  # the same four games fifty times: 200 games
    report = sb.summary(preds(ACTUAL * k, implied=IMPLIED * k, stats=STATS * k, blend=BLEND * k))
    comp = {c["candidate"]: c for c in report["comparisons"]}
    assert report["games"] == 200 == sb.MIN_SHIP_GAMES
    assert (comp["stats"]["team_mae_gain"], comp["blend"]["team_mae_gain"]) == (2.375, 1.75)
    assert comp["stats"]["wins"] is True and comp["blend"]["wins"] is True
    assert sb.pick_winner(report["comparisons"]) == "stats"


def test_s11_one_game_short_of_the_minimum_does_not_ship():
    actual, line, cand = [(20, 20)] * 199, [(23, 19)] * 199, [(21, 21)] * 199
    report = sb.summary(preds(actual, implied=line, stats=line, blend=cand))
    blend = next(c for c in report["comparisons"] if c["candidate"] == "blend")
    assert blend["team_ci"] == [1.0, 1.0] and blend["total_mae_gain"] == 0.0 and blend["wins"] is False
    assert sb.pick_winner(report["comparisons"]) is None


def test_s11_a_candidate_that_is_closer_on_team_scores_but_worse_on_total_points_does_not_ship():
    n = 200
    # actual 20-20; line 22-18 (team miss 2, total miss 0); stats 21-21 (team miss 1, total miss 2)
    report = sb.summary(preds([(20, 20)] * n, implied=[(22, 18)] * n, stats=[(21, 21)] * n, blend=[(22, 18)] * n))
    comp = {c["candidate"]: c for c in report["comparisons"]}
    assert comp["stats"]["team_ci"] == [1.0, 1.0] and comp["stats"]["total_mae_gain"] == -2.0
    assert comp["stats"]["wins"] is False
    # blend is the line itself: zero gain is not a win
    assert comp["blend"]["team_ci"] == [0.0, 0.0] and comp["blend"]["wins"] is False
    assert sb.pick_winner(report["comparisons"]) is None


def test_s11_a_clear_team_score_win_with_equal_total_points_error_ships():
    n = 200
    # actual 20-20; line 23-19 (team miss 2, total miss 2); blend 21-21 (team miss 1, total miss 2)
    report = sb.summary(preds([(20, 20)] * n, implied=[(23, 19)] * n, stats=[(23, 19)] * n, blend=[(21, 21)] * n))
    comp = {c["candidate"]: c for c in report["comparisons"]}
    assert comp["blend"]["total_mae_gain"] == 0.0 and comp["blend"]["wins"] is True
    assert sb.pick_winner(report["comparisons"]) == "blend"


def test_s11_a_better_average_whose_interval_includes_zero_does_not_ship():
    # even games: line 30-30 (team miss 10), stats 26-26 (team miss 6): +4
    # odd games: line 20-20 (exact), stats 24-24 (team miss 4): -4.  Mean gain just above zero, interval spans zero.
    implied = [(30, 30), (20, 20)] * 100
    stats = [(26, 26), (24, 24)] * 100  # even games +4, odd games -4 ... plus two games that tip the mean
    stats[0], stats[2] = (20, 20), (20, 20)  # +10 twice: mean gain = (98 * 4 + 20 - 100 * 4) / 200 = +0.06
    report = sb.summary(preds([(20, 20)] * 200, implied=implied, stats=stats, blend=implied))
    stat = next(c for c in report["comparisons"] if c["candidate"] == "stats")
    assert stat["team_mae_gain"] == pytest.approx(0.06) and stat["total_mae_gain"] == pytest.approx(0.12)
    assert stat["team_ci"][0] < 0 < stat["team_ci"][1]
    assert stat["wins"] is False and sb.pick_winner(report["comparisons"]) is None


def test_s10_summary_of_no_games_reports_missing_not_a_number():
    report = sb.summary(preds([], implied=[], stats=[], blend=[]))
    assert report["games"] == 0
    assert all(r["team_mae"] is None and r["total_mae"] is None for r in report["methods"])
    for c in report["comparisons"]:
        assert c["team_mae_gain"] is None and c["total_mae_gain"] is None
        assert c["team_ci"] == [None, None] and c["total_ci"] == [None, None] and c["wins"] is False
    assert sb.pick_winner(report["comparisons"]) is None


def test_s10_summary_refuses_a_missing_prediction_or_score():
    good = preds(ACTUAL, implied=IMPLIED, stats=STATS, blend=BLEND)
    for col in ("pred_blend_away", "home_score"):
        bad = good.copy()
        bad.loc[1, col] = np.nan
        with pytest.raises(ValueError, match="missing"):
            sb.summary(bad)


# ---- S12: the two tiebreak slots ----


@pytest.mark.parametrize(
    ("weekday", "kickoff", "expected"),
    [
        ("Sunday", datetime(2024, 11, 11, 1, 20, tzinfo=UTC), True),  # Sunday 8:20 pm Eastern (winter)
        ("Sunday", datetime(2024, 9, 8, 20, 25, tzinfo=UTC), False),  # Sunday 4:25 pm Eastern (summer)
        ("Sunday", datetime(2024, 9, 8, 23, 0, tzinfo=UTC), True),  # Sunday 7:00 pm Eastern
        ("Sunday", datetime(2024, 9, 8, 22, 59, tzinfo=UTC), False),  # Sunday 6:59 pm Eastern
        ("Monday", datetime(2024, 9, 10, 0, 15, tzinfo=UTC), True),  # Monday 8:15 pm Eastern
        ("Monday", datetime(2024, 9, 9, 23, 15, tzinfo=UTC), True),  # Monday 7:15 pm Eastern (early game)
        ("Monday", datetime(2024, 9, 9, 21, 0, tzinfo=UTC), True),  # Monday 5:00 pm Eastern: any Monday game
        ("Thursday", datetime(2024, 9, 6, 0, 15, tzinfo=UTC), False),
        ("Saturday", datetime(2024, 12, 22, 1, 15, tzinfo=UTC), False),
    ],
)
def test_s12_tiebreak_slot_is_sunday_night_or_monday_in_eastern_time(weekday, kickoff, expected):
    assert sb.is_tiebreak_slot(weekday, kickoff) is expected


# ---- S13, S14: the whole run ----


def test_s13_backtest_report_on_the_fixture_matches_an_independent_count():
    df = frame()
    report = sb.run_score_backtest(df, [2021, 2022], window=3)
    keys = {"seasons", "games", "methods", "comparisons", "by_season", "tiebreak_slots", "ships", "excluded"}
    assert set(report) == keys
    assert report["excluded"] == 0
    tested = df[df["season"].isin([2021, 2022]) & (df["status"] == "final") & (df["game_type"] == "REG")]
    assert report["seasons"] == [2021, 2022] and report["games"] == len(tested) > 0
    # the fixture line is 3 and 45.5 for every game, so the line entry is 24-21 everywhere
    miss = ((tested["home_score"] - 24).abs() + (tested["away_score"] - 21).abs()) / 2
    total_miss = (tested["home_score"] + tested["away_score"] - 45).abs()
    line = report["methods"][0]
    assert line["method"] == "implied"
    assert line["team_mae"] == pytest.approx(miss.mean()) and line["total_mae"] == pytest.approx(total_miss.mean())
    assert [r["season"] for r in report["by_season"]] == [2021, 2022]
    assert sum(r["n"] for r in report["by_season"]) == report["games"]
    for row in report["by_season"]:
        season_miss = miss[tested["season"] == row["season"]]
        assert row["n"] == len(season_miss)
        assert row["implied"]["team_mae"] == pytest.approx(season_miss.mean())
        assert set(row) == {"season", "n", "implied", "stats", "blend"}
    slots = [sb.is_tiebreak_slot(w, k) for w, k in zip(tested["weekday"], tested["kickoff_utc"], strict=True)]
    assert set(report["tiebreak_slots"]) == {"games", "methods", "comparisons"}
    assert report["tiebreak_slots"]["games"] == sum(slots)
    assert report["ships"] == sb.pick_winner(report["comparisons"])
    assert report["ships"] in (None, "stats", "blend")
    assert json.loads(json.dumps(report)) == report  # plain numbers and lists only
    assert sb.run_score_backtest(df, [2021, 2022], window=3) == report  # same answer every run


def test_s14_every_method_is_compared_on_the_same_games():
    df = frame()
    base = sb.run_score_backtest(df, [2022], window=3)
    target = df[(df["season"] == 2022) & (df["status"] == "final")].index[0]
    df.loc[target, "spread_line"] = np.nan  # no line: the stats model still has a number, the line does not
    report = sb.run_score_backtest(df, [2022], window=3)
    assert report["games"] == base["games"] - 1
    assert report["by_season"][0]["n"] == base["games"] - 1
    assert (base["excluded"], report["excluded"]) == (0, 1)  # the report says how many games were left out


def test_s13_the_run_puts_games_in_kickoff_order_itself():
    df = frame()
    shuffled = df.sample(frac=1, random_state=3).reset_index(drop=True)
    in_order = sb.run_score_backtest(df, [2021, 2022], window=3)
    assert sb.run_score_backtest(shuffled, [2021, 2022], window=3) == in_order


@pytest.mark.parametrize("seasons", [[], [2022, 2022]])
def test_s13_an_empty_or_repeated_season_list_is_refused(seasons):
    with pytest.raises(ValueError, match="seasons"):
        sb.run_score_backtest(frame(), seasons, window=3)


# ---- S15: no file, network or database access in the new modules ----


def test_s15_the_new_modules_do_no_file_network_or_database_access():
    root = Path(scores.__file__).resolve().parents[1]
    for rel in ("predictions/scores.py", "analytics/score_backtest.py"):
        text = (root / rel).read_text()
        for banned in ("sqlalchemy", "httpx", "requests", "urllib", "open(", "os.environ", "subprocess", "socket"):
            assert banned not in text, f"{rel} uses {banned}"


# ---- S8, S11, S13: what the whole run is built from ----


def test_s8_s11_the_run_uses_default_elo_a_ten_season_window_and_decides_on_all_games(monkeypatch):
    calls = {"elo": [], "window": [], "decided_on": []}
    real_features, real_season, real_pick = sb.add_score_features, sb.predict_season, sb.pick_winner

    def features(df, elo):
        calls["elo"].append(elo)
        return real_features(df, elo)

    def season(frame_, season_, window):
        calls["window"].append(window)
        return real_season(frame_, season_, window)

    def pick(comparisons):
        calls["decided_on"].append(comparisons)
        return real_pick(comparisons)

    monkeypatch.setattr(sb, "add_score_features", features)
    monkeypatch.setattr(sb, "predict_season", season)
    monkeypatch.setattr(sb, "pick_winner", pick)
    df = frame()
    # the fixture's weekdays depend on today's date, so pin them: one tested game on Monday, the rest on Thursday
    df["weekday"] = "Thursday"
    target = df[(df["season"] == 2022) & (df["status"] == "final")].index[0]
    df.loc[target, "weekday"] = "Monday"
    report = sb.run_score_backtest(df, [2021, 2022])
    assert calls["elo"] == [EloParams()]
    assert calls["window"] == [10, 10]
    assert report["tiebreak_slots"]["games"] == 1 < report["games"]
    assert calls["decided_on"] == [report["comparisons"]]
    assert report["comparisons"] != report["tiebreak_slots"]["comparisons"]
