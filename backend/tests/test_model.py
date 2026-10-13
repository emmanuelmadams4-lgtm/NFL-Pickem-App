import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from nflpi.analytics import backtest as bt
from nflpi.analytics.backtest import _elo_frames, candidate_preds, evaluate, inseason_blend, predict_season
from nflpi.analytics.metrics import (
    bootstrap_ci,
    brier,
    calibration,
    game_log_loss,
    log_loss,
    paired_gain,
    wilson_ci,
)
from nflpi.ingestion import nflverse
from nflpi.models import Prediction
from nflpi.predictions import engine
from nflpi.predictions import features as ft
from nflpi.predictions import market as mk
from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.features import (
    BASE_FEATURES,
    BLEND_FEATURES,
    add_features,
    epa_diff,
    games_frame,
    team_game_epa,
)
from nflpi.predictions.market import novig_home_prob
from nflpi.predictions.model import LogitModel
from tests.conftest import CURRENT, schedule_rows


def frame() -> pd.DataFrame:
    games = nflverse.parse_games(schedule_rows(), 2018)
    for g in games:
        g["home_ml"], g["away_ml"] = g.pop("_home_ml"), g.pop("_away_ml")
        g.pop("_spread"), g.pop("_total")
    return games_frame(games)


def test_pregame_elo_never_sees_its_own_or_later_results():
    df = frame()
    base = run_elo(df, EloParams())
    i = len(df) // 2
    flipped = df.copy()
    flipped.loc[i:, ["home_score", "away_score"]] = flipped.loc[i:, ["away_score", "home_score"]].to_numpy()
    after = run_elo(flipped, EloParams())
    # Ratings up to and including game i are unchanged; later ones may move.
    assert np.allclose(base.loc[:i, "home_elo"], after.loc[:i, "home_elo"])
    assert np.allclose(base.loc[:i, "away_elo"], after.loc[:i, "away_elo"])


def test_qb_change_flag_is_pregame_and_within_season():
    df = frame()
    target = df[(df["season"] == 2019)].index[-1]
    team = df.loc[target, "home_team"]
    df.loc[target, "home_qb"] = "Backup Guy"
    f = add_features(df, EloParams())
    assert f.loc[target, "home_qb_change"] == 1.0
    assert f.loc[target, "home_prev_qb"] == f"{team} QB1"
    first_games = f.groupby("season").head(1).index
    assert (f.loc[first_games, ["home_qb_change", "away_qb_change"]] == 0).all().all()


def test_walk_forward_trains_only_on_past_seasons(monkeypatch):
    seen = []
    from nflpi.predictions import model as model_mod

    real_fit = model_mod.LogitModel.fit.__func__

    def spy(cls, df, features):
        seen.append(set(df["season"]))
        return real_fit(cls, df, features)

    monkeypatch.setattr(model_mod.LogitModel, "fit", classmethod(spy))
    frames = _elo_frames(frame())
    test = predict_season(frames, 2021, window=3)
    assert set(test["season"]) == {2021}
    assert all(seasons <= {2018, 2019, 2020} for seasons in seen)
    for col in ("p_home", "p_elo", "p_logistic", "p_blend"):
        assert test[col].between(0, 1).all()


def test_metrics_and_calibration():
    p = np.array([0.9, 0.8, 0.35, 0.65])
    y = np.array([1.0, 0.0, 0.0, 1.0])
    assert abs(brier(p, y) - np.mean((p - y) ** 2)) < 1e-12
    assert log_loss(np.array([0.5]), np.array([1.0])) == np.log(2)
    buckets = {b["bucket"]: b for b in calibration(p, y)}
    assert (
        buckets["60-70%"]["n"] == 2 and buckets["60-70%"]["observed"] == 1.0
    )  # 0.65 home won; 0.35 means away 65%, away won
    assert buckets["80-90%"]["n"] == 1 and buckets["90-100%"]["n"] == 1
    lo, hi = wilson_ci(66, 100)
    assert 0.56 < lo < 0.66 < hi < 0.75


def test_predictions_are_valid_and_snapshots_are_insert_only(loaded):
    preds = loaded.scalars(select(Prediction)).all()
    assert preds, "expected predictions for the upcoming weeks"
    for p in preds:
        assert 0 < p.home_win_prob < 1
        assert p.uncertainty in ("low", "moderate", "high")
        assert p.features["used_market"] is True and p.factors
    # Same inputs: nothing new is written.
    assert engine.refresh_predictions(loaded) == []
    assert len(loaded.scalars(select(Prediction)).all()) == len(preds)


def test_qb_change_creates_new_snapshot_and_keeps_old(loaded):
    from nflpi.models import Game

    first = loaded.scalars(select(Prediction).order_by(Prediction.id)).first()
    g = loaded.get(Game, first.game_id)
    g.home_qb = "Emergency Starter"
    loaded.commit()
    engine.refresh_predictions(loaded)
    history = loaded.scalars(select(Prediction).where(Prediction.game_id == g.game_id).order_by(Prediction.id)).all()
    assert len(history) == 2
    assert history[0].home_win_prob == first.home_win_prob  # untouched
    assert history[1].features["home_qb_change"] == 1.0
    assert "starting QB" in history[1].change_note
    assert any("QB change" in r for r in history[1].uncertainty_reasons)


def test_backfill_labels_rows_and_needs_an_earlier_model(loaded):
    n = engine.backfill_season(loaded, CURRENT)
    rows = loaded.scalars(select(Prediction).where(Prediction.kind == "backfill")).all()
    assert n == len(rows) > 0
    assert all(r.features["market_kind"] == "closing" for r in rows)


