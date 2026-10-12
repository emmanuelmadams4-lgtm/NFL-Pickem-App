"""Compute open pick sheets and freeze each game at kickoff."""

import logging
import math
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nflpi.ai import jev, research
from nflpi.analytics.metrics import LABEL_HIT_RATE, pick_label
from nflpi.models import AppSetting, Game, PickPoint, Prediction, SheetEntry, UserPick

log = logging.getLogger(__name__)
TIE_BAND = 0.01
TIE_CRITERIA = [
    "The inputs conflict or key information is missing.",
    "The inputs lean toward the pick but have a clear weakness.",
    "The stats and line favor the pick with no major missing information.",
    "The stats and line strongly favor the pick with stable starting quarterbacks.",
]


class Ranked(NamedTuple):
    game_id: str
    prob: float


class Evidence(NamedTuple):
    score: float
    confidence: float


def _number(value: object) -> float | None:
    """A finite number from stored or received JSON, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def _chance(p: Prediction, g: Game, team: str) -> float:
    return p.home_win_prob if team == g.home_team else 1 - p.home_win_prob


def week_size(session: Session, season: int, week: int) -> int:
    games = session.scalars(select(Game).where(Game.season == season, Game.week == week))
    return sum(g.status != "postponed" for g in games)


def _game_row(g: Game, entry: SheetEntry | None, prediction: Prediction | None,
              pick: UserPick | None, history: set[str]) -> dict:
    if entry:
        return dict(label=entry.label, label_hit_rate=LABEL_HIT_RATE.get(entry.label), app_pick=entry.app_pick,
                    app_points=entry.app_points, my_pick=entry.my_pick, my_points=entry.my_points,
                    pick_by=entry.pick_by, points_by=entry.points_by)
    app_pick = prediction.pick if prediction else None
    app_prob = _chance(prediction, g, app_pick) if prediction else None
    label = pick_label(app_prob) if app_prob is not None else None
    return dict(label=label, label_hit_rate=LABEL_HIT_RATE.get(label) if label else None,
                app_pick=app_pick, app_points=None,
                my_pick=pick.picked_team if pick else (None if g.game_id in history else app_pick),
                my_points=None, pick_by=("csv" if pick.source == "csv" else "user") if pick else "app",
                points_by="app")


def _jev_request(games: list[Game], preds: dict[str, Prediction], ranked: list[Ranked]) -> tuple[str, dict]:
    by_id = {g.game_id: g for g in games}
    state = []
    for item in ranked:
        g, p = by_id[item.game_id], preds[item.game_id]
        stats = p.features.get("stats_only_prob")
        agree = ((stats >= 0.5) == (p.market_home_prob >= 0.5)
                 if stats is not None and p.market_home_prob is not None else None)
        qb_change = bool(p.features.get("home_qb_change") or p.features.get("away_qb_change"))
        state.append(f"{g.game_id}: {g.away_team} at {g.home_team}; pick {p.pick}; chance {item.prob:.0%}; "
                     f"stats and line agree {agree}; starting QB change {qb_change}; "
                     f"uncertainty {p.uncertainty}: {', '.join(p.uncertainty_reasons)}")
    questions = {item.game_id: {"type": "score", "instructions":
                 f"How strong is the evidence in the state for the pick in game `{item.game_id}`?",
                 "criteria": TIE_CRITERIA} for item in ranked}
    return "\n".join(state), questions


def order(games: list[Ranked], evidence: dict[str, Evidence]) -> list[str]:
    ranked = sorted(games, key=lambda g: (-g.prob, g.game_id))
    i = 0
    while i < len(ranked) - 1:
        upper, lower = ranked[i:i + 2]
        a, b = evidence.get(upper.game_id), evidence.get(lower.game_id)
        if (upper.prob - lower.prob < TIE_BAND and a and b and a.confidence >= 0.8
                and b.confidence >= 0.8 and b.score >= a.score + 1.0):
            ranked[i], ranked[i + 1] = lower, upper
            i += 2
        else:
            i += 1
    return [g.game_id for g in ranked]


def recommendations(session: Session, games: list[Game]) -> dict[str, Prediction]:
    ids = [g.game_id for g in games]
    if not ids:
        return {}
    by_id = {g.game_id: g for g in games}
    rows = session.scalars(select(Prediction).where(Prediction.game_id.in_(ids)).order_by(Prediction.id)).all()
    return {p.game_id: p for p in rows if p.created_at < by_id[p.game_id].kickoff_utc or p.kind == "backfill"}


def _evidence(session: Session, season: int, week: int, preds: dict[str, Prediction]) -> dict[str, Evidence]:
    row = session.get(AppSetting, f"jev_tiebreak_{season}_{week}")
    cached = row.value if row and isinstance(row.value, dict) else {}
    evidence = {}
    for gid, p in preds.items():
        value = cached.get(gid)
        if not isinstance(value, dict) or value.get("hash") != p.inputs_hash:
            continue
        score, confidence = _number(value.get("score")), _number(value.get("confidence"))
        if score is not None and confidence is not None:
            evidence[gid] = Evidence(score, confidence)
    return evidence


def compute_week(
    session: Session, season: int, week: int, now: datetime, writing: frozenset[str] = frozenset()
) -> dict[str, dict]:
    from nflpi.api.views import is_locked

    games = session.scalars(select(Game).where(Game.season == season, Game.week == week)
                            .order_by(Game.kickoff_utc, Game.game_id)).all()
    ids = [g.game_id for g in games]
    preds = recommendations(session, games)
    entries = {e.game_id: e for e in session.scalars(select(SheetEntry).where(SheetEntry.game_id.in_(ids)))}
    picks = {p.game_id: p for p in session.scalars(select(UserPick).where(UserPick.game_id.in_(ids)))}
    points = {p.game_id: p for p in session.scalars(select(PickPoint).where(PickPoint.game_id.in_(ids)))}
    evidence = _evidence(session, season, week, preds)
    n = sum(g.status != "postponed" for g in games)
    history = {g.game_id for g in games if g.game_id not in entries and g.game_id not in writing and is_locked(g, now)}
    rows = {g.game_id: _game_row(g, entries.get(g.game_id), preds.get(g.game_id), picks.get(g.game_id), history)
            for g in games}
    available_app = set(range(1, n + 1)) - {e.app_points for e in entries.values() if e.app_points is not None}
    available_my = set(range(1, n + 1)) - {e.my_points for e in entries.values() if e.my_points is not None}
    eligible = [g for g in games if g.status != "postponed" and g.game_id not in entries
                and g.game_id not in history and g.game_id in preds]
    for gid, number in zip(order([Ranked(g.game_id, _chance(preds[g.game_id], g, preds[g.game_id].pick))
                                  for g in eligible], evidence),
                           sorted(available_app, reverse=True), strict=False):
        rows[gid]["app_points"] = number
    for g in eligible:
        gid = g.game_id
        number = points[gid].points if gid in points else None
        if number in available_my:
            rows[gid]["my_points"] = number
            rows[gid]["points_by"] = "user"
            available_my.remove(number)
    remaining = [g for g in eligible if rows[g.game_id]["my_points"] is None]
    ranked = [Ranked(g.game_id, _chance(preds[g.game_id], g, rows[g.game_id]["my_pick"])) for g in remaining]
    my_evidence = {gid: value for gid, value in evidence.items() if rows[gid]["my_pick"] == rows[gid]["app_pick"]}
    for gid, number in zip(order(ranked, my_evidence), sorted(available_my, reverse=True), strict=False):
        rows[gid]["my_points"] = number
    for gid, row in rows.items():
        row["differs"] = gid not in history and (row["my_pick"] != row["app_pick"]
                                                 or row["my_points"] != row["app_points"])
    return rows


def finalize(session: Session, now: datetime) -> int:
    setting = session.get(AppSetting, "sheet_start")
    if setting is None:
        session.execute(insert(AppSetting).values(key="sheet_start", value={"at": now.isoformat()})
                        .on_conflict_do_nothing(index_elements=["key"]))
        session.flush()
        setting = session.get(AppSetting, "sheet_start")
    start = datetime.fromisoformat(setting.value["at"])
    has_prediction = select(Prediction.id).where(Prediction.game_id == Game.game_id).exists()
    games = session.scalars(
        select(Game).outerjoin(SheetEntry, SheetEntry.game_id == Game.game_id)
        .where(Game.status != "postponed", SheetEntry.game_id.is_(None), has_prediction,
               or_(Game.status == "final", and_(Game.time_tbd.is_(False), Game.kickoff_utc <= now)),
               or_(Game.status != "final", Game.kickoff_utc >= start))
        .order_by(Game.kickoff_utc, Game.game_id)
    ).all()
    preds = recommendations(session, games)
    written = 0
    for i, g in enumerate(games):
        prediction = preds.get(g.game_id)
        if prediction is None or prediction.kind == "backfill":
            continue
        writing = frozenset(game.game_id for game in games[i:])
        row = compute_week(session, g.season, g.week, now, writing=writing)[g.game_id]
        if row["app_pick"] is None:
            continue
        existing_pick = session.get(UserPick, g.game_id)
        pick_by = row["pick_by"] if existing_pick else "auto"
        values = {k: row[k] for k in ("app_pick", "app_points", "my_pick", "my_points", "label", "points_by")}
        app_prob = _chance(prediction, g, prediction.pick)
        values.update(game_id=g.game_id, app_prob=app_prob, pick_by=pick_by, locked_at=now)
        result = session.execute(insert(SheetEntry).values(**values).on_conflict_do_nothing(index_elements=["game_id"]))
        if result.rowcount:
            written += 1
            if existing_pick is None:
                session.execute(insert(UserPick).values(game_id=g.game_id, picked_team=row["app_pick"],
                                picked_at=now, source="auto").on_conflict_do_nothing(index_elements=["game_id"]))
            point = session.get(PickPoint, g.game_id)
            if point:
                session.delete(point)
    session.commit()
    return written


def refresh_tiebreaks(session: Session, season: int, week: int) -> None:
    from nflpi.api.views import is_locked, now_utc

    games = session.scalars(select(Game).where(Game.season == season, Game.week == week)).all()
    games = [g for g in games if g.status != "postponed" and not is_locked(g, now_utc())]
    if not jev.configured():
        return
    preds = recommendations(session, games)
    ranked = sorted([Ranked(g.game_id, _chance(preds[g.game_id], g, preds[g.game_id].pick))
                     for g in games if g.game_id in preds],
                    key=lambda r: (-r.prob, r.game_id))
    if not any(a.prob - b.prob < TIE_BAND for a, b in zip(ranked, ranked[1:], strict=False)):
        return
    key = f"jev_tiebreak_{season}_{week}"
    setting = session.get(AppSetting, key)
    cached = dict(setting.value) if setting else {}
    asked = [item for item in ranked
             if not (isinstance(cached.get(item.game_id), dict)
                     and cached[item.game_id].get("hash") == preds[item.game_id].inputs_hash)]
    if not asked:
        return
    state, questions = _jev_request(games, preds, asked)
    try:
        research._reserve_call(session)
        answers = jev.decide(state, questions)
        for item in asked:
            gid = item.game_id
            answer = answers.get(gid)
            value = {"hash": preds[gid].inputs_hash}
            answer = answer if isinstance(answer, dict) else {}
            score, confidence = _number(answer.get("score")), _number(answer.get("confidence"))
            if score is not None and confidence is not None:
                value.update(score=score, confidence=confidence)
            cached[gid] = value
        if setting is None:
            session.add(AppSetting(key=key, value=cached))
        else:
            setting.value = cached
        session.commit()
    except Exception:
        log.exception("Jev tie-break unavailable")
        session.rollback()
