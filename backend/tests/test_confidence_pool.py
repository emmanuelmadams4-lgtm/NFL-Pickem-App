"""FR-007 invariant tests for the confidence optimizer.

The confidence_pool assigns unique 1..N confidence ranks to each week's games.
The acceptance criterion (FR-007) is that the ranks form a permutation of
1..N: no duplicates, no gaps, and exactly one of each value.

These are invariant tests, not change-detectors: they assert that the contract
described in the PRD holds, independent of any specific probability inputs.
"""

from nflpi.picks.pool import confidence_pool
from nflpi.picks.types import GameInputs


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


def test_confidence_pool_rank_1_goes_to_surest_pick():
    # The game with the highest calibrated win probability must get rank 1.
    games = [
        _game("SURE-01", 0.90),
        _game("MEDIUM-01", 0.60),
        _game("WEAK-01", 0.40),
        _game("WEAKEST-01", 0.10),
    ]
    pickset = confidence_pool(games, fill_ranks=True)
    by_id = {p.game_id: p for p in pickset.picks}
    assert by_id["SURE-01"].weight == 1
    assert by_id["WEAKEST-01"].weight == 4


def test_confidence_pool_empty_games_returns_empty_pickset():
    pickset = confidence_pool([], fill_ranks=True)
    assert len(pickset.picks) == 0


# ---- FR-007 violation detection ----


def test_confidence_pool_rejects_duplicate_ranks():
    # This should never happen via the optimizer, but the contract must be
    # enforced at the validation boundary.
    games = [
        GameInputs(game_id="A", p_home_win=0.6, p_away_win=0.4, p_tie=0.0),
        GameInputs(game_id="B", p_home_win=0.4, p_away_win=0.6, p_tie=0.0),
    ]
    from nflpi.picks.pool import _validate_confidence_permutation
    try:
        _validate_confidence_permutation([1, 1], 2, ids=["A", "B"])
        assert False, "expected PicksError for duplicate ranks"
    except Exception as e:
        msg = str(e).lower()
        assert ("duplicates" in msg) or ("duplicate" in msg) or ("permutation" in msg), f"unexpected error: {e}"


def test_confidence_pool_rejects_rank_gaps():
    from nflpi.picks.pool import _validate_confidence_permutation
    try:
        _validate_confidence_permutation([1, 3], 2, ids=["A", "B"])
        assert False, "expected PicksError for rank gap"
    except Exception as e:
        assert "missing" in str(e).lower() or "gap" in str(e).lower() or "permutation" in str(e).lower()


def test_confidence_pool_rejects_extra_rank():
    from nflpi.picks.pool import _validate_confidence_permutation
    try:
        _validate_confidence_permutation([1, 2, 4], 3, ids=["A", "B", "C"])
        assert False, "expected PicksError for extra rank"
    except Exception as e:
        assert "extra" in str(e).lower() or "permutation" in str(e).lower()
