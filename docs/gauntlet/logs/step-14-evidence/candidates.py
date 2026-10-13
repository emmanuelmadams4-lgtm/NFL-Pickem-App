"""Print evidence for the in-season blend and EPA rating candidates."""

import json

import pandas as pd

from nflpi.analytics.backtest import EPA_HALF_LIVES, candidate_preds, evaluate
from nflpi.analytics.metrics import summarize
from nflpi.ingestion import nflverse
from nflpi.predictions.features import team_game_epa

games = nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)
frame = (
    pd.DataFrame(games)
    .rename(columns={"_home_ml": "home_ml", "_away_ml": "away_ml"})
    .drop(columns=["_spread", "_total"])
    .sort_values(["kickoff_utc", "game_id"])
    .reset_index(drop=True)
)
epa_rows = [row for season in range(2002, 2026)
            for row in nflverse.fetch_csv(f"stats_team/stats_team_week_{season}.csv")]
epa = team_game_epa(epa_rows)
preds = candidate_preds(frame, list(range(2012, 2026)), epa=epa)
confirm = preds[preds["season"].isin(range(2022, 2026))]


def baseline(rows: pd.DataFrame) -> dict:
    """Summarize market and blend predictions on the same rows."""
    y = rows["home_win"].to_numpy()
    return {model: summarize(rows[f"p_{model}"].to_numpy(), y) for model in ("market", "blend")}


print(json.dumps({
    "games": len(preds),
    "epa_games": int(epa["game_id"].nunique()),
    "baseline": baseline(preds),
    "baseline_confirm": baseline(confirm),
    "candidates": evaluate(preds, {"inseason_refit": ["p_inseason"],
                                   "epa_rating": [f"p_epa_{h}" for h in EPA_HALF_LIVES]},
                           tune=list(range(2012, 2022)), confirm=list(range(2022, 2026))),
}, indent=1))
