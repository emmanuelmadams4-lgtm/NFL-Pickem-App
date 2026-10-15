"""Alerts when a club star gets an Out, Doubtful or Questionable status (step 8i).

A star changing status inside the last 90 minutes before kickoff is sent on its own. Earlier changes wait for one
summary a day at the set Eastern hour. Alert text comes only from the star list and the injury report.
"""

import logging
import unicodedata
from datetime import datetime, timedelta
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.analytics import stars
from nflpi.config import get_settings
from nflpi.models import AppSetting, Game, InjuryReport, Notification, TeamStar
from nflpi.notify import push

log = logging.getLogger(__name__)
BASELINE_KEY = "star_alerts_baseline"
MAX_CHANGE_AGE = timedelta(hours=48)
IMMEDIATE_WINDOW = timedelta(minutes=90)
SUMMARY_GRACE_HOURS = 3
SUMMARY_LINES = 4
NAME_LIMIT = 40
INJURY_LIMIT = 60


class Change(NamedTuple):
    report: InjuryReport
    star: TeamStar
    game: Game


def _plain(text: str, limit: int) -> str:
    """One plain line: every Unicode category C character is dropped, whitespace runs become one space."""
    spaced = "".join(" " if ch.isspace() else ch for ch in text)
    kept = "".join(ch for ch in spaced if not unicodedata.category(ch).startswith("C"))
    return " ".join(kept.split())[:limit].strip()


def _seen(session: Session, *keys: str) -> bool:
    return session.scalar(select(Notification.id).where(Notification.dedupe_key.in_(keys)).limit(1)) is not None


def _same_player_rows(report: InjuryReport) -> tuple:
    """Where-clauses for rows about the same player, season, week and team as this report."""
    same_player = (
        InjuryReport.player_id == report.player_id
        if report.player_id else InjuryReport.player_id.is_(None) & (InjuryReport.player == report.player)
    )
    return (InjuryReport.season == report.season, InjuryReport.week == report.week, InjuryReport.team == report.team,
            same_player)


def _is_change(session: Session, report: InjuryReport) -> bool:
    previous = session.scalars(
        select(InjuryReport)
        .where(*_same_player_rows(report), InjuryReport.id < report.id)
        .order_by(InjuryReport.id.desc())
        .limit(1)
    ).first()
    return previous is None or previous.report_status != report.report_status


def _superseded(session: Session, report: InjuryReport) -> bool:
    """A later row gives the same player a different status (or none), so this one is stale."""
    status = InjuryReport.report_status
    differs = status.is_(None) | (status != report.report_status)
    return session.scalar(
        select(InjuryReport.id).where(*_same_player_rows(report), InjuryReport.id > report.id, differs).limit(1)
    ) is not None


def _first_with_status(session: Session, report: InjuryReport) -> bool:
    """No earlier row gives the same player this same status that week."""
    return session.scalar(
        select(InjuryReport.id).where(
            *_same_player_rows(report), InjuryReport.id < report.id,
            InjuryReport.report_status == report.report_status,
        ).limit(1)
    ) is None


def _game(session: Session, report: InjuryReport, now: datetime) -> Game | None:
    return session.scalars(
        select(Game)
        .where(
            Game.season == report.season, Game.week == report.week, Game.status == "scheduled",
            Game.kickoff_utc > now, (Game.home_team == report.team) | (Game.away_team == report.team),
        )
        .order_by(Game.kickoff_utc, Game.game_id)
        .limit(1)
    ).first()


def _star(session: Session, report: InjuryReport, game: Game) -> TeamStar | None:
    week = session.scalar(
        select(func.max(TeamStar.week)).where(
            TeamStar.season == game.season, TeamStar.week <= game.week, TeamStar.team == report.team
        )
    )
    if week is None:
        return None
    rows = session.scalars(
        select(TeamStar)
        .where(TeamStar.season == game.season, TeamStar.week == week, TeamStar.team == report.team)
        .order_by(TeamStar.slot, TeamStar.rank)
    ).all()
    return next((row for row in rows if stars.star_report(row, [report]) is not None), None)