# --- Step 14: candidates are judged against the current blend (docs/gauntlet/logs/step-14.md, section 2) ---


def test_game_log_loss_is_per_game_and_averages_to_log_loss():
    p, y = np.array([0.9, 0.2]), np.array([1.0, 1.0])
    assert np.allclose(game_log_loss(p, y), [-np.log(0.9), -np.log(0.2)])
    assert abs(game_log_loss(p, y).mean() - log_loss(p, y)) < 1e-12


def test_paired_gain_matches_a_hand_count():
    y = np.array([1.0, 1.0, 0.0, 1.0])
    old = np.array([0.6, 0.6, 0.4, 0.6])  # every game: loss -ln 0.6, pick right
    new = np.array([0.8, 0.7, 0.3, 0.4])  # last game: pick wrong
    per_game = np.log(np.array([0.8, 0.7, 0.7, 0.4]) / 0.6)
    got = paired_gain(new, old, y)
    assert got["n"] == 4
    assert abs(got["log_loss_gain"] - per_game.mean()) < 1e-12 and got["log_loss_gain"] > 0
    # Paired: one resample of the per-game differences, not two separate intervals.
    assert np.allclose(got["log_loss_gain_ci"], bootstrap_ci(per_game))
    assert got["accuracy_diff"] == -0.25
    assert np.allclose(got["accuracy_diff_ci"], bootstrap_ci(np.array([0.0, 0.0, 0.0, -1.0])))
    assert got["ships"] is False


def test_a_candidate_ships_only_with_a_gain_interval_above_zero_and_no_accuracy_drop():
    y = np.tile([1.0, 0.0], 100)
    side = np.where(y == 1, 1.0, -1.0)
    old = 0.5 + 0.1 * side
    better = paired_gain(0.5 + 0.3 * side, old, y)
    assert better["log_loss_gain_ci"][0] > 0 and better["accuracy_diff"] == 0 and better["ships"] is True

    fewer_right = 0.5 + 0.3 * side
    fewer_right[:10] = 0.5 - 0.01 * side[:10]  # ten picks flip to the wrong side
    drop = paired_gain(fewer_right, old, y)
    assert drop["log_loss_gain_ci"][0] > 0 and drop["accuracy_diff"] < 0 and drop["ships"] is False

    noisy = np.where(np.arange(200) % 2 == 0, 0.5 + 0.25 * side, 0.5 + 0.005 * side)[:40]
    unsure = paired_gain(noisy, old[:40], y[:40])
    assert unsure["log_loss_gain"] > 0 and unsure["log_loss_gain_ci"][0] < 0 < unsure["log_loss_gain_ci"][1]
    assert unsure["accuracy_diff"] == 0 and unsure["ships"] is False


def test_paired_gain_refuses_missing_or_empty_input():
    y = np.array([1.0, 0.0])
    good = np.array([0.6, 0.4])
    for new, old, outcome in (
        (np.array([np.nan, 0.4]), good, y),  # a missing pick must never be scored as a wrong pick
        (good, np.array([0.6, np.inf]), y),
        (good, good, np.array([1.0, np.nan])),
        (good[:0], good[:0], y[:0]),  # no games: no verdict
        (good[:1], good, y),
    ):
        with pytest.raises(ValueError):
            paired_gain(new, old, outcome)


