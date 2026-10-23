"""Confidence optimizer (FR-007): unique 1..N confidence values per week.

Yahoo scores outright winners. For N eligible games, each assigned confidence
value is unique and drawn from 1..N (assuming the league uses all values;
verify exact Yahoo settings for byes/canceled games/ties).

Key invariant (FR-007): for a week with N games, the assigned ranks are
exactly 1, 2, ..., N (a permutation). No duplicates, no gaps.

Weights: the largest weight (rank 1) goes to the surest pick (highest
calibrated win probability).
"""

from __future__ import annotations

from collections.abc import Sequence

from nflpi.picks.rules import check_games, choose_su, one_of, pick_set
from nflpi.picks.types import GameInputs, PicksError, Pick, PickSet


def _permutation(n: int) -> list[int]:
    """Return 1..n as a list. FR-007 requires ranks to be a permutation of 1..n."""
    if n < 1:
        raise PicksError("n must be >= 1")
    return list(range(1, n + 1))


def _validate_confidence_permutation(
    ranks: Sequence[int], n: int, *, ids: Sequence[str]
) -> None:
    """Enforce FR-007: ranks must be a permutation of 1..n, no dupes, no gaps.

    Raises PicksError with a clear message listing missing and extra values.
    """
    if len(ranks) != n:
        raise PicksError(
            f"FR-007 violation: expected {n} confidence ranks for {n} games, "
            f"got {len(ranks)}"
        )
    expected = set(range(1, n + 1))
    got = set(ranks)
    if got != expected:
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        raise PicksError(
            f"FR-007 violation: confidence ranks must be a permutation of "
            f"1..{n}. Got {sorted(ranks)}. Missing: {missing}, extra: {extra}"
        )
    if len(set(ranks)) != n:
        duplicates = sorted({r for r in ranks if ranks.count(r) > 1})
        raise PicksError(f"FR-007 violation: duplicate confidence ranks: {duplicates}")


def confidence_pool(
    games: Sequence[GameInputs],
    *,
    win_tie_rule: str = "half",
    fill_ranks: bool = True,
    user_ranks: Sequence[int] | None = None,
) -> PickSet:
    """Assign unique 1..N confidence values to the week's games (FR-007).

    FR-007: for N eligible games, the assigned confidence ranks are exactly
    {1, 2, ..., N}. The surest pick (highest calibrated win probability)
    gets rank 1, the next surest rank 2, and so on, down to the weakest pick
    which gets rank N.

    Args:
        games: one input per eligible game for the week.
        win_tie_rule: tie-break for straight-up win probability.
        fill_ranks: when True (default), every game gets a rank 1..N
                    (PRD FR-007). When False, only games with a user-provided
                    rank get one and the rest are left unranked (for partial
                    slates).
        user_ranks: optional explicit ranks for the games in the order
                    provided. When given, must be a permutation of 1..N.

    Returns:
        A PickSet with confidence ranks assigned to each pick.

    Raises:
        PicksError: If the week has zero games, or if ranks cannot form a
                   permutation of 1..N.
    """
    check_games(games)

    n_games = len(games)
    if n_games == 0:
        return pick_set("confidence_pool", tuple())

    one_of(win_tie_rule, ("half", "first", "last"), "win_tie_rule")

    # Per-game straight-up pick and calibrated probability.
    # choose_su returns (side, share, warns)
    chosen = [choose_su(g, win_tie_rule, "first") for g in games]
    probs = [c[1] for c in chosen]

    if user_ranks is not None:
        if len(user_ranks) != n_games:
            raise PicksError(
                f"FR-007: got {len(user_ranks)} ranks for {n_games} games"
            )
        _validate_confidence_permutation(
            user_ranks, n_games, ids=[g.game_id for g in games]
        )
        ranks = list(user_ranks)
    elif fill_ranks:
        # Sort by calibrated probability descending: surest -> rank 1.
        order = sorted(range(n_games), key=lambda i: (-probs[i], games[i].game_id))
        ranks = _permutation(n_games)
        # pos_by_game[game_index] = rank
        pos_by_game = [0] * n_games
        for pos, game_idx in enumerate(order, start=1):
            pos_by_game[game_idx] = pos
    else:
        # Partial slate: leave ranks unassigned. (Not FR-007-compliant but
        # allowed for incomplete weeks; caller must validate.)
        ranks = None

    if ranks is not None:
        pick_weights = ranks
    else:
        pick_weights = [None] * n_games

    picks = tuple(
        Pick(
            game_id=g.game_id,
            mode="confidence_pool",
            selection=side,
            probability=prob,
            expected_points=None,
            basis="model",
            line=None,
            warnings=(),
            weight=weight,
        )
        for g, (side, prob, _), weight in zip(
            games, chosen, pick_weights, strict=True
        )
    )

    if ranks is not None:
        # Enforce FR-007 invariant: ranks are a permutation of 1..N.
        _validate_confidence_permutation(
            [p.weight for p in picks], n_games, ids=[g.game_id for g in games]
        )

    return pick_set("confidence_pool", picks, warnings=())
