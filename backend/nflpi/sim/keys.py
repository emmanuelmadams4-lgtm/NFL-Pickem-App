"""Learn and apply final-margin key-number weights to simulated scores."""

import logging

import numpy as np

log = logging.getLogger(__name__)
KEY_MAX = 60
KEY_ALPHA = 1.0  # chosen on 2012-2021 only by the keys-tune rule: step-18m-evidence/keys-tune.json
# ponytail: cap learning draws so a large training window stays fast.
KEY_TOTAL_DRAWS = 2_000_000
TILT_STEPS = 50


def key_weight(
    a: np.ndarray, b: np.ndarray, rng: np.random.Generator, ratio: tuple[float, ...], alpha: float
) -> tuple[np.ndarray, np.ndarray]:
    if alpha == 0 or len(ratio) == 0:
        return a, b
    margin = (a - b).astype(float)
    total = (a + b).astype(float)
    target = np.array([margin.mean(), total.mean()])
    log_base = alpha * np.log(np.asarray(ratio)[np.minimum(np.abs(margin).astype(int), KEY_MAX)])
    tilt = np.zeros(2)
    delta = np.full(2, np.nan)
    for _ in range(TILT_STEPS):
        z = log_base + tilt[0] * margin + tilt[1] * total
        weights = np.exp(z - z.max())
        weights /= weights.sum()
        mean = np.array([weights @ margin, weights @ total])
        delta = mean - target
        if np.max(np.abs(delta)) < 1e-9:
            break
        dm, dt = margin - mean[0], total - mean[1]
        covariance = np.array([
            [weights @ (dm * dm), weights @ (dm * dt)],
            [weights @ (dm * dt), weights @ (dt * dt)],
        ])
        tilt -= np.linalg.solve(covariance + 1e-9 * np.eye(2), delta)
    else:
        log.warning("key weighting did not converge after %d steps (mean error %s); draws left unweighted",
                    TILT_STEPS, delta)
        return a, b
    idx = rng.choice(len(a), len(a), p=weights)
    return a[idx], b[idx]


def learn_key_ratio(
    mu_a: np.ndarray, mu_b: np.ndarray, score_a: np.ndarray, score_b: np.ndarray,
    params: object, target_season: int,
) -> tuple[float, ...]:
    """Compare real final-margin counts with equal-draw paired-residual simulations per training row."""
    from nflpi.sim.distributions import sample_regulation
    from nflpi.sim.overtime import resolve_overtime

    order = np.lexsort((score_b, score_a, mu_b, mu_a))
    mu_a, mu_b = np.asarray(mu_a)[order], np.asarray(mu_b)[order]
    score_a, score_b = np.asarray(score_a)[order], np.asarray(score_b)[order]
    if not (np.isfinite(score_a).all() and np.isfinite(score_b).all()):
        raise ValueError("final scores must be finite")
    real_margins = np.rint(np.abs(score_a - score_b)).astype(np.int64)
    n_rows = len(mu_a)
    draws_per_row = max(1, KEY_TOTAL_DRAWS // n_rows)
    n_draws = n_rows * draws_per_row
    rng = np.random.default_rng(target_season)
    a_mu, b_mu = np.repeat(mu_a, draws_per_row), np.repeat(mu_b, draws_per_row)
    reg_a, reg_b = sample_regulation("paired_residual", a_mu, b_mu, n_draws, rng, params)
    final_a, final_b = resolve_overtime(reg_a, reg_b, rng, params, False)
    sim = np.bincount(np.minimum(np.abs(final_a - final_b), KEY_MAX), minlength=KEY_MAX + 1) / draws_per_row
    real = np.bincount(np.minimum(real_margins, KEY_MAX), minlength=KEY_MAX + 1)
    return tuple(float(x) for x in (real + 0.5) / (sim + 0.5))
