"""Post-hoc diagnostic, NOT a candidate (cannot ship): do the recency results depend on the fit penalty?

Both reviewers noted that row weights below 1 also strengthen the fit's fixed penalty. This reruns the three recency
variants with weights rescaled to mean 1 (same recency shape, same penalty as the blend) on the TUNE seasons only.
The confirm seasons are not touched. Run from backend/: uv run python <this file>
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd

from nflpi.analytics import backtest as bt
from nflpi.analytics.metrics import paired_gain
from nflpi.predictions.features import BLEND_FEATURES
from nflpi.predictions.model import LogitModel

spec = importlib.util.spec_from_file_location("ideas", Path(__file__).parent / "ideas.py")
ideas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ideas)

frames = bt._elo_frames(ideas.games())
rows = []
for season in ideas.TUNE:
    test = bt.predict_season(frames, season, 10)
    _, train = bt._train_rows(frames, season, 10)
    train = train.dropna(subset=["market_logit"])
    for h in bt.RECENCY_HALF_LIVES:
        raw = 0.5 ** ((season - 1 - train["season"]) / h)
        for name, weights in ((f"raw_{h}", raw), (f"mean1_{h}", raw / raw.mean())):
            test[name] = LogitModel.fit(train, BLEND_FEATURES, weights=weights).predict(test)
    rows.append(test[test["p_market"].notna()])
preds = pd.concat(rows, ignore_index=True)
y, blend = preds["home_win"].to_numpy(), preds["p_blend"].to_numpy()
print(json.dumps({"seasons": "tune only, 2012 to 2021", "games": len(preds), "tune_gain": {
    name: paired_gain(preds[name].to_numpy(), blend, y)["log_loss_gain"]
    for h in bt.RECENCY_HALF_LIVES for name in (f"raw_{h}", f"mean1_{h}")}}, indent=1, allow_nan=False))
