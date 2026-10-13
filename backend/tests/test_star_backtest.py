"""Step 8b: the star-out challenger. Clause ids (L, F, P) are frozen in docs/gauntlet/logs/step-8b.md."""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from nflpi.analytics import star_backtest as sb
from nflpi.analytics.backtest import candidate_preds
from nflpi.ingestion import nflverse
from nflpi.predictions.features import BLEND_FEATURES
from nflpi.predictions.model import LogitModel
from tests.test_model import _flip_scores, frame

REPORT_COLUMNS = ["star_out_diff", "star_out_w_diff", "qb_out_diff"]
RESERVE_COLUMNS = ["star_res_diff", "star_res_w_diff"]


def _stat(season, pid, position="WR", week=1, season_type="REG", **values) -> dict:
    return {"season": season, "week": week, "season_type": season_type, "player_id": pid, "position": position,
            **dict.fromkeys(nflverse.STAR_STATS, 0.0), **values}


def _report(season, week, team, pid, status="Out", modified=None) -> dict:
    return {"season": season, "week": week, "team": team, "player_id": pid, "status": status, "modified": modified}


def _roster(season, week, team, pid, status="RES") -> dict:
    return {"season": season, "week": week, "team": team, "player_id": pid, "status": status}


def _stats_2021() -> list[dict]:
    """Offence: h1 100 points, h2 50 (mean 75). Defence: a1 60, a2 20 (mean 40). Quarterbacks: hq, aq."""
    return [
        _stat(2021, "h1", receiving_yards=1000.0),
        _stat(2021, "h2", "RB", rushing_yards=500.0),
        _stat(2021, "a1", "LB", def_tackles_solo=60.0),
        _stat(2021, "a2", "CB", def_tackles_solo=20.0),
        _stat(2021, "hq", "QB", attempts=400.0),
        _stat(2021, "aq", "QB", attempts=300.0),
    ]


def _game(df: pd.DataFrame) -> pd.Series:
    return df[(df["season"] == 2022) & (df["week"] == 2)].iloc[0]


def _at(df, stats, reports, roster=None) -> pd.Series:
    """The feature row of the 2022 week 2 game under test."""
    return sb.star_out_features(df, stats, reports, roster).loc[_game(df).name]


def test_league_stars_rank_one_finished_regular_season(monkeypatch):
    monkeypatch.setattr(sb, "STAR_LIMITS", {"qb": 1, "off": 2, "def": 1})
    rows = [
        _stat(2021, "q1", "QB", week=1, attempts=200.0), _stat(2021, "q1", "QB", week=2, attempts=100.0),
        _stat(2021, "q2", "QB", attempts=250.0),
        _stat(2021, "q3", "QB", rushing_yards=2000.0),  # no pass attempt: not a quarterback star, never an offence star
        _stat(2021, "w1", receiving_yards=1000.0, receiving_tds=5.0, receptions=80.0),  # 100 + 30 + 40 = 170
        _stat(2021, "r1", "RB", rushing_yards=800.0, rushing_tds=10.0, receptions=20.0),  # 80 + 60 + 10 = 150
        _stat(2021, "w2", receiving_yards=600.0),  # 60: third on offence, over the limit
        _stat(2021, "w2", week=19, season_type="POST", receiving_yards=5000.0),  # playoffs do not count
        _stat(2021, "d1", "LB", def_tackles_solo=50.0, def_tackles_with_assist=10.0, def_tackle_assists=20.0,
              def_sacks=5.0, def_qb_hits=4.0, def_tackles_for_loss=6.0, def_interceptions=1.0,
              def_pass_defended=2.0, def_fumbles_forced=1.0, def_tds=1.0, def_safeties=1.0),  # 144
        _stat(2021, "d2", "CB", def_tackles_solo=40.0),
        _stat(2021, "x1", receiving_yards=100.0, def_tackles_solo=20.0),  # defence side (20 beats 10), not a star
        _stat(2020, "old", receiving_yards=9000.0),  # another season has its own list
    ]
    stars = sb.league_stars(rows)
    assert set(stars) == {2020, 2021}
    assert stars[2020] == {"old": ("off", 1.0)}
    got = stars[2021]
    assert set(got) == {"q1", "w1", "r1", "d1"}
    assert got["q1"] == ("qb", 1.0) and got["d1"] == ("def", 1.0)
    assert got["w1"][0] == got["r1"][0] == "off"
    assert got["w1"][1] == pytest.approx(170 / 160) and got["r1"][1] == pytest.approx(150 / 160)

    # The real limits, and the point values written out in the frozen clause.
    monkeypatch.undo()
    assert sb.STAR_LIMITS == {"qb": 32, "off": 64, "def": 64}
    wide = sb.league_stars(rows + [_stat(2021, "zero", "TE")])[2021]
    assert "zero" not in wide and "q3" not in wide  # no production, no star
    assert wide["x1"][0] == "def" and wide["w2"] == ("off", pytest.approx(60 / ((170 + 150 + 60) / 3)))
    assert wide["d1"][1] == pytest.approx(144 / ((144 + 40 + 20) / 3))


