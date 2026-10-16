"""Web Push alerts for the PWA (iPhone Home Screen app, iOS 16.4+, and desktop browsers).

Kinds: prediction changes, QB injury status, and game-day kickoff reminders.
Every alert has a dedupe key so a rerun never sends it twice. No Apple developer account is
needed; the server signs messages with its own VAPID key.
"""

import base64
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
from requests import RequestException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nflpi.config import get_settings
from nflpi.models import AppSetting, Game, InjuryReport, Notification, PushSubscription
from nflpi.predictions.events import ChangeEvent
from nflpi.predictions.sheet import is_locked, lock_time

log = logging.getLogger(__name__)
ALERT_STATUSES = {"Out", "Doubtful", "Questionable"}
EASTERN = ZoneInfo("America/New_York")
LABEL_WORDS = {"coin_flip": "a coin flip", "tough_matchup": "a tough matchup", "easy_pick": "an easy pick"}


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


def record(session: Session, kind: str, game_id: str | None, key: str, payload: dict) -> bool:
    """Store the alert; False if it was already sent."""
    try:
        with session.begin_nested():
            session.add(Notification(kind=kind, game_id=game_id, dedupe_key=key, payload=payload))
        return True
    except IntegrityError:
        return False


def send(
    session: Session, title: str, body: str, url: str, ttl: int = 6 * 3600, headers: dict[str, str] | None = None,
    results: list[dict] | None = None,
) -> int:
    """Send to every subscription. Drops subscriptions the push service says are gone."""
    if not configured():
        return 0
    s = get_settings()
    sent = 0
    data = json.dumps({"title": title, "body": body, "url": url})
    for sub in session.scalars(select(PushSubscription)).all():
        info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
        host = urlparse(sub.endpoint).hostname or ""
        try:
            response = webpush(
                info,
                data,
                vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject},
                ttl=ttl,
                headers=headers,
                timeout=10,
            )
            sent += 1
            ok, status, error = True, getattr(response, "status_code", None), None
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                session.delete(sub)
            error = (
                "Push service no longer recognizes this device. Turn alerts off and on again."
                if status in (404, 410) else "Push service rejected the alert."
            )
            log.warning("web push failed for %s (%s)", host, status)
            ok = False
        except RequestException:
            log.warning("web push network error for %s", host)
            ok, status, error = False, None, "Could not reach the push service."
        except Exception as exc:  # noqa: BLE001 - one bad subscription must not stop delivery to others
            log.warning("web push failed for %s (%s)", host, type(exc).__name__)
            ok, status, error = False, None, "Could not send this alert."
        if results is not None:
            results.append({"host": host, "ok": ok, "status": status, "error": error})
    return sent


def send_test_alert(session: Session) -> dict:
    """Send a test alert without recording it as a notification."""
    devices = len(session.scalars(select(PushSubscription.id)).all())
    if not configured():
        return {"configured": False, "devices": devices, "delivered": 0, "results": []}
    results: list[dict] = []
    delivered = send(
        session, "Test alert", "Alerts work on this device.", "/settings/",
        ttl=60, headers={"Urgency": "high"}, results=results,
    )
    session.commit()
    return {"configured": True, "devices": devices, "delivered": delivered, "results": results}


def game_url(game_id: str | None) -> str:
    return f"/game/?id={game_id}" if game_id else "/"


def _matchup(session: Session, game_id: str) -> str:
    g = session.get(Game, game_id)
    return f"{g.away_team} @ {g.home_team}" if g else game_id


def alert_prediction_changes(session: Session, events: list[ChangeEvent], now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    sent = 0
    for e in events:
        game = session.get(Game, e.game_id)
        if game is None or game.status != "scheduled" or is_locked(game, now):
            continue
        flipped = e.old_pick != e.new_pick
        matchup = f"{game.away_team} @ {game.home_team}"
        chance = max(e.new_prob, 1 - e.new_prob)
        if flipped:
            kind = "flip"
            title = f"Pick flipped: {matchup}"
            body = f"Now {e.new_pick} ({chance:.0%}). Was {e.old_pick}."
        elif e.qb_team and e.qb_name:
            kind = "qb"
            title = f"QB change: {matchup}"
            body = f"{e.qb_team} starts {e.qb_name}. Pick: {e.new_pick} ({chance:.0%})."
        elif e.old_label and e.new_label and e.old_label != e.new_label:
            kind = "label"
            title = f"Now {LABEL_WORDS[e.new_label]}: {matchup}"
            body = f"Was {LABEL_WORDS[e.old_label]}. Pick: {e.new_pick} ({chance:.0%})."
        else:
            kind = "move"
            title = f"Big move: {matchup}"
            body = f"Home chance {e.old_prob:.0%} → {e.new_prob:.0%}. Pick stays {e.new_pick}."
        change = [kind, e.old_prob, e.new_prob, e.old_pick, e.new_pick, e.old_label, e.new_label, e.qb_team, e.qb_name]
        digest = hashlib.sha256(json.dumps(change).encode()).hexdigest()[:20]
        key = f"pred:{e.game_id}:{kind}:{digest}"
        if session.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None:
            continue
        delivered = send(session, title, body, game_url(e.game_id))
        if not delivered:
            log.warning("alert %s reached 0 devices", key)
        elif record(session, "prediction", e.game_id, key, {"title": title, "body": body}):
            sent += delivered
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
        if session.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None:
            continue
        delivered = send(session, title, body, game_url(gid))
        if not delivered:
            log.warning("alert %s reached 0 devices", key)
        elif record(session, "injury", gid, key, {"title": title, "body": body}):
            sent += delivered
    session.commit()
    return sent


def send_kickoff_reminders(session: Session, now: datetime) -> int:
    """Send one reminder per Eastern game day before its first pick lock."""
    row = session.get(AppSetting, "reminder_minutes")
    minutes = row.value.get("v") if row else None
    minutes = 60 if minutes is None else minutes
    if minutes == 0:
        return 0
    games = session.scalars(
        select(Game).where(
            Game.time_tbd.is_(False),
            Game.status != "postponed",
        ).order_by(Game.kickoff_utc, Game.game_id)
    ).all()
    days: dict[str, list[Game]] = {}
    for game in games:
        day = game.kickoff_utc.astimezone(EASTERN).date().isoformat()
        days.setdefault(day, []).append(game)
    sent = 0
    for day, day_games in days.items():
        first = day_games[0]
        kickoff = first.kickoff_utc
        lock = lock_time(first)
        if not lock - timedelta(minutes=minutes) <= now < lock:
            continue
        lock_clock = lock.astimezone(EASTERN).strftime("%-I:%M %p")
        count = len(day_games)
        title = (
            f"Games today: picks lock {lock_clock} ET"
            if count > 1 else f"Game today: picks lock {lock_clock} ET"
        )
        matchup = f"{first.away_team} @ {first.home_team}"
        body = f"{count} games today. First: {matchup}." if count > 1 else f"1 game today: {matchup}."
        key = f"remind:{day}:{kickoff.isoformat()}"
        if session.scalar(select(Notification.id).where(Notification.dedupe_key == key)) is not None:
            continue
        delivered = send(
            session,
            title,
            body,
            "/sheet/",
            ttl=int((lock - now).total_seconds()),
            headers={"Urgency": "high"},
        )
        if delivered and record(session, "reminder", first.game_id, key, {"title": title, "body": body}):
            sent += delivered
    session.commit()
    return sent
