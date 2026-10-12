"""Team Elo ratings (FiveThirtyEight-style NFL Elo).

Ratings only move after a game is final, so a game's pre-game rating
never sees its own result or any later result.
"""

import math
from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class EloParams:
    k: float = 20.0
    hfa: float = 48.0  # home edge in Elo points, used for the update expectation
    revert: float = 1 / 3  # share pulled back to the mean between seasons
    mean: float = 1505.0

    def as_dict(self) -> dict:
        return asdict(self)


def expected_home(diff: float) -> float:
    return 1 / (1 + 10 ** (-diff / 400))


def run_elo(games: pd.DataFrame, params: EloParams) -> pd.DataFrame:
    """Add home_elo/away_elo (pre-game) and elo_prob to games sorted by kickoff."""
    ratings: dict[str, float] = {}
    season_of: dict[str, int] = {}
    home_pre, away_pre, prob = [], [], []
    for row in games.itertuples(index=False):
        for team in (row.home_team, row.away_team):
            if team not in ratings:
                ratings[team] = params.mean
            elif season_of[team] != row.season:
                ratings[team] = ratings[team] * (1 - params.revert) + params.mean * params.revert
            season_of[team] = row.season
        h, a = ratings[row.home_team], ratings[row.away_team]
        hfa = 0.0 if row.neutral_site else params.hfa
        p = expected_home(h - a + hfa)
        home_pre.append(h)
        away_pre.append(a)
        prob.append(p)
        if row.status == "final" and row.home_score is not None and not pd.isna(row.home_score):
            margin = row.home_score - row.away_score
            result = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
            winner_diff = (h - a + hfa) if margin >= 0 else (a - h - hfa)
            mult = math.log(abs(margin) + 1) * (2.2 / (winner_diff * 0.001 + 2.2))
            shift = params.k * mult * (result - p)
            ratings[row.home_team] = h + shift
            ratings[row.away_team] = a - shift
    out = games.copy()
    out["home_elo"] = home_pre
    out["away_elo"] = away_pre
    out["elo_prob"] = prob
    return out