def test_league_stars_break_ties_by_id_and_take_the_position_of_the_latest_week(monkeypatch):
    monkeypatch.setattr(sb, "STAR_LIMITS", {"qb": 1, "off": 1, "def": 1})
    rows = [
        _stat(2021, "b", receiving_yards=500.0), _stat(2021, "a", receiving_yards=500.0),
        _stat(2021, "m", "WR", week=1, attempts=10.0), _stat(2021, "m", "QB", week=5, attempts=10.0),
        _stat(2021, "n", "QB", week=1, attempts=30.0), _stat(2021, "n", "WR", week=6, receiving_yards=10.0),
    ]
    got = sb.league_stars(rows)[2021]
    assert got == {"a": ("off", 1.0), "m": ("qb", 1.0)}  # n ended the season as a receiver with 1 point


def test_stars_come_only_from_the_season_before_the_game():
    df = frame()
    game = _game(df)
    reports = [_report(2022, 2, game.home_team, "h1"), _report(2022, 2, game.away_team, "a1")]
    base = _at(df, _stats_2021(), reports)
    assert base["star_out_diff"] == 0 and base["star_out_w_diff"] == pytest.approx(4 / 3 - 1.5)
    # The game's own season, a later season and an older season never change the list.
    noise = [_stat(season, pid, receiving_yards=9000.0) for season in (2019, 2020, 2022, 2023) for pid in ("h1", "zz")]
    noise += [_stat(2022, "a1", "LB", week=2, def_tackles_solo=900.0)]  # who played in the game's own week
    pd.testing.assert_series_equal(_at(df, _stats_2021() + noise, reports), base)
    # The season before does: a bigger 2021 for someone else pushes h1's weight down.
    moved = _at(df, _stats_2021() + [_stat(2021, "big", receiving_yards=3000.0)], reports)
    assert moved["star_out_w_diff"] == pytest.approx(100 / 150 - 1.5)
    # A 2021 star list says nothing about 2023 games (that needs 2022), whatever was reported.
    later = sb.star_out_features(df, _stats_2021(), reports + [_report(2023, 1, game.home_team, "h1")])
    assert later.loc[df["season"] == 2023, REPORT_COLUMNS].isna().all().all()


def test_a_star_is_out_only_on_an_out_or_doubtful_report_for_that_team_and_week():
    df = frame()
    game = _game(df)
    home, away = game.home_team, game.away_team
    week2 = df[(df["season"] == 2022) & (df["week"] == 2)]
    reverse, third = week2.iloc[1], week2.iloc[2]  # the same two clubs with sides swapped; two other clubs
    assert (reverse.home_team, reverse.away_team) == (away, home)
    assert not {third.home_team, third.away_team} & {home, away}
    other = third.home_team
    reports = [
        _report(2022, 2, home, "h1"), _report(2022, 2, home, "h2", "Doubtful"),
        _report(2022, 2, home, "h1", "OUT"),  # the same player twice counts once
        _report(2022, 2, home, "nobody"),  # not a star
        _report(2022, 2, away, "a1", "Questionable"), _report(2022, 2, away, "a2", ""),
        _report(2022, 2, away, "a2", "Probable"), _report(2022, 2, away, "a2", None),
        _report(2022, 3, away, "a1"), _report(2022, 1, away, "a1"),  # another week
        _report(2021, 2, away, "a1"), _report(2023, 2, away, "a1"),  # another season
        _report(2022, 2, other, "a1"),  # listed by a club that is not in this game
    ]
    got = _at(df, _stats_2021(), reports)
    assert sb.REPORT_OUT == {"out", "doubtful"}
    assert got["star_out_diff"] == 2 and got["star_out_w_diff"] == pytest.approx(2.0) and got["qb_out_diff"] == 0
    assert list(sb.star_out_features(df, _stats_2021(), reports).columns) == REPORT_COLUMNS
    # The away club's star goes out: home minus away.
    got = _at(df, _stats_2021(), reports + [_report(2022, 2, away, "a1", "out")])
    assert got["star_out_diff"] == 1 and got["star_out_w_diff"] == pytest.approx(2.0 - 1.5)
    # The row for the other club counts in that club's own week 2 game, and only there.
    feats = sb.star_out_features(df, _stats_2021(), reports)
    assert feats.loc[third.name, "star_out_diff"] == 1
    assert feats.loc[third.name, "star_out_w_diff"] == pytest.approx(1.5)
    # Home minus away: the same two clubs with the sides swapped give the opposite sign.
    assert feats.loc[reverse.name, "star_out_diff"] == -2
    assert feats.loc[reverse.name, "star_out_w_diff"] == pytest.approx(-2.0)


