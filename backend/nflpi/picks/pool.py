"""Confidence pool: the largest unique weight goes to the largest straight-up share.

FR-007: for N games the default weights are exactly 1..N, one each (no duplicates, no gaps).
Ranks passed in by the caller (user_ranks) must be that same permutation.
"""

from collections.abc import Sequence

from nflpi.picks.rules import check_games, choose_su, one_of, pick_set
from nflpi.picks.types import GameInputs, Pick, PicksError, PickSet


def _weights(weights: Sequence[int] | None, n: int) -> list[int]:
    if weights is None:
        return list(range(n, 0, -1))
    ok = all(isinstance(w, int) and not isinstance(w, bool) and w > 0 for w in weights)
    if len(weights) != n or not ok or len(set(weights)) != n:
        raise PicksError(f"weights must be {n} unique positive integers")
    return sorted(weights, reverse=True)


def _validate_confidence_permutation(ranks: Sequence[int], n: int, *, ids: Sequence[str]) -> None:
    """FR-007: the ranks must be a permutation of 1..n. The error names what is missing, extra or repeated."""
    if len(ranks) != n:
        raise PicksError(f"FR-007 violation: expected {n} confidence ranks for {n} games, got {len(ranks)}")
    expected, got = set(range(1, n + 1)), set(ranks)
    if got != expected:
        duplicates = sorted({r for r in ranks if list(ranks).count(r) > 1})
        raise PicksError(
            f"FR-007 violation: confidence ranks must be a permutation of 1..{n}. Got {sorted(ranks)}. "
            f"Missing: {sorted(expected - got)}, extra: {sorted(got - expected)}, duplicates: {duplicates}"
        )


def confidence_pool(
    games: Sequence[GameInputs],
    *,
    weights: Sequence[int] | None = None,
    tie_rule: str = "game_id",
    win_tie_rule: str = "half",
    fill_ranks: bool = True,
    user_ranks: Sequence[int] | None = None,
) -> PickSet:
    """Give each game a unique weight; the surest pick (largest straight-up share) gets the largest.

    weights: your own unique positive integers instead of N..1.
    tie_rule: equal shares go by "game_id" or "input_order"; the first gets the larger weight.
    user_ranks: explicit weights in input order; must be a permutation of 1..N (FR-007).
    fill_ranks: False leaves a game unweighted (no expected points) unless user_ranks or weights are given.
    """
    check_games(games)
    one_of(tie_rule, ("game_id", "input_order"), "tie_rule")
    if weights is not None and user_ranks is not None:
        raise PicksError("give weights or user_ranks, not both")
    chosen = [choose_su(g, win_tie_rule, "first") for g in games]
    ids = [g.game_id for g in games]
    n = len(games)
    if user_ranks is not None:
        _validate_confidence_permutation(user_ranks, n, ids=ids)
        weight: list[int | None] = list(user_ranks)
    elif fill_ranks or weights is not None:
        # Stable sort: equal shares keep input order, or go by game id; the first in order gets the larger weight.
        order = sorted(range(n), key=lambda i: (-chosen[i][1], ids[i] if tie_rule == "game_id" else ""))
        by_order = dict(zip(order, _weights(weights, n), strict=True))
        weight = [by_order[i] for i in range(n)]
        if weights is None:
            _validate_confidence_permutation(weight, n, ids=ids)
    else:
        weight = [None] * n
    picks = tuple(
        Pick(g.game_id, "confidence_pool", side, share, None if w is None else w * share, "model", None, warns, w)
        for g, (side, share, warns), w in zip(games, chosen, weight, strict=True)
    )
    return pick_set("confidence_pool", picks)
