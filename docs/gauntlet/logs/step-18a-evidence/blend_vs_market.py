"""Step 18a lookup: how often the blend's pick differs from the market's, and the live-equivalent weights."""

import pandas as pd

from nflpi.analytics.backtest import _elo_frames, predict_season, tune_elo
from nflpi.ingestion import nflverse
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES
from nflpi.predictions.model import LogitModel

frame = (
    pd.DataFrame(nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002))
    .rename(columns={"_home_ml": "home_ml", "_away_ml": "away_ml"})
    .drop(columns=["_spread", "_total"])
    .sort_values(["kickoff_utc", "game_id"])
    .reset_index(drop=True)
)
frames = _elo_frames(frame)
preds = pd.concat([predict_season(frames, s, 10) for s in range(2012, 2026)], ignore_index=True)
preds = preds[preds["p_market"].notna()]
differ = (preds["p_blend"] > 0.5) != (preds["p_market"] > 0.5)
right = (preds["p_blend"] > 0.5) == (preds["home_win"] == 1)
print("games", len(preds), "blend pick differs from market pick", int(differ.sum()), f"({differ.mean():.2%})")
print("when they differ, blend right", int(right[differ].sum()), "of", int(differ.sum()))
print("mean |p_blend - p_market|", round(float((preds["p_blend"] - preds["p_market"]).abs().mean()), 4),
      "; max", round(float((preds["p_blend"] - preds["p_market"]).abs().max()), 4))
print("correlation of p_blend and p_market", round(float(preds["p_blend"].corr(preds["p_market"])), 4))
seasons = list(range(2016, 2026))  # what `jobs train` uses for the 2026 season: the ten seasons before it
elo = tune_elo(frames, seasons)
train = frames[elo][frames[elo]["season"].isin(seasons) & frames[elo]["home_win"].notna()]
print("live-equivalent fit, seasons 2016-2025, Elo", elo.as_dict(), "rows", len(train))
print("stats model", LogitModel.fit(train, BASE_FEATURES).as_dict())
print("blend", LogitModel.fit(train.dropna(subset=["market_logit"]), BLEND_FEATURES).as_dict())
