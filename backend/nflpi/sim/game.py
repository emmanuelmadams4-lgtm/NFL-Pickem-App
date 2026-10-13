"""Monte Carlo simulation of one game's final score."""

from dataclasses import dataclass
from math import isfinite

import numpy as np

from nflpi.sim.distributions import DEFAULT_DISTRIBUTION, DISTRIBUTIONS, sample_regulation
from nflpi.sim.overtime import resolve_overtime
from nflpi.sim.params import SimParams, TeamFeatures

MAX_SIMULATIONS = 10_000_000
LEVELS = (0.5, 0.8, 0.95)
SAMPLING_LABEL = "Monte Carlo sampling error only; it is not the model's uncertainty"


@dataclass(frozen=True, eq=False)
class SimResult:
    a_score: np.ndarray
    b_score: np.ndarray
    n: int
    distribution: str
    neutral_site: bool
    spread: float | None
    total: float | None
    p_a_win: float
    p_b_win: float
    p_tie: float
    p_a_cover: float | None
    p_b_cover: float | None
    p_spread_push: float | None
    p_over: float | None
    p_under: float | None
    p_total_push: float | None
    expected_margin: float
    expected_total: float
    margin_intervals: dict[float, tuple[float, float]]
    total_intervals: dict[float, tuple[float, float]]
    sampling_error: dict[str, float | str]


def _intervals(x: np.ndarray) -> dict[float, tuple[float, float]]:
    return {
        level: (float(np.quantile(x, (1 - level) / 2, method="lower")),
                float(np.quantile(x, (1 + level) / 2, method="higher")))
        for level in LEVELS
    }


def _check_line(name: str, value: float | None, positive: bool) -> None:
    if value is not None and (not isfinite(value) or (positive and value <= 0)):
        raise ValueError(f"{name} must be finite{' and positive' if positive else ''}")


def simulate_game(
    team_a_features: TeamFeatures, team_b_features: TeamFeatures, n_simulations: int = 10_000, *,
    params: SimParams | None = None, seed: int | None = None, spread: float | None = None,
    total: float | None = None, neutral_site: bool = False, distribution: str = DEFAULT_DISTRIBUTION,
    playoff: bool = False,
) -> SimResult:
    """Simulate final scores of team A against team B.

    Conventions: margin M = a - b. `spread` is the quoted spread h for team A: A covers when M + h > 0,
    B covers when M + h < 0, push when M + h == 0. Over when a + b > total, under when <, push when ==.
    `neutral_site` is only recorded. Playoff games never end tied.
    """
    if isinstance(n_simulations, bool) or not isinstance(n_simulations, int) \
            or not 1 <= n_simulations <= MAX_SIMULATIONS:
        raise ValueError(f"n_simulations must be an int in 1..{MAX_SIMULATIONS}")
    if distribution not in DISTRIBUTIONS:
        raise ValueError(f"unknown distribution {distribution!r}; choose from {DISTRIBUTIONS}")
    _check_line("spread", spread, positive=False)
    _check_line("total", total, positive=True)
    rng = np.random.default_rng(seed)
    reg_a, reg_b = sample_regulation(
        distribution, team_a_features.expected_points, team_b_features.expected_points, n_simulations, rng, params
    )
    a, b = resolve_overtime(reg_a, reg_b, rng, params, playoff)
    margin, points = a - b, a + b
    n = n_simulations

    probs: dict[str, float] = {
        "p_a_win": float((margin > 0).mean()),
        "p_b_win": float((margin < 0).mean()),
        "p_tie": float((margin == 0).mean()),
    }
    if spread is not None:
        edge = margin + spread
        probs |= {"p_a_cover": float((edge > 0).mean()), "p_b_cover": float((edge < 0).mean()),
                  "p_spread_push": float((edge == 0).mean())}
    if total is not None:
        probs |= {"p_over": float((points > total).mean()), "p_under": float((points < total).mean()),
                  "p_total_push": float((points == total).mean())}
    error: dict[str, float | str] = {k: float(np.sqrt(p * (1 - p) / n)) for k, p in probs.items()}
    error["expected_margin"] = float(margin.std() / np.sqrt(n))
    error["expected_total"] = float(points.std() / np.sqrt(n))
    error["label"] = SAMPLING_LABEL
    return SimResult(
        a_score=a, b_score=b, n=n, distribution=distribution, neutral_site=neutral_site, spread=spread, total=total,
        p_a_win=probs["p_a_win"], p_b_win=probs["p_b_win"], p_tie=probs["p_tie"],
        p_a_cover=probs.get("p_a_cover"), p_b_cover=probs.get("p_b_cover"), p_spread_push=probs.get("p_spread_push"),
        p_over=probs.get("p_over"), p_under=probs.get("p_under"), p_total_push=probs.get("p_total_push"),
        expected_margin=float(margin.mean()), expected_total=float(points.mean()),
        margin_intervals=_intervals(margin), total_intervals=_intervals(points), sampling_error=error,
    )
