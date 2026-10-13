import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

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
from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.features import BLEND_FEATURES, add_features, epa_diff, games_frame, team_game_epa
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
