"""Regulation-score samplers. Every one is vectorised and returns non-negative int64 arrays."""

import numpy as np

from nflpi.sim.params import SimParams

DISTRIBUTIONS = ("poisson", "paired_residual", "bivariate_normal", "shared_gamma_poisson")
DEFAULT_DISTRIBUTION = "paired_residual"  # chosen on 2012-2021 only: step-18c-evidence/tune-result.json


def _paired_residual(mu_a: float, mu_b: float, n: int, rng: np.random.Generator, p: SimParams):
    idx = rng.integers(0, len(p.residual_a), n)
    out = []
    for mu, pool in ((mu_a, p.residual_a), (mu_b, p.residual_b)):
        base = np.floor(mu) + (rng.random(n) < mu - np.floor(mu))  # stochastic rounding keeps the mean at mu
        out.append(base.astype(np.int64) + pool[idx])
    return out


def _bivariate_normal(mu_a: float, mu_b: float, n: int, rng: np.random.Generator, p: SimParams):
    z1 = rng.standard_normal(n)
    z2 = p.rho * z1 + np.sqrt(1 - p.rho**2) * rng.standard_normal(n)
    return [np.rint(mu + np.sqrt(phi * mu) * z).astype(np.int64)
            for mu, phi, z in ((mu_a, p.phi_a, z1), (mu_b, p.phi_b, z2))]


def _shared_gamma_poisson(mu_a: float, mu_b: float, n: int, rng: np.random.Generator, p: SimParams):
    k_s = p.v_shared / p.v**2
    k_e = 1 / p.v - k_s
    shared = rng.gamma(k_s, size=n) if k_s > 0 else 0.0
    out = []
    for mu in (mu_a, mu_b):
        own = rng.gamma(k_e, size=n) if k_e > 0 else 0.0
        out.append(rng.poisson(mu * (shared + own) / (k_s + k_e)))
    return out


_SAMPLERS = {
    "paired_residual": _paired_residual,
    "bivariate_normal": _bivariate_normal,
    "shared_gamma_poisson": _shared_gamma_poisson,
}


def sample_regulation(
    distribution: str, mu_a: float, mu_b: float, n: int, rng: np.random.Generator, params: SimParams | None
) -> tuple[np.ndarray, np.ndarray]:
    if distribution not in DISTRIBUTIONS:
        raise ValueError(f"unknown distribution {distribution!r}; choose from {DISTRIBUTIONS}")
    if distribution == "poisson":
        a, b = rng.poisson(mu_a, n), rng.poisson(mu_b, n)
    elif params is None:
        raise ValueError(f"distribution {distribution!r} needs learned params")
    else:
        a, b = _SAMPLERS[distribution](mu_a, mu_b, n, rng, params)
    return np.maximum(a, 0).astype(np.int64), np.maximum(b, 0).astype(np.int64)