def _changes(session: Session, baseline: int, now: datetime) -> list[Change]:
    reports = session.scalars(
        select(InjuryReport)
        .where(
            InjuryReport.id > baseline,
            InjuryReport.observed_at >= now - MAX_CHANGE_AGE,
            InjuryReport.report_status.in_(stars.ALERT_STATUSES),
        )
        .order_by(InjuryReport.id)
    ).all()
    found = []
    for report in reports:
        who = report.player_id or report.player
        injury_key = f"inj:{report.season}:{report.week}:{who}:{report.report_status}"
        if _seen(session, f"star:{report.id}"):
            continue
        if _first_with_status(session, report) and _seen(session, injury_key):
            continue
        if not _is_change(session, report) or _superseded(session, report):
            continue
        game = _game(session, report, now)
        star = _star(session, report, game) if game else None
        if star is not None:
            found.append(Change(report, star, game))
    return found


def _send_immediate(session: Session, change: Change, now: datetime) -> int:
    report, star, game = change
    kickoff = game.kickoff_utc
    name = _plain(star.player, NAME_LIMIT)
    title = f"Star {report.report_status.lower()}: {name} ({star.team})"
    body = f"{game.away_team} @ {game.home_team}, {kickoff.astimezone(push.EASTERN).strftime('%-I:%M %p')} ET."
    injury = _plain(report.injury or "", INJURY_LIMIT)
    if injury:
        body += f" {injury}."
    delivered = push.send(
        session, title, body, push.game_url(game.game_id),
        ttl=max(1, int((kickoff - now).total_seconds())), headers={"Urgency": "high"},
    )
    if not delivered:
        return 0
    push.record(session, "star", game.game_id, f"star:{report.id}", {"title": title, "body": body})
    session.commit()
    return 1


def _immediate(session: Session, changes: list[Change], now: datetime) -> int:
    sent = 0
    for change in changes:
        kickoff = change.game.kickoff_utc
        if change.game.time_tbd or not kickoff - IMMEDIATE_WINDOW <= now < kickoff:
            continue
        try:
            sent += _send_immediate(session, change, now)
        except Exception as exc:  # noqa: BLE001 - one bad alert must not stop the others
            log.warning("star alert failed: %s", type(exc).__name__)
            session.rollback()
    return sent


def _summary(session: Session, changes: list[Change], now: datetime) -> int:
    hour = get_settings().star_summary_hour
    eastern = now.astimezone(push.EASTERN)
    key = f"starsum:{eastern.date().isoformat()}"
    if not hour <= eastern.hour < hour + SUMMARY_GRACE_HOURS or _seen(session, key):
        return 0
    pending = [c for c in changes if c.game.time_tbd or c.game.kickoff_utc - IMMEDIATE_WINDOW > now]
    groups: dict[tuple[str, str], list[Change]] = {}
    for change in pending:
        groups.setdefault((change.star.team, change.star.player_id or change.star.player), []).append(change)
    if not groups:
        return 0
    newest = [max(group, key=lambda c: c.report.id) for group in groups.values()]
    lines = [f"{_plain(c.star.player, NAME_LIMIT)} ({c.star.team}) {c.report.report_status}" for c in newest]
    shown = lines[:SUMMARY_LINES]
    if len(lines) > SUMMARY_LINES:
        shown.append(f"+{len(lines) - SUMMARY_LINES} more")
    title = f"Star report: {len(lines)} change{'s' if len(lines) != 1 else ''} today"
    body = "\n".join(shown)
    if not push.send(session, title, body, "/"):
        return 0
    push.record(session, "starsum", None, key, {"title": title, "body": body})
    for change in pending:
        push.record(session, "star", change.game.game_id, f"star:{change.report.id}", {"title": title, "body": body})
    session.commit()
    return 1


def run(session: Session, now: datetime) -> dict[str, int]:
    """Send due star alerts; return how many alerts were delivered (not devices)."""
    none = {"immediate": 0, "summary": 0}
    if session.scalar(select(TeamStar.team).limit(1)) is None:
        return none
    baseline = session.get(AppSetting, BASELINE_KEY)
    if baseline is None:
        newest_id = session.scalar(select(func.max(InjuryReport.id))) or 0
        session.add(AppSetting(key=BASELINE_KEY, value={"report_id": newest_id}))
        session.commit()
        return none
    changes = _changes(session, baseline.value["report_id"], now)
    result = {"immediate": _immediate(session, changes, now), "summary": 0}
    try:
        result["summary"] = _summary(session, changes, now)
    except Exception as exc:  # noqa: BLE001 - the summary is retried next round
        log.warning("star alert failed: %s", type(exc).__name__)
        session.rollback()
    if result["immediate"] or result["summary"]:
        log.info("star alerts: immediate=%d summary=%d", result["immediate"], result["summary"])
    return result