def test_a_report_changed_at_or_after_kickoff_is_not_used():
    df = frame()
    game = _game(df)
    stats = _stats_2021()
    seen = [_report(2022, 2, game.away_team, "a2")]  # keeps the week known
    before = _report(2022, 2, game.home_team, "h1", modified=game.kickoff_utc - timedelta(seconds=1))
    at = _report(2022, 2, game.home_team, "h1", modified=game.kickoff_utc)
    after = _report(2022, 2, game.home_team, "h1", modified=game.kickoff_utc + timedelta(hours=3))
    assert _at(df, stats, seen)["star_out_diff"] == -1
    assert _at(df, stats, seen + [before])["star_out_diff"] == 0
    assert _at(df, stats, seen + [at])["star_out_diff"] == -1
    assert _at(df, stats, seen + [after])["star_out_diff"] == -1
    assert _at(df, stats, seen + [_report(2022, 2, game.home_team, "h1", modified=None)])["star_out_diff"] == 0


def test_the_quarterback_is_counted_apart():
    df = frame()
    game = _game(df)
    reports = [_report(2022, 2, game.home_team, "h1")]
    base = _at(df, _stats_2021(), reports)
    assert base["qb_out_diff"] == 0 and base["star_out_diff"] == 1
    got = _at(df, _stats_2021(), reports + [_report(2022, 2, game.away_team, "aq")])
    assert got["qb_out_diff"] == -1
    assert got["star_out_diff"] == base["star_out_diff"] and got["star_out_w_diff"] == base["star_out_w_diff"]
    got = _at(df, _stats_2021(), reports + [_report(2022, 2, game.home_team, "hq", "Doubtful")])
    assert got["qb_out_diff"] == 1 and got["star_out_diff"] == 1


def test_unknown_stays_missing_and_a_known_empty_report_is_zero():
    df = frame()
    game = _game(df)
    other_game = df[(df["season"] == 2022) & (df["week"] == 2)].iloc[1]
    reports = [_report(2022, 2, other_game.home_team, "nobody", "Questionable")]  # the week has a report
    feats = sb.star_out_features(df, _stats_2021(), reports)
    assert list(feats.index) == list(df.index)
    assert (feats.loc[(df["season"] == 2022) & (df["week"] == 2), REPORT_COLUMNS] == 0).all().all()
    # A week with no report row at all is unknown, not "nobody is out".
    assert feats.loc[(df["season"] == 2022) & (df["week"] != 2), REPORT_COLUMNS].isna().all().all()
    assert feats.loc[df["season"] != 2022, REPORT_COLUMNS].isna().all().all()
    # No star list for the season before (no 2020 stats): unknown even with a report.
    feats = sb.star_out_features(df, _stats_2021(), reports + [_report(2021, 2, game.home_team, "h1")])
    assert feats.loc[df["season"] == 2021, REPORT_COLUMNS].isna().all().all()
    assert sb.star_out_features(df, [], reports)[REPORT_COLUMNS].isna().all().all()
    # A season with playoff rows only has no list at all (an empty list would read as "nobody is out").
    post_only = [_stat(2021, "h1", week=19, season_type="POST", receiving_yards=900.0)]
    assert 2021 not in sb.league_stars(post_only)
    assert sb.star_out_features(df, post_only, reports)[REPORT_COLUMNS].isna().all().all()


