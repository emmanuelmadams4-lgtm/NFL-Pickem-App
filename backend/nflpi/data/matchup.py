"""Matchup score, 0 to 100. BENCH CANDIDATE ONLY.

Nothing in predictions/, api/, analytics/ or jobs.py imports this module. It must win a walk-forward bench before
anything ships. No EPA term and no DVOA term. 50 is an even matchup; above 50 favours the home side.
"""

import math

import numpy as np
import pandas as pd

ELO_LOGIT_PER_100 = math.log(10) / 4  # the Elo logistic's own constant (400-point scale); nothing is fitted
MATCHUP_FORMULA = (
    "z_elo = (ln(10) / 4) * elo_diff, where elo_diff is the home-minus-away Elo gap divided by 100; "
    "z_market = market_logit (log-odds of the no-vig home probability), used only when asked for; "
    "z = mean of the available components; score = 100 / (1 + exp(-z)); NaN when elo_diff is NaN."
)


def matchup_components(frame: pd.DataFrame, include_market: bool = False) -> pd.DataFrame:
    """The z parts and how many fed the mean. Rows with a NaN elo_diff have no components."""
    z_elo = ELO_LOGIT_PER_100 * frame["elo_diff"].astype(float)
    market = (
        frame["market_logit"].astype(float) if "market_logit" in frame.columns else pd.Series(np.nan, index=frame.index)
    )
    z_market = market if include_market else pd.Series(np.nan, index=frame.index)
    parts = pd.DataFrame({"z_elo": z_elo, "z_market": z_market})
    parts["n_components"] = parts[["z_elo", "z_market"]].notna().sum(axis=1).where(z_elo.notna(), 0)
    return parts


def matchup_score(frame: pd.DataFrame, include_market: bool = False) -> pd.Series:
    parts = matchup_components(frame, include_market)
    z = parts[["z_elo", "z_market"]].mean(axis=1, skipna=True).where(parts["z_elo"].notna())
    return 100 / (1 + np.exp(-z))
