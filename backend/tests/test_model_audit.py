"""Step 18a audit: executable proof for the findings in docs/model/AUDIT.md.

Each test names the finding it proves. A failure here is a real defect in the
model code (lane modelc's), not something to patch in this file.
"""

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from nflpi import jobs
from nflpi.analytics import backtest as bt
from nflpi.analytics.backtest import _elo_frames, predict_season
from nflpi.ingestion import nflverse
from nflpi.models import Game, Prediction
from nflpi.predictions import engine
from nflpi.predictions import model as model_mod
from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import BLEND_FEATURES, add_features, games_frame
from tests.conftest import CURRENT, schedule_rows

WINDOW = 3  # conftest sets TRAIN_WINDOW_SEASONS=3
PREGAME = [*BLEND_FEATURES, "home_elo", "away_elo", "elo_prob", "market_prob", "home_prev_qb", "away_prev_qb"]
PROBS = ["p_home", "p_elo", "p_logistic", "p_market", "p_blend"]
ROUNDING = 6e-5  # the live path stores four decimals


def frame() -> pd.DataFrame:
    """The bench's own input: schedule rows straight from the parser (as `jobs.backtest` builds it)."""
    games = nflverse.parse_games(schedule_rows(), 2018)
    for g in games:
        g["home_ml"], g["away_ml"] = g.pop("_home_ml"), g.pop("_away_ml")
        g.pop("_spread"), g.pop("_total")
    return games_frame(games)


