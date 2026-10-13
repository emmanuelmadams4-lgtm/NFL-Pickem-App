"""Pre-game score estimates; the closing line is a benchmark with a timing advantage."""

from dataclasses import dataclass
from math import floor, isfinite

import numpy as np
import pandas as pd

from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import add_features

FORM_GAMES = 16
STATS_FEATURES = [
    "elo_diff", "home_field", "home_qb_change", "away_qb_change", "home_pf", "home_pa", "away_pf", "away_pa"
]
BLEND_FEATURES = ["implied_home", "implied_away", *STATS_FEATURES]


def implied_score(spread_line: float | None, total_line: float | None) -> tuple[float, float] | None:
    if spread_line is None or total_line is None:
        return None
    if not isfinite(spread_line) or not isfinite(total_line) or total_line <= 0 or abs(spread_line) > total_line:
        return None
    return (float((total_line + spread_line) / 2), float((total_line - spread_line) / 2))


def entry(points: float) -> int:
    return max(0, floor(points + 0.5))


def entry_pair(home: float, away: float) -> tuple[int, int]:
    if home % 1 == 0.5 and away % 1 == 0.5:
        return entry(home), max(0, floor(away))
    return entry(home), entry(away)


def tiebreak_score(spread_line: float | None, total_line: float | None) -> dict | None:
    implied = implied_score(spread_line, total_line)
    if implied is None:
        return None
    home, away = entry_pair(*implied)
    return {"home": home, "away": away, "method": "line_implied"}


def scoring_form(df: pd.DataFrame, games: int = FORM_GAMES) -> dict[str, list[float]]:
    history: dict[str, list[tuple[float, float]]] = {}
    result: dict[str, list[float]] = {key: [] for key in ("home_pf", "home_pa", "away_pf", "away_pa")}
    for row in df.itertuples(index=False):
        for side in ("home", "away"):
            team = getattr(row, f"{side}_team")
            past = history.get(team, [])[-games:] if games else []
            result[f"{side}_pf"].append(sum(pf for pf, _ in past) / len(past) if past else float("nan"))
            result[f"{side}_pa"].append(sum(pa for _, pa in past) / len(past) if past else float("nan"))
        if row.status == "final" and pd.notna(row.home_score) and pd.notna(row.away_score):
            home, away = float(row.home_score), float(row.away_score)
            history.setdefault(row.home_team, []).append((home, away))
            history.setdefault(row.away_team, []).append((away, home))
    return result


def add_score_features(df: pd.DataFrame, elo: EloParams) -> pd.DataFrame:
    out = add_features(df, elo)
    for key, values in scoring_form(out).items():
        out[key] = values
    implied = [
        implied_score(spread, total)
        for spread, total in zip(out["spread_line"], out["total_line"], strict=True)
    ]
    out["implied_home"] = [pair[0] if pair is not None else np.nan for pair in implied]
    out["implied_away"] = [pair[1] if pair is not None else np.nan for pair in implied]
    return out


@dataclass
class ScoreModel:
    features: list[str]
    home_coef: list[float]
    home_intercept: float
    away_coef: list[float]
    away_intercept: float

    @classmethod
    def fit(cls, df: pd.DataFrame, features: list[str]) -> "ScoreModel":
        train = df.loc[df["status"] == "final"].dropna(subset=[*features, "home_score", "away_score"])
        if len(train) < len(features) + 1:
            raise ValueError("Too few usable rows to fit a score model")
        x = np.column_stack((train[features].to_numpy(dtype=float), np.ones(len(train))))
        home = np.linalg.lstsq(x, train["home_score"].to_numpy(dtype=float), rcond=None)[0]
        away = np.linalg.lstsq(x, train["away_score"].to_numpy(dtype=float), rcond=None)[0]
        return cls(list(features), [float(v) for v in home[:-1]], float(home[-1]),
                   [float(v) for v in away[:-1]], float(away[-1]))

    def predict(self, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        values = x[self.features].to_numpy(dtype=float)
        valid = np.isfinite(values).all(axis=1)
        home = np.full(len(x), np.nan)
        away = np.full(len(x), np.nan)
        home[valid] = values[valid] @ np.asarray(self.home_coef) + self.home_intercept
        away[valid] = values[valid] @ np.asarray(self.away_coef) + self.away_intercept
        return home, away