def test_reserve_lists_add_to_the_report_from_2016_only(monkeypatch):
    df = frame()
    game = _game(df)
    home, away = game.home_team, game.away_team
    stats = _stats_2021()
    reports = [_report(2022, 2, home, "h1"), _report(2022, 3, home, "h1")]
    assert sb.ROSTER_OUT == {"RES", "PUP", "SUS"} and sb.ROSTER_FIRST_SEASON == 2016
    roster = [
        _roster(2022, 2, home, "h1"),  # on the report as well: counted once
        _roster(2022, 2, home, "h2", "PUP"),
        _roster(2022, 2, away, "a1", "SUS"),
        _roster(2022, 2, away, "a2", "INA"),  # the game-day inactive list is not used
        _roster(2022, 2, away, "aq"),  # quarterbacks are not in these two columns
        _roster(2022, 3, away, "a2"), _roster(2022, 1, away, "a2"), _roster(2021, 2, away, "a2"),
    ]
    feats = sb.star_out_features(df, stats, reports, roster)
    assert list(feats.columns) == REPORT_COLUMNS + RESERVE_COLUMNS
    got = feats.loc[game.name]
    assert got["star_res_diff"] == 2 - 1 and got["star_res_w_diff"] == pytest.approx(2.0 - 1.5)
    assert got["star_out_diff"] == 1 and got["qb_out_diff"] == 0  # the report columns do not move
    for status in ("ACT", "DEV", "CUT", "INA", "", None):
        quiet = [_roster(2022, 2, away, "a2", status), _roster(2022, 2, home, "h1", status)]
        assert sb.star_out_features(df, stats, reports, quiet).loc[game.name, "star_res_diff"] == 1
    # A week with a report but no roster row is unknown for the reserve columns only.
    week3 = (df["season"] == 2022) & (df["week"] == 3)
    only_week2 = [row for row in roster if (row["season"], row["week"]) == (2022, 2)]
    feats = sb.star_out_features(df, stats, reports, only_week2)
    assert feats.loc[week3, RESERVE_COLUMNS].isna().all().all() and feats.loc[week3, "star_out_diff"].notna().all()
    # No report that week: the reserve columns are unknown too.
    assert sb.star_out_features(df, stats, [], roster)[RESERVE_COLUMNS].isna().all().all()
    # Before the first usable season a roster status is not a pregame fact and is never read.
    monkeypatch.setattr(sb, "ROSTER_FIRST_SEASON", 2023)
    feats = sb.star_out_features(df, stats, reports, roster)
    assert np.isnan(feats.loc[game.name, "star_res_diff"]) and feats.loc[game.name, "star_out_diff"] == 1


def test_features_never_read_a_result():
    df = frame()
    game = _game(df)
    stats = _stats_2021() + [_stat(2022, pid, receiving_yards=700.0) for pid in ("h1", "a1")]
    reports = [_report(2022, week, game.home_team, "h1") for week in (1, 2, 3)]
    roster = [_roster(2022, week, game.away_team, "a1") for week in (1, 2, 3)]
    got = sb.star_out_features(df, stats, reports, roster)
    assert got.loc[game.name, "star_res_diff"] == 0 and got.notna().any().all()
    flipped = sb.star_out_features(_flip_scores(df, df["season"] >= 2018), stats, reports, roster)
    pd.testing.assert_frame_equal(flipped, got)
    bare = df[["season", "week", "kickoff_utc", "home_team", "away_team"]]  # no score, no status, no starter
    pd.testing.assert_frame_equal(sb.star_out_features(bare, stats, reports, roster), got)


