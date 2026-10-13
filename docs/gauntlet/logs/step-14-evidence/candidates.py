"""Print evidence for the in-season blend candidate."""

import json

import pandas as pd

from nflpi.analytics.backtest import candidate_preds, evaluate
from nflpi.analytics.metrics import summarize
from nflpi.ingestion import nflverse

games = nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)
frame = (
    pd.DataFrame(games)
    .rename(columns={"_home_ml": "home_ml", "_away_ml": "away_ml"})
    .drop(columns=["_spread", "_total"])
    .sort_values(["kickoff_utc", "game_id"])
    .reset_index(drop=True)
)
preds = candidate_preds(frame, list(range(2012, 2026)))
confirm = preds[preds["season"].isin(range(2022, 2026))]


def baseline(rows: pd.DataFrame) -> dict:
    """Summarize market and blend predictions on the same rows."""
    y = rows["home_win"].to_numpy()
    return {model: summarize(rows[f"p_{model}"].to_numpy(), y) for model in ("market", "blend")}


print(json.dumps({
    "games": len(preds),
    "baseline": baseline(preds),
    "baseline_confirm": baseline(confirm),
    "candidates": evaluate(preds, {"inseason_refit": ["p_inseason"]},
                           tune=list(range(2012, 2022)), confirm=list(range(2022, 2026))),
}, indent=1))
