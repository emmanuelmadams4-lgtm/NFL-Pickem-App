"""Quarterback history: append a row per club only when the projected starter changes (blank counts as a value)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.models import QbObservation

SIDES = ("home", "away")


def record_qbs(session: Session, games: list[dict], observed_at: datetime) -> int:
    """Insert a QbObservation for each (game, side) with no row yet or whose newest name differs. No commit."""
    newest = {
        (o.game_id, o.side): o.qb
        for o in session.scalars(
            select(QbObservation).where(
                QbObservation.id.in_(
                    select(func.max(QbObservation.id)).group_by(QbObservation.game_id, QbObservation.side)
                )
            )
        )
    }
    new_rows = [
        QbObservation(game_id=g["game_id"], side=side, qb=g[f"{side}_qb"], observed_at=observed_at)
        for g in games
        for side in SIDES
        if (g["game_id"], side) not in newest or newest[(g["game_id"], side)] != g[f"{side}_qb"]
    ]
    session.add_all(new_rows)
    return len(new_rows)
