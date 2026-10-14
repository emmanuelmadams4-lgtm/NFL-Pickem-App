"""Pick rules: straight-up, against the spread, totals, grading. Pure functions over plain probabilities."""

from collections.abc import Sequence

from nflpi.betting.settle import settle_moneyline, settle_spread, settle_total
from nflpi.data.asof import home_spread_from_nflverse  # noqa: F401 - re-exported by nflpi.picks
from nflpi.picks.types import GameInputs, Pick, PicksError, PickSet

COIN_FLIP = "NOT_SHOWN_TO_BEAT_COIN_FLIP"
ASSUMED_LABEL = "Assumed: straight-up pick'em (pool rules unavailable)"
LABELS = {
    "straight_up": "Straight-up picks",
    "ats": "Picks against the pool spread",
    "totals": "Over/under picks",
    "confidence_pool": "Confidence pool",
}


def one_of(value: str, allowed: tuple[str, ...], name: str) -> str:
    if value not in allowed:
        raise PicksError(f"{name} must be one of {allowed}, got {value!r}")
    return value


def check_games(games: Sequence[GameInputs]) -> None:
    ids = [g.game_id for g in games]
    if len(set(ids)) != len(ids):
        raise PicksError("duplicate game ids")


def pick_set(
    mode: str, picks: tuple[Pick, ...], *, mode_assumed: bool = False, warnings: tuple[str, ...] = ()
) -> PickSet:
    points = [p.expected_points for p in picks]
    total = None if any(x is None for x in points) else float(sum(points))
    label = ASSUMED_LABEL if mode_assumed else LABELS[mode]
    return PickSet(mode, mode_assumed, label, picks, warnings, total)


def _flags(g: GameInputs) -> tuple[str, ...]:
    return (("QB_MISSING",) if g.qb_missing else ()) + (("STALE_INPUTS",) if g.stale_inputs else ())


def _first(tie_break: str) -> bool:
    return one_of(tie_break, ("first", "second"), "tie_break") == "first"


def choose_su(
    g: GameInputs, tie_rule: str, tie_break: str, close_band: float = 0.05, disagree_band: float = 0.15
) -> tuple[str, float, tuple[str, ...]]:
    """Straight-up side, its share and warnings."""
    extra = g.p_tie / 2 if one_of(tie_rule, ("half", "loss"), "tie_rule") == "half" else 0.0
    home, away = g.p_home_win + extra, g.p_away_win + extra
    warns: list[str] = []
    if home == away:
        side = "home" if _first(tie_break) else "away"
        warns.append("EXACT_TIE_BREAK")
    else:
        side = "home" if home > away else "away"
    share = home if side == "home" else away
    if share < 0.5 + close_band:
        warns.append("CLOSE_CALL")
    warns.extend(_flags(g))
    if g.market_home_win is not None and abs(g.p_home_win - g.market_home_win) >= disagree_band:
        warns.append("MODEL_DISAGREES_WITH_MARKET")
    return side, share, tuple(warns)


def pick_straight_up(
    games: Sequence[GameInputs],
    *,
    tie_rule: str = "half",
    tie_break: str = "first",
    close_band: float = 0.05,
    disagree_band: float = 0.15,
    mode_assumed: bool = False,
) -> PickSet:
    check_games(games)
    picks = []
    for g in games:
        side, share, warns = choose_su(g, tie_rule, tie_break, close_band, disagree_band)
        picks.append(Pick(g.game_id, "straight_up", side, share, share, "model", None, warns))
    return pick_set("straight_up", tuple(picks), mode_assumed=mode_assumed)


def _by_chance(first: float, second: float, push: float, push_rule: str, tie_break: str) -> tuple[bool, float, float]:
    """Whether the first side is picked, its expected points and its chance."""
    bonus = 0.5 * push if one_of(push_rule, ("no_points", "half"), "push_rule") == "half" else 0.0
    a, b = first + bonus, second + bonus
    pick_first = a > b or (a == b and _first(tie_break))
    return pick_first, (a if pick_first else b), (first if pick_first else second)


def _by_value(value: float, tie_break: str) -> bool:
    """Whether the first side is picked from a signed margin; zero goes to tie_break."""
    return value > 0 or (value == 0 and _first(tie_break))


