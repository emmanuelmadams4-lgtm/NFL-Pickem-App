"""Overtime: regulation ties either stay tied (regular season only) or one side gains a learned increment."""

import numpy as np

from nflpi.sim.params import SimParams

# ponytail: without learned params (poisson baseline) overtime is a fixed 3-point field goal and never ties.
FALLBACK_INCREMENTS = np.array([3], dtype=np.int64)


def resolve_overtime(
    a: np.ndarray, b: np.ndarray, rng: np.random.Generator, params: SimParams | None, playoff: bool
) -> tuple[np.ndarray, np.ndarray]:
    tie_frac = 0.0 if params is None or playoff else params.ot_tie_frac
    increments = FALLBACK_INCREMENTS if params is None else params.ot_increments
    tied = a == b
    n = len(a)
    stays_tied = rng.random(n) < tie_frac
    gain = rng.choice(increments, n)
    a_gets = rng.random(n) < 0.5
    move = tied & ~stays_tied
    return (np.where(move & a_gets, a + gain, a).astype(np.int64),
            np.where(move & ~a_gets, b + gain, b).astype(np.int64))
