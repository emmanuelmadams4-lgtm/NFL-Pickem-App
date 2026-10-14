"""Confidence pool: the largest unique weight goes to the largest straight-up share."""

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


def confidence_pool(
    games: Sequence[GameInputs],
    *,
    weights: Sequence[int] | None = None,
    tie_rule: str = "game_id",
    win_tie_rule: str = "half",
) -> PickSet:
    check_games(games)
    one_of(tie_rule, ("game_id", "input_order"), "tie_rule")
    chosen = [choose_su(g, win_tie_rule, "first") for g in games]
    ids = [g.game_id for g in games]
    # Stable sort: equal shares keep input order, or go by game id; the first in order gets the larger weight.
    order = sorted(range(len(games)), key=lambda i: (-chosen[i][1], ids[i] if tie_rule == "game_id" else ""))
    weight = dict(zip(order, _weights(weights, len(games)), strict=True))
    picks = tuple(
        Pick(g.game_id, "confidence_pool", side, share, weight[i] * share, "model", None, warns, weight[i])
        for i, (g, (side, share, warns)) in enumerate(zip(games, chosen, strict=True))
    )
    return pick_set("confidence_pool", picks)
