"""Walk-forward backtest.

To test season S, every choice (Elo settings, model weights, home rate) is
made on seasons before S only. Elo is online and only sees finished games.
The market line is the closing line, so it is a benchmark, not a fair
mid-week input; the "blend" model inherits that advantage and is labeled so.
"""

import numpy as np
import pandas as pd

from nflpi.analytics.metrics import bootstrap_ci, calibration, log_loss, summarize
from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES, add_features
from nflpi.predictions.model import LogitModel

ELO_GRID = [EloParams(k=k, hfa=h) for k in (15.0, 20.0, 25.0) for h in (30.0, 48.0, 65.0)]
MODELS = ["home", "elo", "logistic", "market", "blend"]
ABLATE = ["home_qb_change", "away_qb_change"]
LABELS = {
    "home": "Always pick home team",
    "elo": "Elo ratings only",
    "logistic": "Stats model (Elo + rest + QB + home)",
    "market": "Betting market (closing line)",
    "blend": "Stats model + market (uses closing line)",
}


def _elo_frames(df: pd.DataFrame) -> dict[EloParams, pd.DataFrame]:
    base = add_features(df, ELO_GRID[0])
    frames = {}
    for params in ELO_GRID:
        e = run_elo(df, params)
        f = base.copy()
        f[["home_elo", "away_elo", "elo_prob"]] = e[["home_elo", "away_elo", "elo_prob"]]
        f["elo_diff"] = (f["home_elo"] - f["away_elo"]) / 100
        frames[params] = f
    return frames


def tune_elo(frames: dict[EloParams, pd.DataFrame], seasons: list[int]) -> EloParams:
    def loss(params: EloParams) -> float:
        f = frames[params]
        m = f["season"].isin(seasons) & f["home_win"].notna()
        return log_loss(f.loc[m, "elo_prob"].to_numpy(), f.loc[m, "home_win"].to_numpy())

    return min(ELO_GRID, key=loss)


def predict_season(frames: dict[EloParams, pd.DataFrame], season: int, window: int) -> pd.DataFrame:
    train_seasons = list(range(season - window, season))
    params = tune_elo(frames, train_seasons)
    f = frames[params]
    train = f[f["season"].isin(train_seasons) & f["home_win"].notna()]
    test = f[(f["season"] == season) & (f["game_type"] == "REG") & f["home_win"].notna()].copy()

    home_rate = train.loc[train["home_field"] == 1, "home_win"].mean()
    test["p_home"] = np.where(test["home_field"] == 1, home_rate, 0.5)
    test["p_elo"] = test["elo_prob"]
    test["p_logistic"] = LogitModel.fit(train, BASE_FEATURES).predict(test)
    test["p_market"] = test["market_prob"]
    blend = LogitModel.fit(train.dropna(subset=["market_logit"]), BLEND_FEATURES)
    has_mkt = test["market_logit"].notna()
    test["p_blend"] = test["p_logistic"]
    test.loc[has_mkt, "p_blend"] = blend.predict(test[has_mkt])
    for feat in ABLATE:  # ablations: does each extra feature add value?
        keep = [x for x in BASE_FEATURES if x != feat]
        test[f"p_without_{feat}"] = LogitModel.fit(train, keep).predict(test)
    test["elo_k"], test["elo_hfa"] = params.k, params.hfa
    return test


def run_backtest(df: pd.DataFrame, seasons: list[int], window: int = 10) -> dict:
    frames = _elo_frames(df)
    preds = pd.concat([predict_season(frames, s, window) for s in seasons], ignore_index=True)
    # Compare every model on the same games: those with a market line.
    preds = preds[preds["p_market"].notna()]
    y = preds["home_win"].to_numpy()

    models = []
    for m in MODELS:
        p = preds[f"p_{m}"].to_numpy()
        models.append({"model": m, "label": LABELS[m], **summarize(p, y)})

    ablations = []
    base_ll = log_loss(preds["p_logistic"].to_numpy(), y)
    for feat in ABLATE:
        ll = log_loss(preds[f"p_without_{feat}"].to_numpy(), y)
        ablations.append({"feature": feat, "log_loss_without": ll, "log_loss_gain": ll - base_ll})

    by_season = []
    for s, g in preds.groupby("season"):
        yy = g["home_win"].to_numpy()
        row = {"season": int(s), "n": len(g)}
        for m in MODELS:
            row[m] = float(np.mean((g[f"p_{m}"].to_numpy() > 0.5) == (yy == 1)))
        by_season.append(row)

    comparisons = []
    correct = {m: ((preds[f"p_{m}"].to_numpy() > 0.5) == (y == 1)).astype(float) for m in MODELS}
    for a, b in (("logistic", "market"), ("blend", "market"), ("logistic", "elo"), ("logistic", "home")):
        diff = correct[a] - correct[b]
        lo, hi = bootstrap_ci(diff)
        comparisons.append(
            {"a": a, "b": b, "accuracy_diff": float(diff.mean()), "ci": [lo, hi], "significant": lo > 0 or hi < 0}
        )

    fav_split = []
    market_fav_home = preds["p_market"].to_numpy() > 0.5
    for m in MODELS:
        picks_home = preds[f"p_{m}"].to_numpy() > 0.5
        agrees = picks_home == market_fav_home
        ok = correct[m]
        fav_split.append(
            {
                "model": m,
                "picked_favorite": int(agrees.sum()),
                "favorite_accuracy": float(ok[agrees].mean()) if agrees.any() else None,
                "picked_underdog": int((~agrees).sum()),
                "underdog_accuracy": float(ok[~agrees].mean()) if (~agrees).any() else None,
            }
        )

    return {
        "seasons": [int(s) for s in seasons],
        "games": int(len(preds)),
        "models": models,
        "comparisons": comparisons,
        "ablations": ablations,
        "by_season": by_season,
        "calibration": {m: calibration(preds[f"p_{m}"].to_numpy(), y) for m in ("logistic", "blend", "market")},
        "favorite_split": fav_split,
        "elo_settings": sorted({(float(k), float(h)) for k, h in zip(preds["elo_k"], preds["elo_hfa"], strict=True)}),
    }
