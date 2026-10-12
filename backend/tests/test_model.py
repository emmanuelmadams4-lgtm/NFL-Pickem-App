import numpy as np
import pandas as pd
from sqlalchemy import select

from nflpi.analytics.backtest import _elo_frames, predict_season
from nflpi.analytics.metrics import brier, calibration, log_loss, wilson_ci
from nflpi.ingestion import nflverse
from nflpi.models import Prediction
from nflpi.predictions import engine
from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.features import add_features, games_frame
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
