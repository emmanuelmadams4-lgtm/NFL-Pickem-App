"""Simulator inputs and the parameters learned from past games (walk-forward: the caller passes only past rows)."""

from dataclasses import dataclass
from math import isfinite

import numpy as np

MIN_TRAIN_GAMES = 200
MIN_ERA_OT_GAMES = 30
MAX_EXPECTED_POINTS = 100.0


@dataclass(frozen=True)
class TeamFeatures:
    expected_points: float

    def __post_init__(self) -> None:
        if not isfinite(self.expected_points) or not 0 < self.expected_points <= MAX_EXPECTED_POINTS:
            raise ValueError(f"expected_points must be finite and in (0, {MAX_EXPECTED_POINTS:g}]")


@dataclass(frozen=True, eq=False)
class SimParams:
    residual_a: np.ndarray
    residual_b: np.ndarray
    phi_a: float
    phi_b: float
    rho: float
    v: float
    v_shared: float
    ot_tie_frac: float
    ot_increments: np.ndarray
    ot_era: str
    ot_era_fallback: bool
    n_train: int


def ot_era(season: int) -> str:
    if season < 2012:
        return "sudden_death_15"
    return "modified_15" if season < 2017 else "modified_10"


def regulation_scores(a: np.ndarray, b: np.ndarray, overtime: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """An overtime game was tied after regulation, so both sides get the loser's final score."""
    low = np.minimum(a, b)
    is_ot = np.asarray(overtime) == 1
    return np.where(is_ot, low, a), np.where(is_ot, low, b)


def _overtime_rates(
    a: np.ndarray, b: np.ndarray, overtime: np.ndarray, seasons: np.ndarray, era: str
) -> tuple[float, np.ndarray, bool]:
    is_ot = overtime == 1
    if not is_ot.any():
        raise ValueError("no overtime games in the training rows")
    same_era = is_ot & np.array([ot_era(int(s)) == era for s in seasons])
    fallback = int(same_era.sum()) < MIN_ERA_OT_GAMES
    chosen = is_ot if fallback else same_era
    diff = np.abs(a[chosen] - b[chosen])
    if not (diff > 0).any():
        raise ValueError("no decided overtime games in the training rows")
    return float((diff == 0).mean()), np.sort(diff[diff > 0]).astype(np.int64), fallback


def _centre(pool: np.ndarray, offset: float) -> np.ndarray:
    """Subtract a real offset from a sorted integer pool: floor(offset) from every row and 1 more from k evenly
    spaced rows, k = round(frac * n), so the mean moves by `offset` to within 1/(2n) and the shape is kept."""
    n, whole = len(pool), np.floor(offset)
    k = int(round((offset - whole) * n))
    extra = np.zeros(n, dtype=np.int64)
    extra[(np.arange(k) * n) // max(k, 1)] = 1
    return pool - int(whole) - extra


def learn_params(
    mu_a: np.ndarray, mu_b: np.ndarray, score_a: np.ndarray, score_b: np.ndarray,
    overtime: np.ndarray, seasons: np.ndarray, target_season: int,
) -> SimParams:
    n = len(mu_a)
    if n < MIN_TRAIN_GAMES:
        raise ValueError(f"need at least {MIN_TRAIN_GAMES} training games, got {n}")
    mu_a, mu_b = np.asarray(mu_a, dtype=float), np.asarray(mu_b, dtype=float)
    sa, sb = np.asarray(score_a), np.asarray(score_b)
    overtime, seasons = np.asarray(overtime), np.asarray(seasons)
    tie_frac, increments, fallback = _overtime_rates(sa, sb, overtime, seasons, ot_era(target_season))

    reg_a, reg_b = regulation_scores(sa, sb, overtime)
    pool_a = reg_a - np.rint(mu_a).astype(np.int64)
    pool_b = reg_b - np.rint(mu_b).astype(np.int64)
    # The target season's mu is fit on these same seasons, so the older models' mean error (score - mu) is already
    # in mu; left in the pool it would count twice (step-18k.md "Simulator double-count fix"). Each side's pool is
    # centred on half the mean points overtime added over regulation (the same for both sides, so which side won
    # overtime in the past does not tilt the margin); the overtime step adds those points back.
    half_ot = float(np.mean(reg_a - sa) + np.mean(reg_b - sb)) / 2
    order = np.lexsort((pool_b, pool_a))
    pool_a = _centre(pool_a[order], float(np.mean(pool_a)) - half_ot)
    pool_b = _centre(pool_b[order], float(np.mean(pool_b)) - half_ot)
    order = np.lexsort((pool_b, pool_a))
    r_a, r_b = reg_a - mu_a, reg_b - mu_b
    phi_a = float(np.mean(r_a**2) / np.mean(mu_a))
    phi_b = float(np.mean(r_b**2) / np.mean(mu_b))
    rho = float(np.corrcoef(r_a / np.sqrt(phi_a * mu_a), r_b / np.sqrt(phi_b * mu_b))[0, 1])
    v_a = np.mean(r_a**2 - mu_a) / np.mean(mu_a**2)
    v_b = np.mean(r_b**2 - mu_b) / np.mean(mu_b**2)
    v = float(max((v_a + v_b) / 2, 1e-6))
    v_shared = float(np.clip(np.mean(r_a * r_b) / np.mean(mu_a * mu_b), 0.0, v))
    return SimParams(
        residual_a=pool_a[order], residual_b=pool_b[order], phi_a=phi_a, phi_b=phi_b, rho=rho, v=v,
        v_shared=v_shared, ot_tie_frac=tie_frac, ot_increments=increments, ot_era=ot_era(target_season),
        ot_era_fallback=fallback, n_train=n,
    )
