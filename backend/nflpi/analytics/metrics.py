"""Scoring rules, calibration and bootstrap intervals."""

import numpy as np

EPS = 1e-6
UPSET_GAP = 0.12
UNCERTAINTY_GAP = 0.08
EARLY_WEEK_END = 4
COIN_FLIP_BELOW = 0.55
EASY_PICK_FROM = 0.67
# Measured on the 2012-2025 walk-forward backtest, blend model (docs/gauntlet/logs/step-4-evidence/s4-label-cuts.log).
LABEL_HIT_RATE = {"coin_flip": 0.524, "tough_matchup": 0.596, "easy_pick": 0.770}


def pick_label(prob: float) -> str:
    if prob < COIN_FLIP_BELOW:
        return "coin_flip"
    return "easy_pick" if prob >= EASY_PICK_FROM else "tough_matchup"


def uncertainty_grade(
    disagreement: float | None, qb_change: bool, early_season: bool, stale: bool = False
) -> tuple[str, list[str]]:
    """Grade pre-game input reliability; return only reasons that raise the grade."""
    if disagreement is None or np.isnan(disagreement):
        return "high", ["missing_market"]
    score = 0
    reasons = []
    for key, points, applies in (
        ("qb_change", 1, qb_change),
        ("disagreement", 1, disagreement >= UNCERTAINTY_GAP),
        ("early_season", 2, early_season),
        ("stale", 1, stale),
    ):
        if applies and score < 2:
            score = min(2, score + points)
            reasons.append(key)
    return ("low", "moderate", "high")[score], reasons


def upset_watch(stats_home_prob: float, market_home_prob: float | None) -> bool:
    """A stats pick of the market underdog or a 12-point gap qualifies."""
    if market_home_prob is None or np.isnan(market_home_prob):
        return False
    picks_underdog = market_home_prob != 0.5 and (stats_home_prob >= 0.5) != (market_home_prob >= 0.5)
    return bool(picks_underdog or abs(stats_home_prob - market_home_prob) >= UPSET_GAP)


def accuracy(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p > 0.5) == (y == 1)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    return float(game_log_loss(p, y).mean())


def game_log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Return one clipped log loss per game."""
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calibration(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict]:
    """Bucket by the probability of the picked side (50-60%, 60-70%, ...)."""
    pick_p = np.where(p >= 0.5, p, 1 - p)
    pick_won = np.where(p >= 0.5, y, 1 - y)
    edges = np.linspace(0.5, 1.0, bins // 2 + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (pick_p >= lo) & ((pick_p < hi) if hi < 1 else (pick_p <= hi))
        n = int(mask.sum())
        out.append(
            {
                "bucket": f"{int(lo * 100)}-{int(hi * 100)}%",
                "n": n,
                "predicted": float(pick_p[mask].mean()) if n else None,
                "observed": float(pick_won[mask].mean()) if n else None,
            }
        )
    return out


def bootstrap_ci(
    values: np.ndarray, reps: int = 2000, seed: int = 7, clusters: np.ndarray | None = None
) -> tuple[float, float]:
    """95% interval for the mean of per-game values (e.g. 1/0 correct)."""
    if clusters is not None and len(clusters) != len(values):
        raise ValueError("clusters must match values length")
    if len(values) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    if clusters is None:
        idx = rng.integers(0, len(values), size=(reps, len(values)))
        means = values[idx].mean(axis=1)
    else:
        _, inverse = np.unique(clusters, return_inverse=True)
        n_clusters = int(inverse.max()) + 1
        sums = np.bincount(inverse, weights=values)
        counts = np.bincount(inverse)
        idx = rng.integers(0, n_clusters, size=(reps, n_clusters))
        means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_gain(p_new: np.ndarray, p_old: np.ndarray, y: np.ndarray, clusters: np.ndarray | None = None) -> dict:
    """Compare two predictions on the same games."""
    if len(p_new) != len(p_old) or len(p_new) != len(y) or len(y) == 0:
        raise ValueError("prediction arrays must have the same nonzero length")
    if not all(np.isfinite(values).all() for values in (p_new, p_old, y)):
        raise ValueError("prediction arrays must contain only finite values")
    if clusters is not None and len(clusters) != len(y):
        raise ValueError("clusters must match predictions length")
    loss_diff = game_log_loss(p_old, y) - game_log_loss(p_new, y)
    correct_diff = ((p_new > 0.5) == (y == 1)).astype(float) - ((p_old > 0.5) == (y == 1)).astype(float)
    loss_ci = list(bootstrap_ci(loss_diff))
    accuracy_diff = float(correct_diff.mean())
    result = {
        "n": int(len(y)),
        "log_loss_gain": float(loss_diff.mean()),
        "log_loss_gain_ci": loss_ci,
        "accuracy_diff": accuracy_diff,
        "accuracy_diff_ci": list(bootstrap_ci(correct_diff)),
        "ships": bool(loss_ci[0] > 0 and accuracy_diff >= 0),
    }
    if clusters is not None:
        cluster_ci = list(bootstrap_ci(loss_diff, clusters=clusters))
        result.update({
            "log_loss_gain_ci_cluster": cluster_ci,
            "accuracy_diff_ci_cluster": list(bootstrap_ci(correct_diff, clusters=clusters)),
            "ships_cluster": bool(cluster_ci[0] > 0 and accuracy_diff >= 0),
        })
    return result


def wilson_ci(correct: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return (None, None)
    p = correct / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return float(center - half), float(center + half)


def summarize(p: np.ndarray, y: np.ndarray) -> dict:
    correct = ((p > 0.5) == (y == 1)).astype(float)
    lo, hi = bootstrap_ci(correct)
    return {
        "n": int(len(y)),
        "accuracy": accuracy(p, y),
        "accuracy_ci": [lo, hi],
        "brier": brier(p, y),
        "log_loss": log_loss(p, y),
    }