def _flip_scores(df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    out = df.copy()
    out.loc[mask, ["home_score", "away_score"]] = out.loc[mask, ["away_score", "home_score"]].to_numpy()
    return out


def test_inseason_refit_uses_earlier_weeks_and_never_the_same_or_a_later_week():
    df = frame()
    frames = _elo_frames(df)
    base = predict_season(frames, 2022, window=3)
    got = inseason_blend(frames, 2022, window=3)
    assert list(got.index) == list(base.index) and got.between(0, 1).all()
    week = base["week"]
    # Week 1 has no game of its own season to learn from: same training rows as the season-level blend.
    assert np.allclose(got[week == 1], base.loc[week == 1, "p_blend"])
    assert not np.allclose(got[week > 1], base.loc[week > 1, "p_blend"])
    # The last game of week 3 and everything after it cannot move a pick made for weeks 1 to 3.
    # (Earlier week 3 games are left alone: Elo rightly moves between games of one week.)
    last_of_week3 = df.loc[(df["season"] == 2022) & (df["week"] == 3), "kickoff_utc"].max()
    later = _flip_scores(df, (df["season"] == 2022) & (df["kickoff_utc"] >= last_of_week3))
    after = inseason_blend(_elo_frames(later), 2022, window=3)
    assert np.allclose(got[week <= 3], after[week <= 3])
    assert not np.allclose(got[week > 3], after[week > 3])
    # A game's own result never moves its own pick, even for the first game of a week.
    first = df[(df["season"] == 2022) & (df["week"] == 3)].index[0]
    own = inseason_blend(_elo_frames(_flip_scores(df, df.index == first)), 2022, window=3)
    assert np.isclose(got[first], own[first])


def test_inseason_refit_skips_a_postponed_game_that_was_not_played_yet():
    df = frame()
    late = df[(df["season"] == 2022) & (df["week"] == 1)].index[0]
    week2_last = df.loc[(df["season"] == 2022) & (df["week"] == 2), "kickoff_utc"].max()
    df.loc[late, "kickoff_utc"] = week2_last + pd.Timedelta(days=1)  # week 1 game played after week 2
    df = df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    is_late = (df["season"] == 2022) & (df["week"] == 1) & (df["kickoff_utc"] > week2_last)
    assert is_late.sum() == 1
    got = inseason_blend(_elo_frames(df), 2022, window=3)
    after = inseason_blend(_elo_frames(_flip_scores(df, is_late)), 2022, window=3)
    week = df.loc[got.index, "week"]
    assert np.allclose(got[week == 2], after[week == 2])


def test_inseason_refit_trains_on_the_window_and_the_test_season_only(monkeypatch):
    seen = []
    from nflpi.predictions import model as model_mod

    real_fit = model_mod.LogitModel.fit.__func__

    def spy(cls, df, features):
        seen.append(set(df["season"]))
        return real_fit(cls, df, features)

    frames = _elo_frames(frame())
    monkeypatch.setattr(model_mod.LogitModel, "fit", classmethod(spy))
    inseason_blend(frames, 2022, window=3)
    assert seen and all({2019, 2020, 2021} <= seasons <= {2019, 2020, 2021, 2022} for seasons in seen)
    assert any(2022 in seasons for seasons in seen)


def test_evaluate_picks_the_variant_on_tune_seasons_and_confirms_it_once():
    rows = []
    for season, a, b in ((2019, 0.9, 0.9), (2020, 0.8, 0.55), (2021, 0.55, 0.8)):
        for i in range(40):
            y = float(i % 2)
            side = 1.0 if y == 1 else -1.0
            rows.append({"season": season, "home_win": y, "p_blend": 0.5 + 0.1 * side,
                         "p_a": 0.5 + (a - 0.5) * side, "p_b": 0.5 + (b - 0.5) * side, "p_solo": 0.5 + 0.2 * side})
    preds = pd.DataFrame(rows)
    report = evaluate(preds, {"x": ["p_a", "p_b"], "solo": ["p_solo"]}, tune=[2020], confirm=[2021])
    x, solo = report
    tune, confirm = preds[preds["season"] == 2020], preds[preds["season"] == 2021]
    y_t, y_c = tune["home_win"].to_numpy(), confirm["home_win"].to_numpy()
    assert x["candidate"] == "x" and x["chosen"] == "p_a"  # p_b is better on the confirm seasons; that must not matter
    assert x["variants"] == [
        {"variant": v, "tune": paired_gain(tune[v].to_numpy(), tune["p_blend"].to_numpy(), y_t)} for v in ("p_a", "p_b")
    ]
    assert x["confirm"] == paired_gain(confirm["p_a"].to_numpy(), confirm["p_blend"].to_numpy(), y_c)
    # The ship verdict is the confirm verdict: p_a won on the tune season and loses on the confirm season.
    assert x["confirm"]["n"] == 40 and x["confirm"]["log_loss_gain"] < 0 and x["ships"] is False
    assert solo["chosen"] == "p_solo" and solo["confirm"]["log_loss_gain"] > 0 and solo["ships"] is True


def test_candidate_preds_scores_market_games_of_the_asked_seasons():
    df = frame()
    no_line = df[(df["season"] == 2022) & (df["week"] == 2)].index[0]
    df.loc[no_line, ["home_ml", "away_ml"]] = np.nan
    preds = candidate_preds(df, [2021, 2022], window=3)
    assert set(preds["season"]) == {2021, 2022} and len(preds) == 29 and preds["p_market"].notna().all()
    frames = _elo_frames(df)
    for season in (2021, 2022):
        want = inseason_blend(frames, season, window=3).dropna()
        assert np.allclose(preds.loc[preds["season"] == season, "p_inseason"], want)
        assert np.allclose(preds.loc[preds["season"] == season, "p_blend"],
                           predict_season(frames, season, 3).loc[want.index, "p_blend"])


def _epa_row(game_id: str, team: str, passing, rushing, attempts, sacks, carries) -> dict:
    return {"game_id": game_id, "team": team, "passing_epa": str(passing), "rushing_epa": str(rushing),
            "attempts": str(attempts), "sacks_suffered": str(sacks), "carries": str(carries)}


def test_team_game_epa_is_net_epa_per_play_and_leaves_out_incomplete_games():
    rows = [
        _epa_row("g1", "A", 6, 2, 30, 2, 8),  # 8 EPA on 40 plays = 0.2
        _epa_row("g1", "B", 1, -3, 20, 0, 20),  # -2 EPA on 40 plays = -0.05
        _epa_row("g2", "A", 5, 5, 30, 0, 10),  # no row for the opponent
        _epa_row("g3", "A", 5, 5, 30, 0, 10),
        _epa_row("g3", "B", 0, 0, 0, 0, 0),  # zero plays
        _epa_row("g4", "A", "NA", 5, 30, 0, 10),  # missing value
        _epa_row("g4", "B", 1, 1, 30, "", 10),
        _epa_row("g5", "A", "nan", 5, 30, 0, 10),  # a not-a-number must not reach a rating
        _epa_row("g5", "B", 1, 1, 30, 0, 10),
        _epa_row("g6", "A", 1, "inf", 30, 0, 10),
        _epa_row("g6", "B", 1, 1, 30, 0, 10),
    ]
    got = team_game_epa(rows)
    assert list(got.columns) == ["game_id", "team", "net_epa"]
    assert got["game_id"].tolist() == ["g1", "g1"] and got["team"].tolist() == ["A", "B"]
    assert np.allclose(got["net_epa"], [0.25, -0.25])


def test_epa_diff_is_a_pregame_weighted_mean_of_earlier_games():
    start = pd.Timestamp("2022-09-11", tz="UTC")
    games = [("g1", "A", "B"), ("g2", "B", "A"), ("g3", "A", "B"), ("g4", "A", "C")]
    df = pd.DataFrame([
        {"game_id": g, "home_team": h, "away_team": a, "kickoff_utc": start + pd.Timedelta(days=7 * i)}
        for i, (g, h, a) in enumerate(games)
    ])
    epa = pd.DataFrame({
        "game_id": ["g1", "g1", "g2", "g2", "g3", "g3"],
        "team": ["A", "B", "A", "B", "A", "B"],
        "net_epa": [0.2, -0.2, 0.4, -0.4, 9.0, -9.0],
    })
    got = epa_diff(df, epa, half_life=1).to_numpy()
    assert np.isnan(got[0])  # nobody has an earlier game: missing, never zero
    assert np.isclose(got[1], -0.2 - 0.2)  # home B is -0.2, away A is 0.2
    rating = (0.4 + 0.5 * 0.2) / 1.5  # half-life 1: the last game weighs 1, the one before 0.5
    assert np.isclose(got[2], 2 * rating)  # game 3's own 9.0 is not known before game 3
    assert np.isnan(got[3])  # C has no earlier game
    slower = 0.5**0.5
    assert np.isclose(epa_diff(df, epa, half_life=2).to_numpy()[2], 2 * (0.4 + slower * 0.2) / (1 + slower))
    # A game with no EPA rows leaves both ratings where they were.
    assert np.isclose(epa_diff(df, epa[epa["game_id"] != "g2"], half_life=1).to_numpy()[2], 0.4)
    # Rows out of kickoff order would let a later game leak into an earlier rating: refuse them.
    with pytest.raises(ValueError):
        epa_diff(df.iloc[::-1], epa, half_life=1)


def test_epa_candidate_fits_on_past_seasons_and_falls_back_to_the_blend_when_missing(monkeypatch):
    df = frame()
    rows = []
    for g in df[df["status"] == "final"].itertuples():
        if "LV" in (g.home_team, g.away_team):
            continue  # LV never gets a rating
        net = (g.home_score - g.away_score) / 100
        rows += [{"game_id": g.game_id, "team": g.home_team, "net_epa": net},
                 {"game_id": g.game_id, "team": g.away_team, "net_epa": -net}]
    seen = []
    from nflpi.predictions import model as model_mod

    real_fit = model_mod.LogitModel.fit.__func__

    def spy(cls, df, features):
        seen.append((list(features), set(df["season"])))
        return real_fit(cls, df, features)

    monkeypatch.setattr(model_mod.LogitModel, "fit", classmethod(spy))
    assert "p_epa_8" not in candidate_preds(df, [2022], window=3)
    seen.clear()
    preds = candidate_preds(df, [2022], window=3, epa=pd.DataFrame(rows))
    lv = (preds["home_team"] == "LV") | (preds["away_team"] == "LV")
    assert lv.any() and not lv.all()
    for half_life in (4, 8, 16):
        col = f"p_epa_{half_life}"
        assert preds[col].between(0, 1).all()
        assert np.allclose(preds.loc[lv, col], preds.loc[lv, "p_blend"])  # no rating: the blend's own number
        assert not np.allclose(preds.loc[~lv, col], preds.loc[~lv, "p_blend"])
        fits = [seasons for features, seasons in seen if features == [*BLEND_FEATURES, f"epa_diff_{half_life}"]]
        assert fits and all(seasons == {2019, 2020, 2021} for seasons in fits)


# ---- Step 14b: five ideas from the repo review (clauses B, D, V, R, C in docs/gauntlet/logs/step-14b.md) ----

PLAIN_KEYS = {"n", "log_loss_gain", "log_loss_gain_ci", "accuracy_diff", "accuracy_diff_ci", "ships"}
IDEA_PREFIXES = ("p_devig_", "p_in_", "p_recency_")


def test_cluster_bootstrap_resamples_whole_clusters():
    values = np.array([0.3, -0.1, 0.2, 0.5, -0.4, 0.1])
    # One game per cluster is the plain bootstrap.
    assert np.allclose(bootstrap_ci(values, clusters=np.arange(6)), bootstrap_ci(values))
    # Games of one cluster move together: the interval is the one for the cluster means, and it is wider.
    means = np.tile([0.3, -0.2, 0.25, -0.1, 0.4, -0.15, 0.1, 0.2, -0.3, 0.05], 2)
    games, ids = np.repeat(means, 10), np.repeat(np.arange(20), 10)
    got = bootstrap_ci(games, clusters=ids)
    assert np.allclose(got, bootstrap_ci(means))
    plain = bootstrap_ci(games)
    assert got[1] - got[0] > 2 * (plain[1] - plain[0])
    # Each game counts once: a big cluster weighs more than a small one (true mean 0.9, mean of cluster means 0.5).
    sizes = np.tile([9, 1], 20)
    weighted = bootstrap_ci(np.repeat(np.tile([1.0, 0.0], 20), sizes), clusters=np.repeat(np.arange(40), sizes))
    assert 0.75 < weighted[0] < 0.9 < weighted[1] <= 1.0
    with pytest.raises(ValueError):
        bootstrap_ci(values, clusters=np.arange(5))


def test_paired_gain_reports_cluster_intervals_beside_the_rule_without_changing_it():
    y = np.ones(200)
    old = np.full(200, 0.6)
    weeks = np.repeat(np.arange(20), 10)
    step = np.repeat(np.where(np.arange(20) % 5 < 3, 0.1, -0.1), 10)  # 12 weeks better, 8 weeks worse
    new = old * np.exp(step)
    plain = paired_gain(new, old, y)
    assert set(plain) == PLAIN_KEYS  # no clusters asked: the step 14 output, nothing added
    got = paired_gain(new, old, y, clusters=weeks)
    assert set(got) == PLAIN_KEYS | {"log_loss_gain_ci_cluster", "accuracy_diff_ci_cluster", "ships_cluster"}
    assert {key: got[key] for key in plain} == plain  # the rule's own numbers do not move
    assert np.allclose(got["log_loss_gain_ci_cluster"], bootstrap_ci(np.log(new / old), clusters=weeks))
    assert np.allclose(got["accuracy_diff_ci_cluster"], bootstrap_ci(np.zeros(200), clusters=weeks))
    # Same games, same gain: sure game by game, not sure week by week.
    assert plain["ships"] is True and got["ships_cluster"] is False
    assert got["log_loss_gain_ci_cluster"][0] < 0 < plain["log_loss_gain_ci"][0]
    # Every week better: sure both ways.
    assert paired_gain(old * np.exp(0.1), old, y, clusters=weeks)["ships_cluster"] is True
    # A sure gain with fewer right picks still does not pass.
    drop = old * np.exp(0.2)
    drop[:10] = 0.45
    fewer_right = paired_gain(drop, old, y, clusters=weeks)
    assert fewer_right["log_loss_gain_ci_cluster"][0] > 0 and fewer_right["accuracy_diff"] < 0
    assert fewer_right["ships_cluster"] is False
    with pytest.raises(ValueError):
        paired_gain(new, old, y, clusters=weeks[:-1])


def test_evaluate_can_cluster_by_week_and_refuses_overlapping_seasons():
    rows = []
    for season in (2020, 2021):
        for i in range(40):
            y = float(i % 2)
            side = 1.0 if y == 1 else -1.0
            rows.append({"season": season, "week": i // 10 + 1, "home_win": y, "p_blend": 0.5 + 0.1 * side,
                         "p_a": 0.5 + (0.2 + 0.05 * (i // 10 % 2)) * side})
    preds = pd.DataFrame(rows)
    plain = evaluate(preds, {"x": ["p_a"]}, tune=[2020], confirm=[2021])[0]
    got = evaluate(preds, {"x": ["p_a"]}, tune=[2020], confirm=[2021], cluster=["season", "week"])[0]
    confirm = preds[preds["season"] == 2021]
    want = paired_gain(confirm["p_a"].to_numpy(), confirm["p_blend"].to_numpy(), confirm["home_win"].to_numpy(),
                       clusters=(confirm["season"] * 100 + confirm["week"]).to_numpy())
    assert got["confirm"] == want and "ships_cluster" in got["variants"][0]["tune"]
    assert got["ships"] is want["ships"] and got["ships"] is plain["ships"]  # the verdict stays the game-level rule
    assert set(plain["confirm"]) == PLAIN_KEYS
    # Sure game by game, not sure week by week: the verdict is still the game-level one.
    step = np.repeat(np.where(np.arange(20) % 5 < 3, 0.1, -0.1), 10)
    split_verdict = pd.DataFrame({"season": np.repeat([2020, 2021], 200), "week": np.tile(np.repeat(np.arange(20), 10), 2),
                                  "home_win": 1.0, "p_blend": 0.6, "p_a": np.tile(0.6 * np.exp(step), 2)})
    by_week = evaluate(split_verdict, {"x": ["p_a"]}, tune=[2020], confirm=[2021], cluster=["season", "week"])[0]
    assert by_week["confirm"]["ships_cluster"] is False and by_week["ships"] is True
    with pytest.raises(ValueError):  # a season cannot be tuned on and confirmed on
        evaluate(preds, {"x": ["p_a"]}, tune=[2020, 2021], confirm=[2021])


def test_devig_methods_remove_the_margin_each_in_its_own_way():
    assert mk.DEVIG_METHODS == ("multiplicative", "additive", "shin", "power", "odds_ratio")

    def odds(q: float) -> float:
        return q / (1 - q)

    for home_ml, away_ml in ((-200, 170), (170, -200), (-500, 375), (-110, -105), (-110, -110), (120, -140)):
        h, a = mk.implied_prob(home_ml), mk.implied_prob(away_ml)
        p = {method: mk.devig_home_prob(home_ml, away_ml, method) for method in mk.DEVIG_METHODS}
        for method, value in p.items():
            assert 0 < value < 1
            assert abs(value + mk.devig_home_prob(away_ml, home_ml, method) - 1) < 1e-9  # the two sides sum to 1
        assert p["multiplicative"] == novig_home_prob(home_ml, away_ml)  # today's method, unchanged
        assert abs(p["additive"] - (h - (h + a - 1) / 2)) < 1e-12  # the same amount off each side
        # Power: both implied probabilities raised to one exponent.
        assert abs(np.log(p["power"]) / np.log(h) - np.log(1 - p["power"]) / np.log(a)) < 1e-7
        # Odds ratio: both sides' odds cut by one factor.
        assert abs(odds(h) / odds(p["odds_ratio"]) - odds(a) / odds(1 - p["odds_ratio"])) < 1e-7
        # Shin: one share of insider money z explains both prices.
        z = [(q * q / (h + a) - v * v) / (v * (1 - v)) for q, v in ((h, p["shin"]), (a, 1 - p["shin"]))]
        assert abs(z[0] - z[1]) < 1e-9 and 0 < z[0] < 1
        assert abs(p["shin"] - p["additive"]) < 1e-9  # with two outcomes Shin and additive are the same number
    for method in mk.DEVIG_METHODS:  # a price with no margin is left as it is
        assert abs(mk.devig_home_prob(150, -150, method) - 0.4) < 1e-9
    for home_ml, away_ml in ((-200, 170), (-500, 375)):  # the other methods take more margin off the underdog
        base = mk.devig_home_prob(home_ml, away_ml, "multiplicative")
        assert all(mk.devig_home_prob(home_ml, away_ml, m) > base + 1e-4 for m in ("additive", "power", "odds_ratio"))


def test_devig_keeps_a_missing_price_missing_and_refuses_an_unknown_method():
    for method in mk.DEVIG_METHODS:
        assert mk.devig_home_prob(None, -110, method) is None and mk.devig_home_prob(-110, None, method) is None
    with pytest.raises(ValueError):
        mk.devig_home_prob(-110, -110, "basic")


def test_market_logit_is_the_clipped_log_odds_of_the_chosen_method():
    df = frame()
    df.loc[0, "home_ml"] = np.nan
    df.loc[1, ["home_ml", "away_ml"]] = [-100000.0, 5000.0]
    feats = add_features(df, EloParams())
    assert np.allclose(ft.market_logit(df, "multiplicative"), feats["market_logit"], equal_nan=True)
    power = ft.market_logit(df, "power")
    assert list(power.index) == list(df.index)
    assert np.isnan(power[0]) and np.isclose(power[1], np.log(0.99 / 0.01))  # missing stays missing; clipped at 99%
    p = mk.devig_home_prob(df.loc[2, "home_ml"], df.loc[2, "away_ml"], "power")
    assert np.isclose(power[2], np.log(p / (1 - p)))


def test_logit_fit_takes_row_weights():
    feats = add_features(frame(), EloParams())
    train = feats[feats["home_win"].notna()].copy()
    train.loc[train.index[0], "market_logit"] = np.nan  # a row the fit must drop, with its weight
    plain = LogitModel.fit(train, BLEND_FEATURES)
    ones = LogitModel.fit(train, BLEND_FEATURES, weights=pd.Series(1.0, index=train.index))
    assert np.allclose(ones.coef, plain.coef) and np.isclose(ones.intercept, plain.intercept)
    recent = train["season"] >= 2021
    doubled = LogitModel.fit(pd.concat([train, train[recent]]), BLEND_FEATURES)
    weighted = LogitModel.fit(train, BLEND_FEATURES, weights=pd.Series(np.where(recent, 2.0, 1.0), index=train.index))
    assert np.allclose(weighted.coef, doubled.coef, atol=1e-3)  # weight 2 is the same as having the row twice
    assert not np.allclose(weighted.coef, plain.coef, atol=1e-2)
    for bad in (-1.0, np.nan):
        with pytest.raises(ValueError):
            LogitModel.fit(train, BLEND_FEATURES, weights=pd.Series(bad, index=train.index))


def lines_frame() -> pd.DataFrame:
    """The fixture schedule with prices and lines that vary from game to game."""
    df = frame()
    home_favoured = df["home_ml"] < 0
    step = df.index % 3
    favourite, underdog = -150.0 - 50 * step, 130.0 + 40 * step
    df["home_ml"] = np.where(home_favoured, favourite, underdog)
    df["away_ml"] = np.where(home_favoured, underdog, favourite)
    df["spread_line"] = np.where(home_favoured, 3.0, -3.0) + df.index % 5 - 2.0
    df["total_line"] = 40.0 + df.index % 7 * 1.5
    return df


def _idea_columns(preds: pd.DataFrame) -> list[str]:
    return [col for col in preds if col.startswith(IDEA_PREFIXES)]


def test_idea_preds_fit_every_variant_on_the_seasons_before_the_test_season(monkeypatch):
    df = lines_frame()
    no_line = df[(df["season"] == 2022) & (df["week"] == 2)].index[0]
    df.loc[no_line, ["home_ml", "away_ml"]] = np.nan
    base = candidate_preds(df, [2021, 2022], window=3)
    seen = []
    real_fit = LogitModel.fit.__func__

    def spy(cls, train, features, weights=None):
        seen.append((list(features), train, weights))
        return real_fit(cls, train, features) if weights is None else real_fit(cls, train, features, weights=weights)

    monkeypatch.setattr(LogitModel, "fit", classmethod(spy))
    preds = bt.idea_preds(df, [2021, 2022], window=3)
    # Same games and the same baseline as the step 14 bench: only games with a price.
    assert list(preds["game_id"]) == list(base["game_id"]) and len(preds) == 29
    assert np.allclose(preds["p_blend"], base["p_blend"])
    # No fit ever sees the test season or a later one.
    assert seen and all(set(train["season"]) <= {2018, 2019, 2020} or set(train["season"]) <= {2019, 2020, 2021}
                        for _, train, _ in seen)
    fitted = [features for features, _, _ in seen]
    for method in ("additive", "shin", "power", "odds_ratio"):  # one fit per test season, in place of market_logit
        assert fitted.count([f"market_logit_{method}", *BASE_FEATURES]) == 2
    for extra in (["spread_pts"], ["total_pts"], ["spread_pts", "total_pts"], ["spread_per_total"]):
        assert fitted.count([*BLEND_FEATURES, *extra]) == 2
    # Recency: the blend's own inputs, each training row weighted by its age in seasons.
    assert bt.RECENCY_HALF_LIVES == (2, 4, 8)
    weighted = [(train, weights) for features, train, weights in seen if weights is not None]
    assert len(weighted) == 6 and all(features == BLEND_FEATURES for features, _, w in seen if w is not None)
    for season in (2021, 2022):
        found = set()
        for train, weights in weighted:
            if train["season"].max() == season - 1:
                age = season - 1 - train["season"]
                found |= {h for h in (2, 4, 8) if np.allclose(weights.reindex(train.index), 0.5 ** (age / h))}
        assert found == {2, 4, 8}
    cols = _idea_columns(preds)
    assert sorted(cols) == sorted([
        "p_devig_additive", "p_devig_shin", "p_devig_power", "p_devig_odds_ratio",
        "p_in_spread", "p_in_total", "p_in_both", "p_in_ratio",
        "p_recency_2", "p_recency_4", "p_recency_8",
    ])
    assert all(preds[col].between(0, 1).all() and not np.allclose(preds[col], preds["p_blend"]) for col in cols)
    assert np.allclose(preds["p_devig_shin"], preds["p_devig_additive"])
    assert np.allclose(preds["spread_pts"], preds["spread_line"] / 7)
    assert np.allclose(preds["total_pts"], (preds["total_line"] - 45) / 10)
    assert np.allclose(preds["spread_per_total"], 10 * preds["spread_line"] / preds["total_line"])


def test_line_input_variants_fall_back_to_the_blend_where_a_line_is_missing():
    df = lines_frame()
    week1 = df[(df["season"] == 2022) & (df["week"] == 1)].index
    df.loc[week1[0], "spread_line"] = np.nan
    df.loc[week1[1], "total_line"] = np.nan
    preds = bt.idea_preds(df, [2022], window=3).set_index("game_id")
    no_spread, no_total = preds.loc[df.loc[week1[0], "game_id"]], preds.loc[df.loc[week1[1], "game_id"]]
    for col in ("p_in_spread", "p_in_both", "p_in_ratio"):  # never an invented line
        assert no_spread[col] == no_spread["p_blend"]
    assert no_spread["p_in_total"] != no_spread["p_blend"]
    for col in ("p_in_total", "p_in_both", "p_in_ratio"):
        assert no_total[col] == no_total["p_blend"]
    assert no_total["p_in_spread"] != no_total["p_blend"]


def test_idea_preds_never_use_a_result_from_the_test_week_or_later():
    df = lines_frame()
    got = bt.idea_preds(df, [2022], window=3)
    cols = _idea_columns(got)
    week5 = df.loc[(df["season"] == 2022) & (df["week"] == 5), "kickoff_utc"].min()
    after = bt.idea_preds(_flip_scores(df, df["kickoff_utc"] >= week5), [2022], window=3)
    early = (got["week"] < 5).to_numpy()
    assert early.any() and list(after["game_id"]) == list(got["game_id"])
    assert all(np.allclose(got.loc[early, col], after.loc[early, col]) for col in cols)
    # Results of an earlier season do move every variant: that is what it learns from.
    earlier = bt.idea_preds(_flip_scores(df, df["season"] == 2021), [2022], window=3)
    assert all(not np.allclose(got[col], earlier[col]) for col in cols)


def _overconfident_blend(per_season: int = 4000) -> pd.DataFrame:
    """Walk-forward style rows whose blend is too sure of itself: true log-odds are half the blend's, less 0.15."""
    rng = np.random.default_rng(3)
    rows = []
    for season in (2019, 2020, 2021, 2022):
        truth = rng.uniform(0.15, 0.85, per_season)
        z = np.log(truth / (1 - truth))
        rows.append(pd.DataFrame({"season": season, "p_true": truth, "p_blend": 1 / (1 + np.exp(-(2 * z + 0.3))),
                                  "home_win": (rng.uniform(size=per_season) < truth).astype(float)}))
    return pd.concat(rows, ignore_index=True)


def test_calibration_is_fitted_on_earlier_seasons_only():
    preds = _overconfident_blend()
    season = preds["season"]
    late = season >= 2021
    flipped = preds.assign(home_win=np.where(late, 1 - preds["home_win"], preds["home_win"]))
    for method in ("platt", "isotonic"):
        got = bt.calibrated(preds, method)
        assert list(got.index) == list(preds.index)
        # The first season has nothing earlier to learn from: missing, not invented.
        assert got[season == 2019].isna().all() and got[season > 2019].between(0.01, 0.99).all()
        after = bt.calibrated(flipped, method)
        assert np.allclose(got[season == 2021], after[season == 2021])  # its own and later results: no effect
        assert not np.allclose(got[season == 2022], after[season == 2022])  # 2021 results do teach 2022
    with pytest.raises(ValueError):
        bt.calibrated(preds, "beta")


def test_calibration_pulls_an_overconfident_blend_back_to_the_truth():
    preds = _overconfident_blend()
    last = preds["season"] == 2022
    y = preds.loc[last, "home_win"].to_numpy()
    raw = log_loss(preds.loc[last, "p_blend"].to_numpy(), y)
    for method, tolerance in (("platt", 0.012), ("isotonic", 0.035)):  # Platt on raw probability misses by 0.025
        got = bt.calibrated(preds, method)[last]
        assert (got - preds.loc[last, "p_true"]).abs().mean() < tolerance
        assert log_loss(got.to_numpy(), y) < raw - 0.05
    # Isotonic never reorders the picks, and never says 0% or 100%.
    one_season = bt.calibrated(preds[preds["season"] <= 2020], "isotonic")[preds["season"] == 2020]
    order = np.argsort(preds.loc[preds["season"] == 2020, "p_blend"].to_numpy())
    assert (np.diff(one_season.to_numpy()[order]) >= 0).all()
    extreme = preds[preds["season"] <= 2020].assign(home_win=lambda d: (d["p_blend"] > 0.5).astype(float))
    sure = bt.calibrated(extreme, "isotonic")[extreme["season"] == 2020]
    assert sure.min() == 0.01 and sure.max() == 0.99


# ---- Step 14b idea 5: offence and defence split with success rate (clauses E1 to E3) ----


def _split_row(game_id: str, team: str, plays: float, epa: float, success: float) -> dict:
    return {"game_id": game_id, "team": team, "plays": plays, "epa": epa, "success": success}


def test_offence_defence_gives_each_team_its_own_rates_and_its_opponents():
    got = ft.offence_defence([
        _split_row("g1", "KC", 50, 10.0, 25),  # 0.2 EPA per play, half the plays succeed
        _split_row("g1", "BUF", 40, -4.0, 16),  # -0.1 EPA per play, 40% succeed
        _split_row("g2", "KC", 60, 6.0, 30),
        _split_row("g2", "LV", 0, 0.0, 0),  # no plays on one side: the game is left out for both teams
        _split_row("g3", "MIA", 55, 5.5, 22),  # only one side in the file: left out
    ])
    assert list(got.columns) == ["game_id", "team", "off_epa", "def_epa", "off_sr", "def_sr"]
    assert got[["game_id", "team"]].to_numpy().tolist() == [["g1", "KC"], ["g1", "BUF"]]
    assert np.allclose(got[["off_epa", "def_epa", "off_sr", "def_sr"]].to_numpy(),
                       [[0.2, -0.1, 0.5, 0.4], [-0.1, 0.2, 0.4, 0.5]])  # allowed = what the opponent's offence did


def _fixture_split(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g in df[df["status"] == "final"].itertuples():
        if "LV" in (g.home_team, g.away_team):
            continue  # LV never gets a rating
        rows += [_split_row(g.game_id, g.home_team, 60, g.home_score / 4 - 5, 20 + g.home_score / 2),
                 _split_row(g.game_id, g.away_team, 60, g.away_score / 4 - 5, 20 + g.away_score / 2)]
    return ft.offence_defence(rows)


def test_split_preds_fit_on_past_seasons_and_fall_back_to_the_blend_without_a_rating(monkeypatch):
    df = lines_frame()
    split = _fixture_split(df)
    seen = []
    real_fit = LogitModel.fit.__func__

    def spy(cls, train, features, weights=None):
        seen.append((list(features), set(train["season"])))
        return real_fit(cls, train, features)

    monkeypatch.setattr(LogitModel, "fit", classmethod(spy))
    preds = bt.split_preds(df, [2022], split, window=3)
    base = bt.idea_preds(df, [2022], window=3)
    assert list(preds["game_id"]) == list(base["game_id"]) and np.allclose(preds["p_blend"], base["p_blend"])
    assert bt.SPLIT_HALF_LIVES == (4, 8, 16)
    lv = (preds["home_team"] == "LV") | (preds["away_team"] == "LV")
    assert lv.any() and not lv.all()
    for h in (4, 8, 16):
        epa = [f"off_epa_diff_{h}", f"def_epa_diff_{h}"]
        rate = [f"off_sr_diff_{h}", f"def_sr_diff_{h}"]
        for col, extra in ((f"p_split_{h}", epa), (f"p_split_sr_{h}", epa + rate)):
            fits = [seasons for features, seasons in seen if features == [*BLEND_FEATURES, *extra]]
            assert len(fits) == 1 and fits[0] == {2019, 2020, 2021}  # never the test season
            assert preds[col].between(0, 1).all()
            assert np.allclose(preds.loc[lv, col], preds.loc[lv, "p_blend"])  # no rating: the blend's own number
            assert not np.allclose(preds.loc[~lv, col], preds.loc[~lv, "p_blend"])
        # Each input is a pregame rating difference, home minus away, on a fixed scale (EPA x 10, success rate x 20).
        for name, source, scale in ((epa[0], "off_epa", 10), (epa[1], "def_epa", 10),
                                    (rate[0], "off_sr", 20), (rate[1], "def_sr", 20)):
            want = scale * epa_diff(df, split[["game_id", "team", source]].rename(columns={source: "net_epa"}), h)
            assert np.allclose(preds[name], want[df["game_id"].isin(preds["game_id"])], equal_nan=True)
    assert preds.loc[lv, "off_epa_diff_4"].isna().all()  # missing stays missing


def test_split_preds_never_use_a_result_from_the_test_week_or_later():
    df = lines_frame()
    got = bt.split_preds(df, [2022], _fixture_split(df), window=3)
    cols = [col for col in got if col.startswith("p_split_")]
    week5 = df.loc[(df["season"] == 2022) & (df["week"] == 5), "kickoff_utc"].min()
    later = _flip_scores(df, df["kickoff_utc"] >= week5)
    after = bt.split_preds(later, [2022], _fixture_split(later), window=3)
    early = (got["week"] < 5).to_numpy()
    assert len(cols) == 6 and early.any()
    assert all(np.allclose(got.loc[early, col], after.loc[early, col]) for col in cols)