def _line_pick(g, mode, sides, line, push_rule, tie_break, chances, value, fallback):
    """Shared ATS/totals path: model chances, then a margin-style fallback."""
    first, second = sides
    flags = _flags(g) + (COIN_FLIP,)
    if chances is not None:
        pick_first, points, chance = _by_chance(*chances, push_rule, tie_break)
        return Pick(g.game_id, mode, first if pick_first else second, chance, points, "model", line, flags)
    if value is not None and line is not None:
        side = first if _by_value(value, tie_break) else second
        return Pick(g.game_id, mode, side, None, None, "margin_fallback", line, flags + (fallback,))
    return None


def _all(*parts):
    return None if any(p is None for p in parts) else parts


def pick_ats(games: Sequence[GameInputs], *, push_rule: str = "no_points", tie_break: str = "first") -> PickSet:
    # ponytail: no close/disagree bands here; those warnings describe win chances, not cover chances.
    check_games(games)
    picks = []
    for g in games:
        chances = _all(g.p_home_cover, g.p_away_cover, g.p_spread_push)
        value = None if g.expected_margin is None or g.home_spread is None else g.expected_margin + g.home_spread
        pick = _line_pick(
            g, "ats", ("home", "away"), g.home_spread, push_rule, tie_break, chances, value, "NO_COVER_MODEL"
        )
        if pick is None:
            side, share, _ = choose_su(g, "half", tie_break)
            warns = _flags(g) + (COIN_FLIP, "NO_COVER_MODEL") + (("NO_SPREAD",) if g.home_spread is None else ())
            pick = Pick(g.game_id, "ats", side, None, None, "straight_up_fallback", g.home_spread, warns)
        picks.append(pick)
    return pick_set("ats", tuple(picks), warnings=(COIN_FLIP,) if picks else ())


def pick_totals(games: Sequence[GameInputs], *, push_rule: str = "no_points", tie_break: str = "first") -> PickSet:
    check_games(games)
    picks = []
    for g in games:
        chances = _all(g.p_over, g.p_under, g.p_total_push)
        value = None if g.expected_total is None or g.total is None else g.expected_total - g.total
        pick = _line_pick(
            g, "totals", ("over", "under"), g.total, push_rule, tie_break, chances, value, "NO_TOTAL_MODEL"
        )
        if pick is None:
            side = "over" if _first(tie_break) else "under"
            warns = _flags(g) + (COIN_FLIP, "NO_TOTAL_MODEL")
            pick = Pick(g.game_id, "totals", side, None, None, "default", g.total, warns)
        picks.append(pick)
    return pick_set("totals", tuple(picks), warnings=(COIN_FLIP,) if picks else ())


def make_picks(games: Sequence[GameInputs], mode: str | None = None, **options) -> PickSet:
    from nflpi.picks.pool import confidence_pool  # late import: pool builds on this module

    if mode is None:
        return pick_straight_up(games, mode_assumed=True, **options)
    modes = {
        "straight_up": pick_straight_up,
        "ats": pick_ats,
        "totals": pick_totals,
        "confidence_pool": confidence_pool,
    }
    if mode not in modes:
        raise PicksError(f"unknown mode {mode!r}; expected one of {tuple(modes)}")
    return modes[mode](games, **options)


def grade_pick(pick: Pick, home_score: int, away_score: int) -> str:
    """win, loss or push, settled by nflpi.betting.settle."""
    if pick.mode in ("straight_up", "confidence_pool"):
        return settle_moneyline(pick.selection, home_score, away_score)
    if pick.mode not in ("ats", "totals"):
        raise PicksError(f"cannot grade mode {pick.mode!r}")
    if pick.line is None:
        raise PicksError(f"a {pick.mode} pick without a line cannot be graded")
    settle = settle_spread if pick.mode == "ats" else settle_total
    return settle(pick.selection, pick.line, home_score, away_score)


def pick_points(result: str, push_rule: str = "no_points") -> float:
    one_of(result, ("win", "loss", "push"), "result")
    if result == "push" and one_of(push_rule, ("no_points", "half"), "push_rule") == "half":
        return 0.5
    return 1.0 if result == "win" else 0.0
