"""Score backtest; the closing line is a benchmark with a timing advantage."""

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from nflpi.analytics.metrics import bootstrap_ci
from nflpi.predictions.elo import EloParams
from nflpi.predictions.scores import BLEND_FEATURES, STATS_FEATURES, ScoreModel, add_score_features, entry

METHODS = ["implied", "stats", "blend"]
LABELS = {
    "implied": "Closing line implied score",
    "stats": "Stats model without the line",
    "blend": "Stats model with the closing line",
}


def is_tiebreak_slot(weekday: str, kickoff_utc: datetime) -> bool:
    return bool(weekday == "Monday" or
                (weekday == "Sunday" and kickoff_utc.astimezone(ZoneInfo("America/New_York")).hour >= 19))


def predict_season(frame: pd.DataFrame, season: int, window: int) -> pd.DataFrame:
    train = frame.loc[frame["season"].between(season - window, season - 1)]
    test = frame.loc[
        (frame["season"] == season) & (frame["game_type"] == "REG") & (frame["status"] == "final")
        & frame["home_score"].notna() & frame["away_score"].notna()
    ].copy()
    models = {
        "stats": ScoreModel.fit(train, STATS_FEATURES),
        "blend": ScoreModel.fit(train, BLEND_FEATURES),
    }
    for side in ("home", "away"):
        test[f"pred_implied_{side}"] = np.array(
            [entry(value) if pd.notna(value) else np.nan for value in test[f"implied_{side}"]], dtype=float
        )
    for method, model in models.items():
        home, away = model.predict(test)
        for side, values in (("home", home), ("away", away)):
            test[f"pred_{method}_{side}"] = np.array(
                [entry(value) if np.isfinite(value) else np.nan for value in values], dtype=float
            )
    return test


def summary(preds: pd.DataFrame) -> dict:
    n = len(preds)
    errors: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    methods = []
    for method in METHODS:
        home = preds[f"pred_{method}_home"].to_numpy(dtype=float)
        away = preds[f"pred_{method}_away"].to_numpy(dtype=float)
        actual_home = preds["home_score"].to_numpy(dtype=float)
        actual_away = preds["away_score"].to_numpy(dtype=float)
        team = (np.abs(home - actual_home) + np.abs(away - actual_away)) / 2
        total = np.abs(home + away - actual_home - actual_away)
        errors[method] = (team, total)
        methods.append({"method": method, "label": LABELS[method],
                        "team_mae": float(team.mean()) if n else None,
                        "total_mae": float(total.mean()) if n else None})
    comparisons = []
    for candidate in METHODS[1:]:
        team_gain = errors["implied"][0] - errors[candidate][0]
        total_gain = errors["implied"][1] - errors[candidate][1]
        team_ci = list(bootstrap_ci(team_gain)) if n else [None, None]
        total_ci = list(bootstrap_ci(total_gain)) if n else [None, None]
        total_mean = float(total_gain.mean()) if n else None
        comparisons.append({"candidate": candidate, "team_mae_gain": float(team_gain.mean()) if n else None,
                            "team_ci": team_ci, "total_mae_gain": total_mean, "total_ci": total_ci,
                            "wins": bool(n and team_ci[0] > 0 and total_mean >= 0)})
    return {"games": n, "methods": methods, "comparisons": comparisons}


def pick_winner(comparisons: list[dict]) -> str | None:
    winners = [row for row in comparisons if row["wins"]]
    return max(winners, key=lambda row: row["team_mae_gain"])["candidate"] if winners else None


def run_score_backtest(df: pd.DataFrame, seasons: list[int], window: int = 10) -> dict:
    frame = add_score_features(df, EloParams())
    predictions = pd.concat([predict_season(frame, season, window) for season in seasons], ignore_index=True)
    prediction_cols = [f"pred_{method}_{side}" for method in METHODS for side in ("home", "away")]
    predictions = predictions.dropna(subset=prediction_cols)
    overall = summary(predictions)
    by_season = []
    for season in seasons:
        season_report = summary(predictions.loc[predictions["season"] == season])
        row = {"season": int(season), "n": season_report["games"]}
        row.update({method["method"]: {"team_mae": method["team_mae"], "total_mae": method["total_mae"]}
                    for method in season_report["methods"]})
        by_season.append(row)
    slots = [is_tiebreak_slot(weekday, kickoff) for weekday, kickoff in
             zip(predictions["weekday"], predictions["kickoff_utc"], strict=True)]
    return {
        "seasons": [int(season) for season in seasons],
        **overall,
        "by_season": by_season,
        "tiebreak_slots": summary(predictions.loc[slots]),
        "ships": pick_winner(overall["comparisons"]),
    }
