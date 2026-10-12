"""Web Push alerts for the PWA (iPhone Home Screen app, iOS 16.4+, and desktop browsers).

Kinds: prediction flips / big moves, QB injury status, and "no pick yet" kickoff reminders.
Every alert has a dedupe key so a rerun never sends it twice. No Apple developer account is
needed; the server signs messages with its own VAPID key.
"""

import base64
import json
import logging
from datetime import datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
from requests import RequestException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nflpi.config import get_settings
from nflpi.models import AppSetting, Game, InjuryReport, Notification, Prediction, PushSubscription, UserPick
from nflpi.predictions.engine import ChangeEvent

log = logging.getLogger(__name__)
ALERT_STATUSES = {"Out", "Doubtful", "Questionable"}


def generate_vapid_keys() -> tuple[str, str]:
    """Return (public, private) as base64url strings for VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return b64(public), b64(private)


def configured() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key and s.vapid_subject)


def _record(session: Session, kind: str, game_id: str | None, key: str, payload: dict) -> bool:
    """Store the alert; False if it was already sent."""
    try:
        with session.begin_nested():
            session.add(Notification(kind=kind, game_id=game_id, dedupe_key=key, payload=payload))
        return True
    except IntegrityError:
        return False


def _send(
    session: Session, title: str, body: str, url: str, ttl: int = 6 * 3600, headers: dict[str, str] | None = None
) -> int:
    """Send to every subscription. Drops subscriptions the push service says are gone."""
    if not configured():
        return 0
    s = get_settings()
    sent = 0
    data = json.dumps({"title": title, "body": body, "url": url})
    for sub in session.scalars(select(PushSubscription)).all():
        info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
        try:
            webpush(
                info,
                data,
                vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject},
                ttl=ttl,
                headers=headers,
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                session.delete(sub)
            log.warning("web push failed for %s (%s): %s", sub.endpoint, status, exc)
        except RequestException as exc:
            log.warning("web push network error for %s: %s", sub.endpoint, exc)
        except Exception:  # noqa: BLE001 - one bad subscription must not stop delivery to others
            log.exception("web push failed for %s", sub.endpoint)
    return sent


def game_url(game_id: str | None) -> str:
    return f"/game/?id={game_id}" if game_id else "/"


def _matchup(session: Session, game_id: str) -> str:
    g = session.get(Game, game_id)
    return f"{g.away_team} @ {g.home_team}" if g else game_id


def alert_prediction_changes(session: Session, events: list[ChangeEvent]) -> int:
    sent = 0
    for e in events:
        flipped = e.old_pick != e.new_pick
        title = f"{'Pick flipped' if flipped else 'Big move'}: {_matchup(session, e.game_id)}"
        body = (
            f"Now {e.new_pick} ({max(e.new_prob, 1 - e.new_prob):.0%}). Was {e.old_pick}."
            if flipped
            else f"Home chance {e.old_prob:.0%} → {e.new_prob:.0%}. Pick stays {e.new_pick}."
        )
        key = f"pred:{e.game_id}:{e.new_pick}:{round(e.new_prob, 2)}"
        if _record(session, "prediction", e.game_id, key, {"title": title, "body": body}):
            sent += _send(session, title, body, game_url(e.game_id))
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
        gid = game.game_id if game else None
        title = f"QB injury: {r.player} ({r.team}) {r.report_status}"
        body = f"Week {r.week}. Practice: {r.practice_status or 'n/a'}. Check the pick."
        key = f"inj:{r.season}:{r.week}:{r.player_id or r.player}:{r.report_status}"
        if _record(session, "injury", gid, key, {"title": title, "body": body}):
            sent += _send(session, title, body, game_url(gid))
    session.commit()
    return sent


def send_kickoff_reminders(session: Session, now: datetime) -> int:
    """'No pick yet' for games kicking off within the reminder window (setting: reminder_minutes)."""
    row = session.get(AppSetting, "reminder_minutes")
    minutes = row.value.get("v") if row else None
    if not minutes:
        return 0
    soon = session.scalars(
        select(Game).where(
            Game.status == "scheduled",
            Game.time_tbd.is_(False),
            Game.kickoff_utc > now,
            Game.kickoff_utc <= now + timedelta(minutes=minutes),
        )
    ).all()
    picked = set(session.scalars(select(UserPick.game_id).where(UserPick.game_id.in_([g.game_id for g in soon]))))
    sent = 0
    for g in soon:
        if g.game_id in picked:
            continue
        pred = session.scalars(
            select(Prediction).where(Prediction.game_id == g.game_id).order_by(Prediction.id.desc()).limit(1)
        ).first()
        mins = int((g.kickoff_utc - now).total_seconds() // 60)
        title = f"No pick yet: {g.away_team} @ {g.home_team}"
        model = f" Model: {pred.pick} {max(pred.home_win_prob, 1 - pred.home_win_prob):.0%}." if pred else ""
        body = f"Kicks off in {mins} min.{model}"
        key = f"remind:{g.game_id}:{g.kickoff_utc.isoformat()}"
        if session.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None:
            continue
        delivered = _send(
            session,
            title,
            body,
            game_url(g.game_id),
            ttl=int((g.kickoff_utc - now).total_seconds()),
            headers={"Urgency": "high"},
        )
        if delivered and _record(session, "reminder", g.game_id, key, {"title": title, "body": body}):
            sent += delivered
    session.commit()
    return sent
