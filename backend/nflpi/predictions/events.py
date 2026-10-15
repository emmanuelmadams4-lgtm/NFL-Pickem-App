"""Prediction change events, kept apart from the engine so alerts need not import the engine's heavy imports."""

from dataclasses import dataclass


@dataclass
class ChangeEvent:
    game_id: str
    old_prob: float
    new_prob: float
    old_pick: str
    new_pick: str
    note: str
    old_label: str | None = None
    new_label: str | None = None
    qb_team: str | None = None
    qb_name: str | None = None
