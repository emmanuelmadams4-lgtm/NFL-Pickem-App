"""Scoring rules, calibration and bootstrap intervals."""

import numpy as np

EPS = 1e-6


def accuracy(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p > 0.5) == (y == 1)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


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


def bootstrap_ci(values: np.ndarray, reps: int = 2000, seed: int = 7) -> tuple[float, float]:
    """95% interval for the mean of per-game values (e.g. 1/0 correct)."""
    if len(values) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(reps, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


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
