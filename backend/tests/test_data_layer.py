"""Data layer (step 18e): as-of frames, input checks, coverage report, bench-only matchup score.

Made-up rows only; no network. Most tests are pure pandas; the last few use the test database.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nflpi.data import asof, checks, coverage, matchup

CUT = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def games_df(*rows: dict) -> pd.DataFrame:
    base = {
        "season": 2026,
        "week": 6,
        "game_type": "REG",
        "home_team": "BUF",
        "away_team": "MIA",
        "home_score": 24.0,
        "away_score": 17.0,
        "status": "final",
        "neutral_site": False,
        "home_qb": "Josh Allen",
        "away_qb": "Tua T",
        "temp_f": 60.0,
        "wind_mph": 5.0,
    }
    return pd.DataFrame([base | r for r in rows])


def snaps_df(*rows: dict) -> pd.DataFrame:
    base = {
        "id": 1,
        "game_id": "G1",
        "kind": "latest",
        "home_moneyline": -150.0,
        "away_moneyline": 130.0,
        "spread_line": 3.0,
        "total_line": 45.5,
        "home_prob_novig": 0.58,
    }
    return pd.DataFrame([base | r for r in rows])


def qbs_df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame([{"id": 1, "game_id": "G1", "side": "home", "qb": "A"} | r for r in rows])


def inj_df(*rows: dict) -> pd.DataFrame:
    base = {
        "id": 1,
        "season": 2026,
        "week": 6,
        "team": "BUF",
        "player_id": "p1",
        "player": "P One",
        "report_status": "Out",
    }
    return pd.DataFrame([base | r for r in rows])


def wx_df(*rows: dict) -> pd.DataFrame:
    base = {
        "id": 1,
        "game_id": "G1",
        "temp_f": 50.0,
        "wind_mph": 8.0,
        "gust_mph": 12.0,
        "precip_prob": 0.1,
        "precip_in": 0.0,
    }
    return pd.DataFrame([base | r for r in rows])


def tables(**kw) -> asof.AsofTables:
    empty = pd.DataFrame()
    parts = {"games": empty, "snapshots": empty, "qb_observations": empty, "injuries": empty, "weather": empty}
    return asof.AsofTables(**(parts | kw))


FUTURE_GAME = {
    "game_id": "G1",
    "kickoff_utc": CUT + 30 * HOUR,
    "home_score": np.nan,
    "away_score": np.nan,
    "status": "scheduled",
}
PLAYED_GAME = {"game_id": "G1", "kickoff_utc": CUT - 30 * HOUR}


# --- as-of: nothing after the cutoff -------------------------------------------------------------------------------


def test_line_observed_after_cutoff_never_appears():
    snaps = snaps_df(
        {"id": 1, "observed_at": CUT - 5 * HOUR, "spread_line": 3.0},
        {"id": 2, "observed_at": CUT + HOUR, "spread_line": 7.0},
    )
    out = asof.asof_lines(snaps, CUT)
    assert out["id"].tolist() == [1]
    assert (out["observed_at"] <= CUT).all()


def test_qb_observed_after_cutoff_never_appears():
    obs = qbs_df({"id": 1, "observed_at": CUT - HOUR, "qb": "Old"}, {"id": 2, "observed_at": CUT + HOUR, "qb": "New"})
    out = asof.asof_qbs(obs, CUT)
    assert out["qb"].tolist() == ["Old"]


def test_injury_observed_after_cutoff_never_appears():
    inj = inj_df(
        {"id": 1, "observed_at": CUT - HOUR, "report_status": "Questionable"},
        {"id": 2, "observed_at": CUT + HOUR, "report_status": "Out"},
    )
    out = asof.asof_injuries(inj, CUT)
    assert out["report_status"].tolist() == ["Questionable"]


def test_weather_observed_after_cutoff_never_appears():
    wx = wx_df(
        {"id": 1, "observed_at": CUT - HOUR, "temp_f": 50.0}, {"id": 2, "observed_at": CUT + HOUR, "temp_f": 10.0}
    )
    out = asof.asof_weather(wx, CUT)
    assert out["temp_f"].tolist() == [50.0]


def test_observation_exactly_at_cutoff_is_included():
    snaps = snaps_df({"id": 1, "observed_at": CUT})
    assert len(asof.asof_lines(snaps, CUT)) == 1


def test_whole_frame_has_no_observed_at_beyond_cutoff():
    games = games_df(FUTURE_GAME)
    t = tables(
        games=games,
        snapshots=snaps_df(
            {"id": 1, "observed_at": CUT - 9 * HOUR},
            {"id": 2, "observed_at": CUT - 2 * HOUR, "spread_line": 4.0},
            {"id": 3, "observed_at": CUT + 2 * HOUR, "spread_line": 9.0},
        ),
        qb_observations=qbs_df(
            {"id": 1, "observed_at": CUT - 3 * HOUR, "qb": "A"}, {"id": 2, "observed_at": CUT + HOUR, "qb": "B"}
        ),
        injuries=inj_df({"id": 1, "observed_at": CUT - HOUR}, {"id": 2, "observed_at": CUT + HOUR, "player_id": "p2"}),
        weather=wx_df({"id": 1, "observed_at": CUT - HOUR}, {"id": 2, "observed_at": CUT + HOUR, "temp_f": 1.0}),
    )
    frame = asof.build_asof_frame(t, CUT)
    stamps = [c for c in frame.columns if c.endswith("observed_at")]
    assert len(frame) == 1 and stamps
    for c in stamps:
        assert frame[c].dropna().le(CUT).all()
    assert frame.loc[0, "spread_line"] == 4.0
    assert frame.loc[0, "home_qb"] == "A"
    assert frame.loc[0, "home_out_count"] == 1
    assert frame.loc[0, "fcst_temp_f"] == 50.0


# --- as-of: results, lines, quarterbacks -----------------------------------------------------------------------------


def test_result_hidden_before_kickoff_plus_lag_and_shown_after():
    kick = CUT - asof.RESULT_LAG + timedelta(minutes=1)  # result lands one minute after the cutoff
    hidden = asof.asof_games(games_df({"game_id": "G1", "kickoff_utc": kick}), CUT)
    shown = asof.asof_games(games_df({"game_id": "G1", "kickoff_utc": kick - timedelta(minutes=2)}), CUT)
    assert hidden.loc[0, ["home_score", "away_score", "temp_f", "wind_mph"]].isna().all()
    assert hidden.loc[0, "status"] == "scheduled"
    assert shown.loc[0, "home_score"] == 24.0 and shown.loc[0, "status"] == "final"


def test_result_visible_when_kickoff_plus_lag_equals_cutoff():
    out = asof.asof_games(games_df({"game_id": "G1", "kickoff_utc": CUT - asof.RESULT_LAG}), CUT)
    assert out.loc[0, "home_score"] == 24.0


def test_asof_games_keeps_every_scheduled_row():
    games = games_df(PLAYED_GAME, FUTURE_GAME | {"game_id": "G2"})
    assert len(asof.asof_games(games, CUT)) == 2


def test_line_age_hours_is_cutoff_minus_observation():
    snaps = snaps_df({"id": 1, "observed_at": CUT - timedelta(hours=7, minutes=30)})
    assert asof.asof_lines(snaps, CUT).loc[0, "line_age_hours"] == pytest.approx(7.5)


def test_latest_line_wins_per_game():
    snaps = snaps_df(
        {"id": 1, "observed_at": CUT - 9 * HOUR, "spread_line": 1.0},
        {"id": 2, "observed_at": CUT - 3 * HOUR, "spread_line": 2.0},
        {"id": 3, "observed_at": CUT - 6 * HOUR, "spread_line": 3.0, "game_id": "G2"},
    )
    out = asof.asof_lines(snaps, CUT).set_index("game_id")
    assert out.loc["G1", "spread_line"] == 2.0 and out.loc["G2", "spread_line"] == 3.0


def test_same_observed_at_picks_the_higher_snapshot_id():
    t = CUT - HOUR
    snaps = snaps_df({"id": 5, "observed_at": t, "spread_line": 1.0}, {"id": 9, "observed_at": t, "spread_line": 2.0})
    assert asof.asof_lines(snaps, CUT).loc[0, "spread_line"] == 2.0


def test_home_spread_is_negated_nflverse_spread_line():
    snaps = snaps_df({"id": 1, "observed_at": CUT - HOUR, "spread_line": 3.5})
    assert asof.asof_lines(snaps, CUT).loc[0, "home_spread"] == -3.5
    assert asof.home_spread_from_nflverse(-7.0) == 7.0
    assert np.isnan(asof.home_spread_from_nflverse(None))
    assert np.isnan(asof.home_spread_from_nflverse(float("nan")))


def test_sign_flip_appears_in_exactly_one_place_in_the_package():
    package = Path(asof.__file__).parent
    hits = [
        (p.name, line)
        for p in package.glob("*.py")
        for line in p.read_text().splitlines()
        if "spread" in line
        and ("-spread" in line.replace(" ", "") or "*-1" in line.replace(" ", ""))
        and not line.lstrip().startswith(("#", '"'))
    ]
    assert len(hits) == 1 and hits[0][0] == "asof.py"


def test_unplayed_game_without_qb_observation_has_missing_qb_not_the_games_table_name():
    frame = asof.build_asof_frame(tables(games=games_df(FUTURE_GAME | {"home_qb": "After The Fact"})), CUT)
    assert pd.isna(frame.loc[0, "home_qb"]) and pd.isna(frame.loc[0, "away_qb"])


def test_unplayed_game_uses_latest_qb_observation_per_side():
    obs = qbs_df(
        {"id": 1, "observed_at": CUT - 9 * HOUR, "qb": "First"},
        {"id": 2, "observed_at": CUT - 2 * HOUR, "qb": "Second"},
        {"id": 3, "observed_at": CUT - 2 * HOUR, "qb": "Visitor", "side": "away"},
    )
    frame = asof.build_asof_frame(tables(games=games_df(FUTURE_GAME), qb_observations=obs), CUT)
    assert frame.loc[0, "home_qb"] == "Second" and frame.loc[0, "away_qb"] == "Visitor"
    assert frame.loc[0, "home_qb_observed_at"] == CUT - 2 * HOUR


def test_played_game_keeps_the_games_table_qb_name():
    obs = qbs_df({"id": 1, "observed_at": CUT - 50 * HOUR, "qb": "Projected"})
    frame = asof.build_asof_frame(tables(games=games_df(PLAYED_GAME), qb_observations=obs), CUT)
    assert frame.loc[0, "home_qb"] == "Josh Allen"
    assert pd.isna(frame.loc[0, "home_qb_observed_at"])


def test_frame_has_one_row_per_game_sorted_by_kickoff_then_id():
    games = games_df(
        {"game_id": "B", "kickoff_utc": CUT + 5 * HOUR},
        {"game_id": "A", "kickoff_utc": CUT + 5 * HOUR},
        {"game_id": "C", "kickoff_utc": CUT + 1 * HOUR},
    )
    snaps = snaps_df(*[{"id": i, "game_id": g, "observed_at": CUT - HOUR} for i, g in enumerate("ABC", 1)])
    frame = asof.build_asof_frame(tables(games=games, snapshots=snaps), CUT)
    assert frame["game_id"].tolist() == ["C", "A", "B"]


def test_out_count_counts_only_out_rows_for_the_week_and_team_and_defaults_to_zero():
    inj = inj_df(
        {"id": 1, "observed_at": CUT - HOUR, "player_id": "p1"},
        {"id": 2, "observed_at": CUT - HOUR, "player_id": "p2"},
        {"id": 3, "observed_at": CUT - HOUR, "player_id": "p3", "report_status": "Questionable"},
        {"id": 4, "observed_at": CUT - 2 * HOUR, "player_id": "p1", "report_status": "Questionable"},
        {"id": 5, "observed_at": CUT - HOUR, "player_id": "p9", "team": "MIA", "week": 5},
    )
    frame = asof.build_asof_frame(tables(games=games_df(FUTURE_GAME), injuries=inj), CUT)
    assert frame.loc[0, "home_out_count"] == 2 and frame.loc[0, "away_out_count"] == 0
    assert frame["home_out_count"].dtype.kind == "i"


def test_naive_cutoff_is_refused():
    with pytest.raises(ValueError, match="tz-aware"):
        asof.build_asof_frame(tables(), datetime(2026, 10, 18, 12, 0))
    with pytest.raises(ValueError, match="tz-aware"):
        asof.asof_lines(snaps_df({"observed_at": CUT}), datetime(2026, 10, 18))


def test_input_frames_are_not_mutated():
    t = tables(
        games=games_df(FUTURE_GAME),
        snapshots=snaps_df({"id": 1, "observed_at": CUT - HOUR}),
        qb_observations=qbs_df({"observed_at": CUT - HOUR}),
        injuries=inj_df({"observed_at": CUT - HOUR}),
        weather=wx_df({"observed_at": CUT - HOUR}),
    )
    before = {k: getattr(t, k).copy() for k in ("games", "snapshots", "qb_observations", "injuries", "weather")}
    asof.build_asof_frame(t, CUT)
    for k, df in before.items():
        pd.testing.assert_frame_equal(getattr(t, k), df)


def test_empty_tables_give_an_empty_frame_with_the_columns():
    frame = asof.build_asof_frame(tables(), CUT)
    assert frame.empty and {"home_qb", "home_out_count", "fcst_temp_f", "home_spread"} <= set(frame.columns)


# --- input checks ---------------------------------------------------------------------------------------------------


def checked_games(*rows: dict) -> pd.DataFrame:
    defaults = [
        {"game_id": "2025_01_MIA_BUF", "season": 2025, "week": 1, "kickoff_utc": datetime(2025, 9, 7, 17, tzinfo=UTC)},
        {"game_id": "2026_01_MIA_BUF", "season": 2026, "week": 1, "kickoff_utc": datetime(2026, 9, 13, 17, tzinfo=UTC)},
    ]
    return games_df(*(rows or defaults))


def test_valid_games_pass_and_report_rows_seasons_and_boundaries():
    report = checks.check_games(checked_games())
    assert report.rows == 2 and report.seasons == [2025, 2026]
    assert set(report.season_boundaries) == {2025, 2026}
    assert report.missing["home_score"].n_missing == 0


def test_duplicate_game_id_is_refused_naming_the_id():
    df = checked_games(
        {"game_id": "DUP", "week": 1, "kickoff_utc": CUT}, {"game_id": "DUP", "week": 2, "kickoff_utc": CUT}
    )
    with pytest.raises(checks.DataCheckError, match="DUP"):
        checks.check_games(df)


def test_same_season_week_and_teams_twice_is_refused():
    df = checked_games({"game_id": "X1"}, {"game_id": "X2"})
    with pytest.raises(checks.DataCheckError, match="appears twice"):
        checks.check_duplicate_games(df)


@pytest.mark.parametrize("code", ["XXX", "OAK"])
def test_unknown_team_code_is_refused_naming_it(code):
    df = checked_games({"game_id": "G1", "home_team": code})
    with pytest.raises(checks.DataCheckError, match=code):
        checks.check_teams(df)


def test_home_equal_to_away_is_refused():
    df = checked_games({"game_id": "G1", "home_team": "BUF", "away_team": "BUF"})
    with pytest.raises(checks.DataCheckError, match="home_team equals away_team"):
        checks.check_teams(df)


def test_missing_required_column_is_refused_naming_it():
    df = checked_games().drop(columns=["neutral_site"])
    with pytest.raises(checks.DataCheckError, match="neutral_site"):
        checks.check_games(df)


@pytest.mark.parametrize("week", [0, 23])
def test_week_outside_one_to_twenty_two_is_refused(week):
    df = checked_games({"game_id": "G1", "week": week, "kickoff_utc": CUT})
    with pytest.raises(checks.DataCheckError, match="week"):
        checks.check_seasons(df)


def test_naive_kickoff_is_refused():
    df = checked_games({"game_id": "G1", "kickoff_utc": datetime(2026, 9, 13, 17)})
    with pytest.raises(checks.DataCheckError, match="tz-aware"):
        checks.check_seasons(df)


def test_overlapping_seasons_are_refused_and_report_boundaries():
    df = checked_games(
        {"game_id": "A", "season": 2025, "kickoff_utc": datetime(2025, 9, 7, 17, tzinfo=UTC)},
        {"game_id": "B", "season": 2025, "kickoff_utc": datetime(2026, 1, 4, 17, tzinfo=UTC)},
        {"game_id": "C", "season": 2026, "kickoff_utc": datetime(2025, 12, 1, 17, tzinfo=UTC)},
    )
    with pytest.raises(checks.DataCheckError, match="overlapping seasons") as err:
        checks.check_seasons(df)
    assert "2025" in str(err.value)


def test_non_integer_season_is_refused():
    df = checked_games({"game_id": "G1", "season": 2025.5, "kickoff_utc": CUT})
    with pytest.raises(checks.DataCheckError, match="season"):
        checks.check_seasons(df)


def test_error_message_shows_at_most_five_examples():
    df = checked_games(*[{"game_id": f"G{i}", "home_team": f"Z{i}", "kickoff_utc": CUT} for i in range(9)])
    with pytest.raises(checks.DataCheckError) as err:
        checks.check_teams(df)
    assert str(err.value).count("'Z") == 5


def test_missing_counts_counts_nan_none_and_empty_string():
    df = pd.DataFrame({"a": [1.0, np.nan, 3.0, 4.0], "b": ["x", None, "", "y"]})
    out = checks.missing_counts(df)
    assert out["a"] == checks.MissingCount(1, 4, 0.25)
    assert out["b"].n_missing == 2 and out["b"].fraction == 0.5
    assert list(checks.missing_counts(df, ["b"])) == ["b"]


def snapshots_ok(**over) -> pd.DataFrame:
    return snaps_df({"observed_at": CUT} | over)


def test_valid_snapshots_pass():
    checks.check_snapshots(snapshots_ok())
    checks.check_snapshots(snapshots_ok(home_moneyline=np.nan))


def test_snapshots_with_naive_observed_at_are_refused():
    with pytest.raises(checks.DataCheckError, match="tz-aware"):
        checks.check_snapshots(snapshots_ok(observed_at=datetime(2026, 10, 18, 12)))


def test_snapshots_with_a_moneyline_of_50_are_refused():
    with pytest.raises(checks.DataCheckError, match="home_moneyline"):
        checks.check_snapshots(snapshots_ok(home_moneyline=50.0))


def test_duplicate_snapshot_key_is_refused():
    df = pd.concat([snapshots_ok(), snapshots_ok()], ignore_index=True)
    with pytest.raises(checks.DataCheckError, match="duplicate"):
        checks.check_snapshots(df)


# --- coverage -------------------------------------------------------------------------------------------------------


def test_coverage_for_counts_rows_seasons_latest_and_missing_fractions():
    df = pd.DataFrame(
        {
            "season": [2025, 2025, 2026, 2026],
            "observed_at": [CUT - 3 * HOUR, CUT - 2 * HOUR, CUT - HOUR, CUT],
            "qb": ["A", None, "", "D"],
        }
    )
    cov = coverage.coverage_for("qbs", df, ["qb", "nope"], "observed_at")
    assert cov.rows == 4 and cov.seasons == [2025, 2026] and cov.rows_per_season == {2025: 2, 2026: 2}
    assert cov.latest == CUT.isoformat()
    assert cov.missing == {"qb": 0.5, "nope": 1.0}
    assert any("nope" in n for n in cov.notes)


def test_report_from_tables_has_the_five_feeds():
    t = tables(games=games_df(PLAYED_GAME), snapshots=snaps_df({"observed_at": CUT}))
    report = coverage.report_from_tables(t)
    assert list(report) == ["games", "lines", "quarterbacks", "injuries", "weather"]
    assert report["lines"].seasons == [2026] and report["quarterbacks"].rows == 0


SCHEDULE_ROWS = [
    {"game_id": "g1", "season": "2026", "gameday": "2026-09-13", "home_score": "24", "home_moneyline": "-150",
     "home_qb_name": "A", "away_qb_name": "B"},
    {"game_id": "g2", "season": "2026", "gameday": "2026-09-20", "home_score": "NA", "home_moneyline": "NA",
     "home_qb_name": "", "away_qb_name": "D"},
    {"game_id": "g0", "season": "2019", "gameday": "2019-09-08", "home_score": "3", "home_moneyline": "NA",
     "home_qb_name": "", "away_qb_name": ""},
]  # fmt: skip


def fake_fetch(path: str) -> list[dict[str, str]]:
    if path == "schedules/games.csv":
        return SCHEDULE_ROWS
    if path == "injuries/injuries_2026.csv":
        return [
            {"gsis_id": "00-1", "report_status": "Out", "team": "BUF"},
            {"gsis_id": "", "report_status": "", "team": "MIA"},
        ]
    raise OSError(f"no such file {path}")


def test_report_from_nflverse_uses_the_injected_fetch_and_records_failures():
    report = coverage.report_from_nflverse([2026], fetch=fake_fetch)
    sched = report["schedule"]
    assert sched.rows == 2 and sched.seasons == [2026]
    assert sched.missing["home_score"] == 0.5
    note = next(n for n in sched.notes if n.startswith("2026:"))
    assert "2 games, 1 finished, last finished kickoff date 2026-09-13, 1 with a moneyline, 1 with both" in note
    assert report["injuries"].rows == 2 and report["injuries"].missing["gsis_id"] == 0.5
    assert report["team_stats"].rows == 0
    assert any("fetch failed" in n and "stats_team_week_2026" in n for n in report["team_stats"].notes)


def test_a_schedule_fetch_failure_is_a_note_and_other_feeds_are_still_returned():
    def broken(path: str):
        if path.startswith("schedules"):
            raise OSError("down")
        return fake_fetch(path)

    report = coverage.report_from_nflverse([2026], fetch=broken)
    assert any("down" in n for n in report["schedule"].notes) and report["injuries"].rows == 2


def test_render_markdown_has_each_feed_name_and_the_title():
    report = coverage.report_from_nflverse([2026], fetch=fake_fetch)
    text = coverage.render_markdown(report, "Coverage check")
    assert text.startswith("# Coverage check")
    for name in ("schedule", "injuries", "team_stats"):
        assert f"| {name} |" in text


# --- matchup (bench candidate only) ---------------------------------------------------------------------------------


def elo_frame(*diffs: float, market: float | None = None) -> pd.DataFrame:
    frame = pd.DataFrame({"elo_diff": list(diffs)})
    if market is not None:
        frame["market_logit"] = market
    return frame


def test_matchup_is_fifty_at_zero_elo_diff():
    assert matchup.matchup_score(elo_frame(0.0)).iloc[0] == pytest.approx(50.0)


def test_matchup_rises_with_elo_diff():
    score = matchup.matchup_score(elo_frame(-3.0, -1.0, 0.0, 1.0, 3.0))
    assert score.is_monotonic_increasing and score.iloc[-1] > 50 > score.iloc[0]


def test_matchup_is_symmetric_around_fifty():
    d = 1.7
    both = matchup.matchup_score(elo_frame(d, -d))
    assert both.iloc[1] == pytest.approx(100 - both.iloc[0])


def test_matchup_one_elo_point_hundred_uses_the_elo_logistic_constant():
    z = np.log(10) / 4
    assert matchup.matchup_score(elo_frame(1.0)).iloc[0] == pytest.approx(100 / (1 + np.exp(-z)))


def test_matchup_is_nan_when_elo_diff_is_nan():
    assert np.isnan(matchup.matchup_score(elo_frame(np.nan, market=0.4)).iloc[0])


def test_matchup_ignores_the_market_unless_asked():
    frame = elo_frame(0.0, market=2.0)
    assert matchup.matchup_score(frame).iloc[0] == pytest.approx(50.0)
    assert matchup.matchup_score(frame, include_market=True).iloc[0] > 50.0


def test_matchup_averages_available_components_and_counts_them():
    frame = pd.DataFrame({"elo_diff": [1.0, 1.0], "market_logit": [np.nan, 1.0]})
    parts = matchup.matchup_components(frame, include_market=True)
    assert parts["n_components"].tolist() == [1, 2]
    z0, z1 = matchup.ELO_LOGIT_PER_100, (matchup.ELO_LOGIT_PER_100 + 1.0) / 2
    assert matchup.matchup_score(frame, include_market=True).tolist() == pytest.approx(
        [100 / (1 + np.exp(-z0)), 100 / (1 + np.exp(-z1))]
    )
    assert "z_elo" in matchup.MATCHUP_FORMULA


def test_nothing_in_the_shipping_code_imports_the_data_package():
    root = Path(asof.__file__).resolve().parents[1]
    files = [*root.joinpath("predictions").rglob("*.py"), *root.joinpath("api").rglob("*.py")]
    files += [*root.joinpath("analytics").rglob("*.py"), root / "jobs.py"]
    # ponytail: bench_*.py are research benches the app never loads (checked below), so they may read the data layer
    benches = [f for f in files if f.name.startswith("bench_")]
    files = [f for f in files if f not in benches]
    assert files
    offenders = [f.name for f in files if "nflpi.data" in f.read_text() or "from nflpi import data" in f.read_text()]
    assert offenders == []
    assert [f.name for f in files if any(b.stem in f.read_text() for b in benches)] == []


# --- database loader ------------------------------------------------------------------------------------------------


def seed_db(session):
    from nflpi.models import Game, InjuryReport, MarketSnapshot, QbObservation, WeatherForecast

    def game(gid, kickoff, **kw):
        return Game(
            game_id=gid, season=2026, week=6, game_type="REG", kickoff_utc=kickoff, weekday="Sun", away_team="MIA",
            home_team="BUF", status="final", source="t", home_qb="After Fact", away_qb="Af2", **kw,
        )  # fmt: skip

    session.add_all([game("P", CUT - 30 * HOUR, home_score=24, away_score=17), game("F", CUT + 30 * HOUR)])
    session.flush()
    session.add_all(
        [
            MarketSnapshot(game_id="F", observed_at=CUT - 5 * HOUR, source="t", kind="latest", spread_line=3.0),
            MarketSnapshot(game_id="F", observed_at=CUT + 5 * HOUR, source="t", kind="latest", spread_line=9.0),
            QbObservation(game_id="F", side="home", qb="Projected", observed_at=CUT - 2 * HOUR),
            QbObservation(game_id="F", side="home", qb="Late Change", observed_at=CUT + 2 * HOUR),
            InjuryReport(season=2026, week=6, team="BUF", player_id="p1", player="P One", report_status="Out",
                         source="t", observed_at=CUT - HOUR),
            WeatherForecast(game_id="F", observed_at=CUT - HOUR, temp_f=48.0, source="t"),
        ]
    )  # fmt: skip
    session.commit()


def test_load_tables_reads_every_table_with_model_column_names(session):
    seed_db(session)
    t = asof.load_tables(session)
    assert len(t.games) == 2 and len(t.snapshots) == 2 and len(t.qb_observations) == 2
    assert {"id", "game_id", "observed_at", "spread_line"} <= set(t.snapshots.columns)
    assert len(t.injuries) == 1 and len(t.weather) == 1


def test_asof_frame_from_db_hides_what_happens_after_the_cutoff(session):
    seed_db(session)
    frame = asof.asof_frame_from_db(session, CUT).set_index("game_id")
    assert frame.loc["F", "spread_line"] == 3.0 and frame.loc["F", "home_spread"] == -3.0
    assert frame.loc["F", "home_qb"] == "Projected"
    assert pd.isna(frame.loc["F", "home_score"]) and frame.loc["F", "status"] == "scheduled"
    assert frame.loc["P", "home_qb"] == "After Fact" and frame.loc["P", "home_score"] == 24
    assert frame.loc["F", "fcst_temp_f"] == 48.0 and frame.loc["F", "home_out_count"] == 1


def test_asof_frame_from_db_is_read_only_and_a_later_cutoff_sees_more(session):
    seed_db(session)
    later = asof.asof_frame_from_db(session, CUT + 10 * HOUR).set_index("game_id")
    assert later.loc["F", "spread_line"] == 9.0 and later.loc["F", "home_qb"] == "Late Change"
    assert len(asof.load_tables(session).snapshots) == 2


# --- review fixes -----------------------------------------------------------------------------------------------------


def test_asof_games_blanks_qb_names_of_unplayed_games_but_keeps_played():
    future = asof.asof_games(games_df(FUTURE_GAME | {"home_qb": "After"}), CUT)
    assert pd.isna(future.loc[0, "home_qb"]) and pd.isna(future.loc[0, "away_qb"])
    played = asof.asof_games(games_df(PLAYED_GAME), CUT)
    assert played.loc[0, "home_qb"] == "Josh Allen"


@pytest.mark.parametrize("column", ["observed_at", "kickoff_utc"])
def test_naive_time_column_is_refused(column):
    naive = datetime(2026, 10, 18, 1)
    if column == "kickoff_utc":
        with pytest.raises(checks.DataCheckError, match="tz-aware"):
            asof.asof_games(games_df(PLAYED_GAME | {"kickoff_utc": naive}), CUT)
    else:
        with pytest.raises(checks.DataCheckError, match="tz-aware"):
            asof.asof_lines(snaps_df({"observed_at": naive}), CUT)


def test_missing_observed_at_column_on_non_empty_frame_is_refused():
    with pytest.raises(checks.DataCheckError, match="observed_at"):
        asof.asof_lines(snaps_df({}), CUT)


def test_nat_observed_at_is_refused_not_dropped():
    with pytest.raises(checks.DataCheckError, match="observed_at"):
        asof.asof_lines(snaps_df({"observed_at": pd.NaT}, {"id": 2, "observed_at": CUT}), CUT)


def test_build_refuses_duplicate_game_id_and_bad_snapshots():
    with pytest.raises(checks.DataCheckError, match="duplicate game_id"):
        asof.build_asof_frame(tables(games=games_df(PLAYED_GAME, PLAYED_GAME)), CUT)
    bad = snaps_df({"observed_at": CUT, "home_moneyline": 50.0})
    with pytest.raises(checks.DataCheckError, match="check_snapshots"):
        asof.build_asof_frame(tables(games=games_df(PLAYED_GAME), snapshots=bad), CUT)


def test_injuries_key_on_player_id_else_player_and_null_both_are_not_collapsed():
    rows = [
        {"id": 1, "observed_at": CUT - 3 * HOUR, "player_id": None, "player": "Name A"},
        {
            "id": 2,
            "observed_at": CUT - 2 * HOUR,
            "player_id": None,
            "player": "Name A",
            "report_status": "Questionable",
        },
        {"id": 3, "observed_at": CUT - 2 * HOUR, "player_id": None, "player": None},
        {"id": 4, "observed_at": CUT - 2 * HOUR, "player_id": None, "player": None},
    ]
    out = asof.asof_injuries(inj_df(*rows), CUT)
    assert len(out) == 3
    assert sorted(out["id"]) == [2, 3, 4]


def test_out_count_matches_report_status_case_insensitively():
    inj = inj_df(
        {"observed_at": CUT - HOUR, "report_status": "OUT"},
        {"id": 2, "player_id": "p2", "observed_at": CUT - HOUR, "report_status": " out "},
    )
    frame = asof.build_asof_frame(tables(games=games_df(FUTURE_GAME | {"week": 6}), injuries=inj), CUT)
    assert frame.loc[0, "home_out_count"] == 2


def test_ties_without_id_do_not_depend_on_row_order():
    rows = [
        {"observed_at": CUT - HOUR, "spread_line": 3.0},
        {"observed_at": CUT - HOUR, "spread_line": 7.0},
        {"observed_at": CUT - HOUR, "spread_line": 1.0},
    ]
    frame = snaps_df(*rows).drop(columns="id")
    first = asof.asof_lines(frame, CUT)["spread_line"].tolist()
    for seed in range(5):
        shuffled = frame.sample(frac=1, random_state=seed)
        assert asof.asof_lines(shuffled, CUT)["spread_line"].tolist() == first


def test_check_games_rejects_negative_score():
    with pytest.raises(checks.DataCheckError, match="negative"):
        checks.check_games(
            checked_games(
                {
                    "game_id": "A",
                    "season": 2026,
                    "week": 1,
                    "kickoff_utc": datetime(2026, 9, 13, 17, tzinfo=UTC),
                    "home_score": -1.0,
                }
            )
        )


def test_check_games_rejects_final_without_score_and_scheduled_with_score():
    kick = {"game_id": "A", "season": 2026, "week": 1, "kickoff_utc": datetime(2026, 9, 13, 17, tzinfo=UTC)}
    with pytest.raises(checks.DataCheckError, match="final"):
        checks.check_games(checked_games(kick | {"home_score": np.nan}))
    with pytest.raises(checks.DataCheckError, match="scheduled"):
        checks.check_games(checked_games(kick | {"status": "scheduled"}))


def test_check_snapshots_rejects_same_sign_moneylines():
    with pytest.raises(checks.DataCheckError, match="sign"):
        checks.check_snapshots(snapshots_ok(home_moneyline=-150.0, away_moneyline=-130.0))
    checks.check_snapshots(snapshots_ok(home_moneyline=-150.0, away_moneyline=np.nan))


def test_check_snapshots_allows_a_pickem_pair_of_negative_lines():
    checks.check_snapshots(snapshots_ok(home_moneyline=-110.0, away_moneyline=-110.0))


def test_asof_lines_do_not_carry_the_mutable_kind_column():
    lines = asof.asof_lines(snapshots_ok(), CUT)
    assert "kind" not in lines.columns
