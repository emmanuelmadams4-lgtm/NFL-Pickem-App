"""Step 15f: grade the in-game win probabilities of finished games (clauses G1-G12 in docs/gauntlet/logs/step-15f.md).

Every forecast is a step function over the game window and is weighted by the seconds it held, so the density of
stored rows never decides the score. Missing numbers get no weight and are never filled.

The game window runs from the first 'in' row to the first 'post' row after it; rows after that are ignored for every
forecaster. A final game with no such 'post' row is 'in_progress' (last row 'in') or 'incomplete' (last row 'lost')."""

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi.analytics.metrics import game_log_loss
from nflpi.models import Game, LiveState, MarketQuote, Prediction

MIN_POINTS = 3
MIN_COVERAGE = 0.5
NAMES = ("pregame_model", "espn_live", "kalshi_live")


@dataclass(frozen=True)
class Point:
    at: datetime
    value: float | None


@dataclass(frozen=True)
class ForecastGrade:
    status: str
    points: int
    coverage: float
    brier: float | None
    log_loss: float | None
    kind: str | None = None


@dataclass(frozen=True)
class GameGrade:
    game_id: str
    week: int
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    status: str
    window_seconds: float | None
    forecasters: dict[str, ForecastGrade] = field(default_factory=dict)


@dataclass(frozen=True)
class ForecasterSummary:
    games: int
    brier: float | None
    log_loss: float | None


@dataclass(frozen=True)
class Summary:
    games_graded: int
    forecasters: dict[str, ForecasterSummary]


def _valid(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and 0.0 <= value <= 1.0


def held_segments(points: list[Point], start: datetime, end: datetime) -> list[tuple[float, float]]:
    """(value, seconds) for each valid point, held until the next point or the end, clipped to [start, end]."""
    segments: list[tuple[float, float]] = []
    for i, point in enumerate(points):
        until = min(points[i + 1].at, end) if i + 1 < len(points) else end
        seconds = (until - max(point.at, start)).total_seconds()
        if seconds > 0 and point.value is not None and _valid(point.value):
            segments.append((point.value, seconds))
    return segments


def _grade_series(
    segments: list[tuple[float, float]], window: float, home_won: bool, min_points: int, min_coverage: float
) -> ForecastGrade:
    covered = sum(seconds for _, seconds in segments)
    coverage = covered / window if window > 0 else 0.0
    if len(segments) < min_points or coverage < min_coverage or covered <= 0:
        return ForecastGrade("not_enough_data", len(segments), coverage, None, None)
    p = np.array([v for v, _ in segments])
    weights = np.array([s for _, s in segments])
    y = np.full(len(segments), 1.0 if home_won else 0.0)
    brier = float(np.average((p - y) ** 2, weights=weights))
    log_loss = float(np.average(game_log_loss(p, y), weights=weights))
    return ForecastGrade("scored", len(segments), coverage, brier, log_loss)


def _pregame(game: Game, predictions: list, start: datetime, end: datetime, home_won: bool) -> ForecastGrade:
    before = [p for p in predictions if p.created_at < game.kickoff_utc and p.kind != "backfill"]
    backfill = [p for p in predictions if p.kind == "backfill"]
    chosen = (before or backfill or [None])[-1]
    window = (end - start).total_seconds()
    segments = [(chosen.home_win_prob, window)] if chosen is not None and _valid(chosen.home_win_prob) else []
    grade = _grade_series(segments, window, home_won, 1, 0.0)
    return replace(grade, kind=chosen.kind if chosen is not None else None)


def _grade_game(game: Game, states: list, quotes: list, predictions: list) -> GameGrade:
    def result(status: str, window: float | None = None, forecasters: dict | None = None) -> GameGrade:
        return GameGrade(game.game_id, game.week, game.home_team, game.away_team, game.home_score, game.away_score,
                         status, window, forecasters or {})  # fmt: skip

    final = game.status == "final" and game.home_score is not None and game.away_score is not None
    if not final:
        return result("in_progress")
    if game.home_score == game.away_score:
        return result("tie")
    first_in = next((s for s in states if s.state == "in"), None)
    if first_in is None:
        return result("no_live_data")
    after = states[states.index(first_in) + 1 :]
    last_row = next((s for s in after if s.state == "post"), None)
    if last_row is None:
        return result("in_progress" if states[-1].state == "in" else "incomplete")
    states = states[: states.index(last_row) + 1]
    start, end = first_in.fetched_at, last_row.fetched_at
    home_won = game.home_score > game.away_score
    window = (end - start).total_seconds()
    espn = [Point(s.fetched_at, s.home_wp if s.state == "in" else None) for s in states]
    kalshi = [Point(q.fetched_at, q.home_prob) for q in quotes]
    forecasters = {
        "pregame_model": _pregame(game, predictions, start, end, home_won),
        "espn_live": _grade_series(held_segments(espn, start, end), window, home_won, MIN_POINTS, MIN_COVERAGE),
        "kalshi_live": _grade_series(held_segments(kalshi, start, end), window, home_won, MIN_POINTS, MIN_COVERAGE),
    }
    return result("graded", window, forecasters)


def _by_game(session: Session, *columns, season: int, order: tuple, where: tuple = ()) -> dict[str, list]:
    rows = session.execute(select(*columns).join(Game, Game.game_id == columns[0]).where(Game.season == season, *where)
                           .order_by(*order))  # fmt: skip
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row.game_id].append(row)
    return grouped


def grade_season(session: Session, season: int) -> list[GameGrade]:
    """Grades for every game of the season that has live data, ordered by (week, kickoff, game_id)."""
    games = session.scalars(
        select(Game).where(Game.season == season).order_by(Game.week, Game.kickoff_utc, Game.game_id)
    ).all()
    states = _by_game(
        session, LiveState.game_id, LiveState.id, LiveState.fetched_at, LiveState.state, LiveState.home_wp,
        season=season, order=(LiveState.fetched_at, LiveState.id),
    )  # fmt: skip
    quotes = _by_game(
        session, MarketQuote.game_id, MarketQuote.id, MarketQuote.fetched_at, MarketQuote.home_prob,
        season=season, order=(MarketQuote.fetched_at, MarketQuote.id),
        where=(MarketQuote.source == "kalshi", MarketQuote.kind == "live"),
    )  # fmt: skip
    predictions = _by_game(
        session, Prediction.game_id, Prediction.id, Prediction.created_at, Prediction.kind, Prediction.home_win_prob,
        season=season, order=(Prediction.created_at, Prediction.id),
    )  # fmt: skip
    return [
        _grade_game(g, states[g.game_id], quotes[g.game_id], predictions[g.game_id])
        for g in games
        if states.get(g.game_id)
    ]


def summarise(grades: list[GameGrade]) -> Summary:
    """Equal-weight mean per game of Brier and log loss, over the games where each forecaster was scored."""
    out: dict[str, ForecasterSummary] = {}
    for name in NAMES:
        scored = [
            x.forecasters[name] for x in grades if name in x.forecasters and x.forecasters[name].status == "scored"
        ]
        out[name] = ForecasterSummary(
            len(scored),
            float(np.mean([f.brier for f in scored])) if scored else None,
            float(np.mean([f.log_loss for f in scored])) if scored else None,
        )
    return Summary(sum(x.status == "graded" for x in grades), out)
