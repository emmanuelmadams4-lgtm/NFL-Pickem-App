"""Server-side alerts sent through the Expo Push service.

Kinds: prediction flips / big moves, and QB injury status changes.
Kickoff reminders are scheduled on the phone itself (works offline).
Every alert has a dedupe key so a rerun never sends it twice.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nflpi.config import get_settings
from nflpi.models import Game, InjuryReport, Notification, PushDevice
from nflpi.predictions.engine import ChangeEvent

log = logging.getLogger(__name__)
ALERT_STATUSES = {"Out", "Doubtful", "Questionable"}


def _record(session: Session, kind: str, game_id: str | None, key: str, payload: dict) -> bool:
    """Store the alert; False if it was already sent."""
    try:
        with session.begin_nested():
            session.add(Notification(kind=kind, game_id=game_id, dedupe_key=key, payload=payload))
        return True
    except IntegrityError:
        return False


def _send(session: Session, title: str, body: str, data: dict) -> int:
    settings = get_settings()
    tokens = list(session.scalars(select(PushDevice.token)))
    if not tokens:
        return 0
    headers = {"Content-Type": "application/json"}
    if settings.expo_access_token:
        headers["Authorization"] = f"Bearer {settings.expo_access_token}"
    messages = [{"to": t, "title": title, "body": body, "data": data, "sound": "default"} for t in tokens]
    try:
        resp = httpx.post(settings.expo_push_url, json=messages, headers=headers, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("expo push failed: %s", exc)
        return 0
    return len(tokens)


def _matchup(session: Session, game_id: str) -> str:
    g = session.get(Game, game_id)
    return f"{g.away_team} @ {g.home_team}" if g else game_id


def alert_prediction_changes(session: Session, events: list[ChangeEvent]) -> int:
    sent = 0
    for e in events:
        flipped = e.old_pick != e.new_pick
        title = (
            f"Pick flipped: {_matchup(session, e.game_id)}" if flipped else f"Big move: {_matchup(session, e.game_id)}"
        )
        body = (
            f"Now {e.new_pick} ({max(e.new_prob, 1 - e.new_prob):.0%}). Was {e.old_pick}."
            if flipped
            else f"Home chance {e.old_prob:.0%} → {e.new_prob:.0%}. Pick stays {e.new_pick}."
        )
        key = f"pred:{e.game_id}:{e.new_pick}:{round(e.new_prob, 2)}"
        if _record(session, "prediction", e.game_id, key, {"title": title, "body": body}):
            sent += _send(session, title, body, {"gameId": e.game_id})
    session.commit()
    return sent


def alert_injuries(session: Session, changed: list[InjuryReport], season: int, week: int) -> int:
    """Alert when a QB in this week's or next week's games gets an injury status."""
    sent = 0
    for r in changed:
        if r.position != "QB" or r.season != season or r.week not in (week, week + 1):
            continue
        if r.report_status not in ALERT_STATUSES:
            continue
        game = session.scalars(
            select(Game).where(
                Game.season == r.season, Game.week == r.week, (Game.home_team == r.team) | (Game.away_team == r.team)
            )
        ).first()
        title = f"QB injury: {r.player} ({r.team}) {r.report_status}"
        body = f"Week {r.week}. Practice: {r.practice_status or 'n/a'}. Check the pick."
        key = f"inj:{r.season}:{r.week}:{r.player_id or r.player}:{r.report_status}"
        if _record(session, "injury", game.game_id if game else None, key, {"title": title, "body": body}):
            sent += _send(session, title, body, {"gameId": game.game_id if game else None})
    session.commit()
    return sent
