"""Logistic regression on pre-game features, with plain-language factor breakdowns."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


@dataclass
class LogitModel:
    features: list[str]
    coef: list[float]
    intercept: float

    @classmethod
    def fit(cls, df: pd.DataFrame, features: list[str], weights: pd.Series | None = None) -> "LogitModel":
        """Fit a logistic model, optionally weighting each training row."""
        if weights is not None and (not np.isfinite(weights).all() or (weights < 0).any()):
            raise ValueError("weights must be finite and nonnegative")
        train = df.dropna(subset=[*features, "home_win"])
        lr = LogisticRegression(C=1.0, max_iter=1000)
        lr.fit(train[features].to_numpy(), train["home_win"].to_numpy(),
               sample_weight=weights.loc[train.index] if weights is not None else None)
        return cls(features, [float(c) for c in lr.coef_[0]], float(lr.intercept_[0]))

    def logit(self, x: pd.DataFrame) -> np.ndarray:
        return x[self.features].to_numpy() @ np.array(self.coef) + self.intercept

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return 1 / (1 + np.exp(-self.logit(x)))

    def predict_one(self, row: pd.Series) -> float:
        z = sum(c * float(row[f]) for f, c in zip(self.features, self.coef, strict=True)) + self.intercept
        return float(1 / (1 + np.exp(-z)))

    def contributions(self, row: pd.Series) -> dict[str, float]:
        """Each feature's push on the home team's log-odds (positive helps home)."""
        return {f: float(c * row[f]) for f, c in zip(self.features, self.coef, strict=True)}

    def as_dict(self) -> dict:
        return {"features": self.features, "coef": self.coef, "intercept": self.intercept}

    @classmethod
    def from_dict(cls, d: dict) -> "LogitModel":
        return cls(d["features"], d["coef"], d["intercept"])
