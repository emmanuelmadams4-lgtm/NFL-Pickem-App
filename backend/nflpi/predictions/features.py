"""Pre-game features. Every value here is known before kickoff."""

import numpy as np
import pandas as pd

from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.market import novig_home_prob

BASE_FEATURES = ["elo_diff", "home_field", "home_qb_change", "away_qb_change"]
# Tested and dropped: rest_diff (no log-loss gain in the 2012-2025 walk-forward backtest).
BLEND_FEATURES = ["market_logit", *BASE_FEATURES]


def games_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def qb_changes(df: pd.DataFrame) -> dict[str, list]:
    """Flag when a team's expected starter differs from its previous game's starter (same season)."""
    last: dict[str, tuple[int, str | None]] = {}
    cols: dict[str, list] = {"home_qb_change": [], "away_qb_change": [], "home_prev_qb": [], "away_prev_qb": []}
    for row in df.itertuples(index=False):
        for side, team, qb in (("home", row.home_team, row.home_qb), ("away", row.away_team, row.away_qb)):
            qb = qb if isinstance(qb, str) and qb else None
            prev = last.get(team)
            prev_qb = prev[1] if prev is not None and prev[0] == row.season else None
            cols[f"{side}_qb_change"].append(1.0 if qb and prev_qb and qb != prev_qb else 0.0)
            cols[f"{side}_prev_qb"].append(prev_qb)
            last[team] = (row.season, qb)
    return cols


def add_features(df: pd.DataFrame, elo: EloParams) -> pd.DataFrame:
    """df needs schedule columns plus home_ml/away_ml (may be NaN)."""
    out = run_elo(df, elo)
    out["elo_diff"] = (out["home_elo"] - out["away_elo"]) / 100
    out["home_field"] = (~out["neutral_site"].astype(bool)).astype(float)
    rest = (out["home_rest"].astype(float) - out["away_rest"].astype(float)).fillna(0) / 7
    out["rest_diff"] = rest.clip(-2, 2)
    for col, values in qb_changes(out).items():
        out[col] = values
    out["market_prob"] = [
        novig_home_prob(h, a) if not (pd.isna(h) or pd.isna(a)) else np.nan
        for h, a in zip(out["home_ml"], out["away_ml"], strict=True)
    ]
    p = out["market_prob"].clip(0.01, 0.99)
    out["market_logit"] = np.log(p / (1 - p))
    out["home_win"] = np.where(
        out["status"] == "final",
        np.where(
            out["home_score"] > out["away_score"], 1.0, np.where(out["home_score"] < out["away_score"], 0.0, np.nan)
        ),
        np.nan,
    )
    return out