def _inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Made-up inputs that vary from game to game; the fits only need numbers."""
    i = df.index.to_numpy()
    return pd.DataFrame({
        "star_out_diff": i % 5 - 2.0, "star_out_w_diff": (i % 7 - 3) / 2, "qb_out_diff": i % 3 - 1.0,
        "star_res_diff": i % 4 - 1.5, "star_res_w_diff": (i % 6 - 2.5) / 2,
    }, index=df.index)


def test_star_preds_fit_on_past_seasons_and_keep_the_blend_when_an_input_is_missing(monkeypatch):
    df = frame()
    assert sb.MIN_FIT_SEASONS == 3
    assert sb.STAR_VARIANTS == {
        "p_star_count": ["star_out_diff"],
        "p_star_weighted": ["star_out_w_diff"],
        "p_star_count_qb": ["star_out_diff", "qb_out_diff"],
        "p_star_weighted_qb": ["star_out_w_diff", "qb_out_diff"],
        "p_star_res_count": ["star_res_diff"],
        "p_star_res_weighted": ["star_res_w_diff"],
    }
    inputs = _inputs(df)
    inputs.loc[df["season"] < 2019, RESERVE_COLUMNS] = np.nan  # reserve inputs start in 2019
    missing = df[(df["season"] == 2022) & (df["week"] == 2)].index[0]
    inputs.loc[missing, "star_out_diff"] = np.nan
    # Two games with no price: one to score (it must not be scored) and one to learn from (it must not be used).
    for season, week in ((2022, 3), (2020, 1)):
        df.loc[df[(df["season"] == season) & (df["week"] == week)].index[0], ["home_ml", "away_ml"]] = np.nan
    base = candidate_preds(df, [2021, 2022], window=3)
    assert len(base) == 29
    seen = []
    real_fit = LogitModel.fit.__func__

    def spy(cls, train, features, weights=None):
        seen.append((list(features), train))
        return real_fit(cls, train, features, weights=weights)

    monkeypatch.setattr(LogitModel, "fit", classmethod(spy))
    preds = sb.star_preds(df, [2021, 2022], inputs, window=3)
    # Same games and the same baseline as the step 14 bench.
    assert list(preds["game_id"]) == list(base["game_id"]) and np.allclose(preds["p_blend"], base["p_blend"])
    star_fits = [(features, train) for features, train in seen if set(features) - set(BLEND_FEATURES)]
    # No fit ever sees the test season or a later one, and every row it sees has the input and a price.
    assert all(set(train["season"]) <= {2018, 2019, 2020} or set(train["season"]) <= {2019, 2020, 2021}
               for _, train in seen)
    assert all(train[features].notna().all().all() for features, train in star_fits)
    fitted = [features for features, _ in star_fits]
    for name in ("p_star_count", "p_star_weighted", "p_star_count_qb", "p_star_weighted_qb"):
        assert fitted.count([*BLEND_FEATURES, *sb.STAR_VARIANTS[name]]) == 2  # one fit per test season
    # Reserve inputs: 2021 has two seasons to learn from (2019, 2020), fewer than three, so no fit and the blend's
    # number; 2022 has three (2019 to 2021) and is fitted.
    for name in ("p_star_res_count", "p_star_res_weighted"):
        fits = [train for features, train in star_fits if features == [*BLEND_FEATURES, *sb.STAR_VARIANTS[name]]]
        assert len(fits) == 1 and set(fits[0]["season"]) == {2019, 2020, 2021}
        first, second = preds[preds["season"] == 2021], preds[preds["season"] == 2022]
        assert (first[name] == first["p_blend"]).all() and not np.allclose(second[name], second["p_blend"])
    assert all(preds[name].between(0, 1).all() for name in sb.STAR_VARIANTS)
    # A game with a missing input keeps the blend's number; a number is never invented.
    row = preds.set_index("game_id").loc[df.loc[missing, "game_id"]]
    assert row["p_star_count"] == row["p_blend"] and row["p_star_count_qb"] == row["p_blend"]
    assert row["p_star_weighted"] != row["p_blend"] and row["p_star_res_count"] != row["p_blend"]
    rest = preds[preds["game_id"] != df.loc[missing, "game_id"]]
    assert (rest["p_star_count"] != rest["p_blend"]).all()


def test_star_preds_never_use_a_result_from_the_test_week_or_later():
    df = frame()
    inputs = _inputs(df)
    got = sb.star_preds(df, [2022], inputs, window=3)
    week5 = df.loc[(df["season"] == 2022) & (df["week"] == 5), "kickoff_utc"].min()
    after = sb.star_preds(_flip_scores(df, df["kickoff_utc"] >= week5), [2022], inputs, window=3)
    early = (got["week"] < 5).to_numpy()
    assert early.any() and list(after["game_id"]) == list(got["game_id"])
    assert all(np.allclose(got.loc[early, name], after.loc[early, name]) for name in sb.STAR_VARIANTS)
    # Results of an earlier season do move every variant: that is what it learns from.
    earlier = sb.star_preds(_flip_scores(df, df["season"] == 2021), [2022], inputs, window=3)
    assert all(not np.allclose(got[name], earlier[name]) for name in sb.STAR_VARIANTS)
