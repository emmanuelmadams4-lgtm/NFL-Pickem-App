"""Game-score simulator."""

from nflpi.sim import keys
from nflpi.sim.distributions import DEFAULT_DISTRIBUTION, DISTRIBUTIONS
from nflpi.sim.game import SimResult, simulate_game
from nflpi.sim.params import SimParams, TeamFeatures, learn_params, ot_era, regulation_scores

__all__ = [
    "DEFAULT_DISTRIBUTION", "DISTRIBUTIONS", "SimParams", "SimResult", "TeamFeatures", "keys", "learn_params", "ot_era",
    "regulation_scores", "simulate_game",
]
