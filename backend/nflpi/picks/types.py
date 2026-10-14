"""Value types for the pick rules. Frozen and validated at construction."""

import math
from dataclasses import dataclass

SUM_TOLERANCE = 1e-9
RUBRIC_LEVELS = 5


class PicksError(ValueError):
    """Invalid input to a pick rule."""


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PicksError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def _prob(value: object, name: str) -> float:
    p = _finite(value, name)
    if not 0 <= p <= 1:
        raise PicksError(f"{name} must be in [0, 1], got {value!r}")
    return p


def _sums_to_one(parts: tuple[float, ...], what: str) -> None:
    if not math.isclose(sum(parts), 1.0, abs_tol=SUM_TOLERANCE):
        raise PicksError(f"{what} must sum to 1")


def _set(game_id: str, line: float | None, line_name: str, names: tuple[str, ...], values: tuple) -> None:
    """A chance set is all three values or none, needs its line, and sums to one."""
    given = [v is not None for v in values]
    if not any(given):
        return
    if not all(given):
        raise PicksError(f"{game_id}: {', '.join(names)} must be given together")
    if line is None:
        raise PicksError(f"{game_id}: {names[0]} needs {line_name}")
    _sums_to_one(tuple(_prob(v, n) for v, n in zip(values, names, strict=True)), ", ".join(names))


@dataclass(frozen=True)
class GameInputs:
    game_id: str
    # ponytail: NaN defaults (rejected in validation) so an empty id is reported before missing chances
    p_home_win: float = math.nan
    p_away_win: float = math.nan
    p_tie: float = 0.0
    home_spread: float | None = None
    total: float | None = None
    p_home_cover: float | None = None
    p_away_cover: float | None = None
    p_spread_push: float | None = None
    p_over: float | None = None
    p_under: float | None = None
    p_total_push: float | None = None
    expected_margin: float | None = None
    expected_total: float | None = None
    qb_missing: bool = False
    stale_inputs: bool = False
    market_home_win: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.game_id, str) or not self.game_id:
            raise PicksError("game_id must be a non-empty string")
        _sums_to_one(
            (_prob(self.p_home_win, "p_home_win"), _prob(self.p_away_win, "p_away_win"), _prob(self.p_tie, "p_tie")),
            "p_home_win, p_away_win, p_tie",
        )
        for name in ("home_spread", "total", "expected_margin", "expected_total"):
            if getattr(self, name) is not None:
                _finite(getattr(self, name), name)
        if self.market_home_win is not None:
            _prob(self.market_home_win, "market_home_win")
        _set(self.game_id, self.home_spread, "home_spread", ("p_home_cover", "p_away_cover", "p_spread_push"),
             (self.p_home_cover, self.p_away_cover, self.p_spread_push))  # fmt: skip
        _set(self.game_id, self.total, "total", ("p_over", "p_under", "p_total_push"),
             (self.p_over, self.p_under, self.p_total_push))  # fmt: skip


@dataclass(frozen=True)
class Pick:
    """probability and expected_points are None when the basis is a fallback with no stated chance."""

    game_id: str
    mode: str
    selection: str
    probability: float | None
    expected_points: float | None
    basis: str
    line: float | None
    warnings: tuple[str, ...]
    weight: int | None = None


@dataclass(frozen=True)
class PickSet:
    mode: str
    mode_assumed: bool
    label: str
    picks: tuple[Pick, ...]
    warnings: tuple[str, ...]
    expected_points: float | None


@dataclass(frozen=True)
class Advice:
    status: str
    stars: int | None
    expected_value: float
    reasons: tuple[str, ...]
    provisional: bool


@dataclass(frozen=True)
class Rubric:
    """Five increasing expected-value thresholds. Only a validated rubric may produce stars."""

    ev_thresholds: tuple[float, ...]
    validated: bool = False
    provisional: bool = True

    def __post_init__(self) -> None:
        t = tuple(self.ev_thresholds)
        if len(t) != RUBRIC_LEVELS:
            raise PicksError(f"need exactly {RUBRIC_LEVELS} thresholds")
        if any(_finite(x, "threshold") <= 0 for x in t) or any(a >= b for a, b in zip(t, t[1:], strict=False)):
            raise PicksError("thresholds must be positive and strictly increasing")
