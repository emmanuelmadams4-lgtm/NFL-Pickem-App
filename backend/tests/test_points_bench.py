"""Step 19b: confidence-pool points bench. Clauses B1-B7 in docs/gauntlet/logs/step-19b.md section 2. No database."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

KICK = datetime(2023, 9, 10, 17, 0, tzinfo=UTC)


def _pb():
    from nflpi.analytics import points_bench  # imported per test so collection works while 19b is red

    return points_bench


def frame(rows):
    """rows: (season, week, game_id, home_win, p_blend, p_market)."""
    return pd.DataFrame(
        [{"season": s, "week": w, "game_id": g, "home_win": y, "p_blend": b, "p_market": m,
          "kickoff_utc": KICK + timedelta(days=7 * (w - 1) + 365 * (s - 2023))} for s, w, g, y, b, m in rows]
    )


# --- B1-B2 points per week ---------------------------------------------------------------------------

def test_b1_points_follow_the_live_confidence_pool_rule():
    f = frame([(2023, 1, "g1", 1, 0.80, 0.5), (2023, 1, "g2", 1, 0.30, 0.5), (2023, 1, "g3", 1, 0.60, 0.5)])
    week = _pb().points_week(f, "p_blend")
    row = week.iloc[0]
    # picks: g1 home (share .80, 3 pts), g2 away (share .70, 2 pts), g3 home (share .60, 1 pt); all homes won
    assert (row["season"], row["week"]) == (2023, 1)
    assert row["points"] == 4 and row["max_points"] == 6 and row["correct"] == 2 and row["n"] == 3


def test_b1b_equal_shares_go_by_game_id_like_the_live_rule():
    f = frame([(2023, 1, "b", 1, 0.60, 0.5), (2023, 1, "a", 0, 0.40, 0.5)])  # both shares 0.60
    row = _pb().points_week(f, "p_blend").iloc[0]
    assert row["points"] == 3  # "a" (away, right) gets 2, "b" (home, right) gets 1


def test_b2_picks_and_order_come_from_the_named_column_not_always_the_blend():
    f = frame([(2023, 1, "g1", 0, 0.70, 0.40), (2023, 1, "g2", 1, 0.55, 0.90)])
    pb = _pb()
    assert pb.points_week(f, "p_blend").iloc[0]["points"] == 1  # blend: g1 home wrong (2), g2 home right (1)
    assert pb.points_week(f, "p_market").iloc[0]["points"] == 3  # market: g2 home right (2), g1 away right (1)


# --- B3 paired comparison -----------------------------------------------------------------------------

def test_b3_compare_pairs_weeks_and_drops_games_missing_either_chance():
    rows = [(2023, w, f"g{w}{i}", 1, 0.6 + 0.01 * i, 0.4 if i == 0 else 0.7) for w in (1, 2, 3) for i in range(3)]
    rows.append((2023, 1, "nan", 1, 0.9, np.nan))  # left out of BOTH sides
    out = _pb().compare(frame(rows), "p_market", "p_blend", [2023], reps=500, seed=3)
    base = _pb().points_week(frame([r for r in rows if r[2] != "nan"]), "p_blend")
    cand = _pb().points_week(frame([r for r in rows if r[2] != "nan"]), "p_market")
    gain = (cand["points"].to_numpy() - base["points"].to_numpy()).mean()
    assert out["n_weeks"] == 3 and out["n_games"] == 9
    assert out["points_gain"] == pytest.approx(gain)
    lo, hi = out["points_gain_ci"]
    assert lo <= gain <= hi
    assert out["accuracy_diff"] == pytest.approx(-3 / 9)  # market misses the three i == 0 games
    assert out["log_loss_gain"] < 0


def test_b3b_compare_is_reproducible_with_a_seed():
    rows = [(2023, w, f"g{w}{i}", i % 2, 0.55 + 0.05 * i, 0.6 - 0.05 * i) for w in range(1, 9) for i in range(4)]
    a = _pb().compare(frame(rows), "p_market", "p_blend", [2023], reps=300, seed=11)
    b = _pb().compare(frame(rows), "p_market", "p_blend", [2023], reps=300, seed=11)
    assert a == b


# --- B4 the pre-registered ship rule (god 65e0b3) -----------------------------------------------------

def _res(gain=1.0, lo=0.1, acc=0.0, ll=0.0):
    return {"points_gain": gain, "points_gain_ci": [lo, gain + 1], "accuracy_diff": acc, "log_loss_gain": ll}


@pytest.mark.parametrize(("test", "guard", "ship"), [
    (_res(), _res(gain=0.0), True),
    (_res(lo=0.0), _res(), False),  # CI lower bound must be ABOVE 0
    (_res(acc=-0.001), _res(), False),  # accuracy lower
    (_res(ll=-0.0001), _res(), False),  # log-loss worse
    (_res(), _res(gain=-0.01), False),  # 2012-2021 points/week below 0
])
def test_b4_decide_ships_only_when_the_primary_and_all_three_guards_hold(test, guard, ship):
    assert _pb().decide(test, guard)["ship"] is ship


def test_b4b_the_rule_windows_are_fixed():
    pb = _pb()
    assert list(pb.TEST_SEASONS) == [2022, 2023, 2024, 2025]
    assert list(pb.GUARD_SEASONS) == list(range(2012, 2022))


# --- B5 D72 -----------------------------------------------------------------------------------------

def test_b5_a_game_on_or_after_the_protected_date_is_never_scored():
    f = frame([(2023, 1, "g1", 1, 0.6, 0.6)])
    f.loc[0, "kickoff_utc"] = datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
    with pytest.raises(Exception, match="D72"):
        _pb().compare(f, "p_market", "p_blend", [2023])


# --- B6 c1 signed QB change ---------------------------------------------------------------------------

def test_b6_a_returning_starter_is_told_apart_from_a_backup_coming_in():
    games = pd.DataFrame([
        {"season": 2023, "home_team": "BAL", "away_team": "X1", "home_qb": "A", "away_qb": "x"},
        {"season": 2023, "home_team": "BAL", "away_team": "X2", "home_qb": "B", "away_qb": "y"},  # backup in
        {"season": 2023, "home_team": "X3", "away_team": "BAL", "home_qb": "z", "away_qb": "A"},  # starter back
        {"season": 2024, "home_team": "BAL", "away_team": "X4", "home_qb": "B", "away_qb": "w"},  # new season
    ])
    out = _pb().qb_direction(games)
    assert list(out["home_qb_in"]) == [0.0, 1.0, 0.0, 0.0]
    assert list(out["away_qb_back"]) == [0.0, 0.0, 1.0, 0.0]
    assert list(out["away_qb_in"]) == [0.0, 0.0, 0.0, 0.0]
    assert list(out["home_qb_back"]) == [0.0, 0.0, 0.0, 0.0]


# --- B8 c2 fitted mix (stack on earlier seasons' out-of-sample chances) -------------------------------

def _oos(seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for season in (2012, 2013, 2014):
        for i in range(120):
            m = rng.uniform(0.2, 0.8)
            rows.append({"season": season, "game_id": f"{season}_{i}", "p_market": m,
                         "p_logistic": float(np.clip(m + rng.normal(0, 0.1), 0.05, 0.95)),
                         "p_blend": 0.5, "home_win": float(rng.uniform() < m)})
    return pd.DataFrame(rows)


def test_b8_the_mix_for_a_season_is_fitted_only_on_earlier_seasons():
    pb = _pb()
    preds = _oos()
    first = pb.mix_c2(preds)
    assert (first[preds["season"] == 2012] == preds.loc[preds["season"] == 2012, "p_blend"]).all()  # nothing earlier
    changed = preds.copy()
    changed.loc[changed["season"] == 2014, "home_win"] = 1 - changed.loc[changed["season"] == 2014, "home_win"]
    again = pb.mix_c2(changed)
    assert np.allclose(first[preds["season"] == 2014], again[preds["season"] == 2014])  # its own results unused
    assert not np.allclose(first[preds["season"] == 2013], 0.5)  # a fitted mix, not the blend
    assert ((first > 0) & (first < 1)).all()


def test_b8b_games_without_a_market_keep_the_blend():
    pb = _pb()
    preds = _oos()
    preds.loc[preds.index[-1], "p_market"] = np.nan
    assert pb.mix_c2(preds).iloc[-1] == preds["p_blend"].iloc[-1]


# --- B9 c3 non-QB injuries (the week's final report, published before the game) ----------------------

def test_b9_counts_only_out_non_qb_players_of_that_team_and_week():
    games = pd.DataFrame([
        {"season": 2023, "week": 5, "home_team": "BAL", "away_team": "CLE"},
        {"season": 2023, "week": 6, "home_team": "CLE", "away_team": "BAL"},
    ])
    injuries = pd.DataFrame([
        {"season": 2023, "week": 5, "team": "BAL", "position": "WR", "report_status": "Out"},
        {"season": 2023, "week": 5, "team": "BAL", "position": "T", "report_status": " out "},
        {"season": 2023, "week": 5, "team": "BAL", "position": "QB", "report_status": "Out"},  # QB: c1's job
        {"season": 2023, "week": 5, "team": "BAL", "position": "CB", "report_status": "Questionable"},
        {"season": 2023, "week": 5, "team": "BAL", "position": "LB", "report_status": "Doubtful"},
        {"season": 2023, "week": 5, "team": "CLE", "position": "RB", "report_status": "Out"},
        {"season": 2023, "week": 6, "team": "BAL", "position": "S", "report_status": "Out"},
        {"season": 2022, "week": 5, "team": "BAL", "position": "WR", "report_status": "Out"},  # other season
    ])
    out = _pb().injury_counts(games, injuries)
    assert list(out["home_out_nonqb"]) == [2, 0]
    assert list(out["away_out_nonqb"]) == [1, 1]
    assert list(out["inj_diff"]) == pytest.approx([0.2, -0.2])  # (home - away) / 5
