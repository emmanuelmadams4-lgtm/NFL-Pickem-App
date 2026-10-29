"""FR-007 invariant tests for the confidence optimizer.

The confidence_pool assigns unique 1..N confidence weights to each week's games.
The acceptance criterion (FR-007) is that the weights form a permutation of
1..N: no duplicates, no gaps, and exactly one of each value.

These are invariant tests, not change-detectors: they assert that the contract
described in the PRD holds, independent of any specific probability inputs.
"""

import pytest

from nflpi.picks.pool import _validate_confidence_permutation, confidence_pool
from nflpi.picks.types import GameInputs, PicksError


def _game(pid: str, prob: float) -> GameInputs:
    return GameInputs(game_id=pid, p_home_win=prob, p_away_win=1 - prob, p_tie=0.0)


def _ranks(pickset) -> list[int]:
    return sorted(int(p.weight) for p in pickset.picks)


# ---- FR-007 invariant: ranks are a permutation of 1..N ----


def test_confidence_pool_ranks_are_permutation_of_1_to_n():
    # Week with 3 eligible games.
    games = [_game("BUF-01", 0.62), _game("LAR-01", 0.48), _game("PIT-01", 0.55)]
    pickset = confidence_pool(games, fill_ranks=True, win_tie_rule="half")
    ranks = _ranks(pickset)
    assert len(ranks) == 3
    assert ranks == [1, 2, 3], f"expected [1,2,3], got {ranks}"


def test_confidence_pool_surest_pick_gets_the_largest_weight_whatever_the_input_order():
    # The pool convention (as on the Yahoo sheet): the largest number goes to the surest pick, 1 to the least sure.
    games = [_game("WEAK-01", 0.60), _game("WEAKEST-01", 0.51), _game("SURE-01", 0.90), _game("MEDIUM-01", 0.70)]
    pickset = confidence_pool(games, fill_ranks=True)
    by_id = {p.game_id: p.weight for p in pickset.picks}
    assert by_id == {"SURE-01": 4, "MEDIUM-01": 3, "WEAK-01": 2, "WEAKEST-01": 1}


def test_confidence_pool_empty_games_returns_empty_pickset():
    pickset = confidence_pool([], fill_ranks=True)
    assert len(pickset.picks) == 0


def test_confidence_pool_user_ranks_are_used_in_input_order_and_must_be_a_permutation():
    games = [_game("A", 0.9), _game("B", 0.6)]
    assert [p.weight for p in confidence_pool(games, user_ranks=[1, 2]).picks] == [1, 2]
    with pytest.raises(PicksError, match="permutation"):
        confidence_pool(games, user_ranks=[2, 2])
    with pytest.raises(PicksError, match="not both"):
        confidence_pool(games, user_ranks=[1, 2], weights=[5, 9])


def test_confidence_pool_fill_ranks_false_leaves_games_unweighted():
    pickset = confidence_pool([_game("A", 0.9), _game("B", 0.6)], fill_ranks=False)
    assert [p.weight for p in pickset.picks] == [None, None]
    assert pickset.expected_points is None


# ---- FR-007 violation detection ----


def test_confidence_pool_rejects_duplicate_ranks():
    # This should never happen via the optimizer, but the contract must be
    # enforced at the validation boundary.
    with pytest.raises(PicksError, match=r"permutation.*duplicates: \[1\]"):
        _validate_confidence_permutation([1, 1], 2, ids=["A", "B"])


def test_confidence_pool_rejects_rank_gaps():
    with pytest.raises(PicksError, match=r"Missing: \[2\]"):
        _validate_confidence_permutation([1, 3], 2, ids=["A", "B"])


def test_confidence_pool_rejects_extra_rank():
    with pytest.raises(PicksError, match=r"extra: \[4\]"):
        _validate_confidence_permutation([1, 2, 4], 3, ids=["A", "B", "C"])