def _flip_scores(df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    out = df.copy()
    out.loc[mask, ["home_score", "away_score"]] = out.loc[mask, ["away_score", "home_score"]].to_numpy()
    return out


def _spy_fits(monkeypatch) -> list[tuple[set[int], dict]]:
    """Record the seasons and the fitted weights of every model fit."""
    seen: list[tuple[set[int], dict]] = []
    real_fit = model_mod.LogitModel.fit.__func__

    def spy(cls, df, features, weights=None):
        fitted = real_fit(cls, df, features, weights)
        seen.append((set(df["season"]), fitted.as_dict()))
        return fitted

    monkeypatch.setattr(model_mod.LogitModel, "fit", classmethod(spy))
    return seen


def _swap(game: Game) -> None:
    game.home_score, game.away_score = game.away_score, game.home_score


def _history(session, game_id: str) -> list[Prediction]:
    return session.scalars(select(Prediction).where(Prediction.game_id == game_id).order_by(Prediction.id)).all()


# --- A3: nothing known only after kickoff reaches a game's own features or probability ---

def test_bench_features_and_probability_ignore_the_games_own_and_later_scores():
    df = frame()
    season = CURRENT - 1
    in_season = df.index[df["season"] == season]
    target = in_season[len(in_season) // 2]

    before = predict_season(_elo_frames(df), season, WINDOW)
    after = predict_season(_elo_frames(_flip_scores(df, df.index >= target)), season, WINDOW)

    assert before.index.equals(after.index)
    upto = before.index <= target
    pd.testing.assert_frame_equal(before.loc[upto, [*PREGAME, *PROBS]], after.loc[upto, [*PREGAME, *PROBS]])
    # The rewrite was real: the target's result changed, and later games did see it.
    assert before.loc[target, "home_win"] != after.loc[target, "home_win"]
    assert not np.allclose(before.loc[~upto, "elo_diff"], after.loc[~upto, "elo_diff"])


def test_live_features_and_probability_ignore_the_games_own_and_later_scores(loaded):
    assert engine.backfill_season(loaded, CURRENT) > 0
    elo = EloParams(**engine.active_model(loaded).params["elo"])
    finals = loaded.scalars(
        select(Game).where(Game.season == CURRENT, Game.status == "final").order_by(Game.kickoff_utc, Game.game_id)
    ).all()
    target = finals[len(finals) // 2]

    def pregame() -> pd.Series:
        f = add_features(engine.load_frame(loaded), elo)
        return f.loc[f["game_id"] == target.game_id, PREGAME].iloc[0]

    first = _history(loaded, target.game_id)
    features_before = pregame()
    assert len(first) == 1

    for g in finals:
        if (g.kickoff_utc, g.game_id) >= (target.kickoff_utc, target.game_id):
            _swap(g)
    loaded.commit()
    engine.refresh_predictions(loaded, game_ids=[target.game_id], kind="backfill")

    # Same inputs hash: the insert-only log gets no new row, so the probability is unchanged.
    assert [p.id for p in _history(loaded, target.game_id)] == [first[0].id]
    pd.testing.assert_series_equal(features_before, pregame())

    # Control: an EARLIER result of one of the two teams does move the prediction.
    teams = {target.home_team, target.away_team}
    earlier = loaded.scalars(
        select(Game)
        .where(Game.status == "final", Game.kickoff_utc < target.kickoff_utc,
               Game.home_team.in_(teams) | Game.away_team.in_(teams))
        .order_by(Game.kickoff_utc.desc(), Game.game_id.desc())
        .limit(1)
    ).one()
    _swap(earlier)
    loaded.commit()
    engine.refresh_predictions(loaded, game_ids=[target.game_id], kind="backfill")
    history = _history(loaded, target.game_id)
    assert len(history) == 2
    assert history[1].features["elo_diff"] != history[0].features["elo_diff"]


# --- A2: the bench and the live path build the same features and the same probability ---

def test_bench_and_live_path_agree_on_features_and_probability(loaded):
    engine.backfill_season(loaded, CURRENT)
    live = {p.game_id: p for p in loaded.scalars(select(Prediction).where(Prediction.kind == "backfill"))}
    bench = predict_season(_elo_frames(frame()), CURRENT, WINDOW).set_index("game_id")

    assert len(bench) > 0 and set(live) == set(bench.index)
    for game_id, p in live.items():
        row = bench.loc[game_id]
        assert p.features["used_market"] is True and p.features["market_kind"] == "closing"
        for feature in BLEND_FEATURES:
            assert p.features[feature] == pytest.approx(row[feature], abs=ROUNDING), (game_id, feature)
        assert p.features["stats_only_prob"] == pytest.approx(row["p_logistic"], abs=ROUNDING), game_id
        assert p.market_home_prob == pytest.approx(row["p_market"]), game_id
        assert p.home_win_prob == pytest.approx(row["p_blend"], abs=ROUNDING), game_id


# --- A5: the fit for season S uses no game from season S or later ---

def test_walk_forward_fit_for_a_season_uses_no_game_from_that_season_or_later(monkeypatch):
    seen = _spy_fits(monkeypatch)
    tuned: list[list[int]] = []
    real_tune = bt.tune_elo

    def spy_tune(frames, seasons):
        tuned.append(list(seasons))
        return real_tune(frames, seasons)

    monkeypatch.setattr(bt, "tune_elo", spy_tune)
    df = frame()

    for season in (CURRENT - 2, CURRENT - 1):
        seen.clear()
        tuned.clear()
        predict_season(_elo_frames(df), season, WINDOW)
        allowed = set(range(season - WINDOW, season))
        assert seen and all(seasons and seasons <= allowed for seasons, _ in seen)
        assert tuned == [sorted(allowed)]

    # Black box: rewriting every result from the test season onward changes no fitted weight.
    season = CURRENT - 1
    seen.clear()
    base = predict_season(_elo_frames(df), season, WINDOW)
    weights = [fitted for _, fitted in seen]
    seen.clear()
    rewritten = predict_season(_elo_frames(_flip_scores(df, df["season"] >= season)), season, WINDOW)
    assert weights and [fitted for _, fitted in seen] == weights
    assert base[["elo_k", "elo_hfa"]].iloc[0].tolist() == rewritten[["elo_k", "elo_hfa"]].iloc[0].tolist()
    assert np.array_equal(base["p_home"].to_numpy(), rewritten["p_home"].to_numpy())


def test_live_model_is_fitted_only_on_seasons_before_the_one_it_predicts(loaded, monkeypatch):
    active = engine.active_model(loaded)
    assert active.trained_through_season == CURRENT - 1
    assert active.params["train_seasons"] == list(range(CURRENT - WINDOW, CURRENT))

    # Rewriting every result of the current season and refitting gives the very same model.
    for g in loaded.scalars(select(Game).where(Game.season == CURRENT, Game.status == "final")):
        _swap(g)
    loaded.commit()
    assert engine.train(loaded, through_season=CURRENT - 1).name == active.name

    # The scheduled job asks for the season before the current one, never the current one.
    asked: list[int] = []
    monkeypatch.setattr(engine, "train", lambda session, through_season: asked.append(through_season))
    jobs.train(loaded)
    assert asked == [CURRENT - 1]
