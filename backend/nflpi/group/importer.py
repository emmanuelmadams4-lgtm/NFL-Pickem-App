"""Check Yahoo group CSV files completely before storing their rows."""

import csv
import io
import re
import unicodedata
from collections.abc import Iterator
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from nflpi.ingestion.nflverse import franchise
from nflpi.models import Game, GroupPick, GroupStanding

MAX_BYTES = 1_000_000
MAX_WEEKS = 22
MAX_GAMES = 16
MAX_CONFIDENCE = 16
MAX_POINTS = 136
MAX_RANK = 9999
MAX_NAME_LENGTH = 64
MAX_TOTAL_POINTS = MAX_WEEKS * MAX_POINTS
PICKS_HEADER = ["Week", "Team", "Game", "Favored", "Spread", "Underdog", "Pick", "Side", "Confidence",
                "Week_Total_Pts"]
SPREAD_PATTERN = r"[0-9]{1,2}(?:\.[0-9])?"


class GroupImportError(ValueError):
    """The group file cannot be imported."""


class ImportResult(NamedTuple):
    kind: str
    rows: int


def _number(cell: str, label: str, minimum: int, maximum: int, line: int) -> int:
    digits = cell.lstrip("0") or "0"
    if (not re.fullmatch(r"[0-9]+", cell) or len(digits) > len(str(maximum))
            or not minimum <= int(digits) <= maximum):
        raise GroupImportError(f"line {line}: {label} is invalid")
    return int(digits)


def _name(cell: str, line: int) -> str:
    normalized = unicodedata.normalize("NFC", cell)
    cleaned = " ".join("".join(ch for ch in normalized if not unicodedata.category(ch).startswith("C")).split())
    if not cleaned or len(cleaned) > MAX_NAME_LENGTH:
        raise GroupImportError(f"line {line}: name is empty or too long")
    return cleaned


def _csv_rows(text: str) -> tuple[str, int, Iterator[list[str]]]:
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader, [])
    except csv.Error as exc:
        raise GroupImportError("columns are invalid") from exc
    if header == PICKS_HEADER:
        kind, weeks = "picks", 0
    elif (len(header) >= 4 and header[:2] == ["Rank", "Team"] and header[-1] == "Total_Pts"
          and len(header) - 3 <= MAX_WEEKS
          and header[2:-1] == [f"Wk{week}" for week in range(1, len(header) - 2)]):
        kind, weeks = "standings", len(header) - 3
    else:
        raise GroupImportError("columns are invalid")
    return kind, weeks, reader


def _rows(reader: Iterator[list[str]]) -> Iterator[tuple[int, list[str]]]:
    line = 2
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            raise GroupImportError(f"line {line}: cells are invalid") from exc
        yield line, row
        line += 1


def _games(session: Session, season: int) -> dict[tuple[int, frozenset[str]], list[str]]:
    matches: dict[tuple[int, frozenset[str]], list[str]] = {}
    for game_id, week, away, home in session.execute(
        select(Game.game_id, Game.week, Game.away_team, Game.home_team).where(Game.season == season)
    ):
        matches.setdefault((week, frozenset((away, home))), []).append(game_id)
    return matches


def _pick_row(
    cells: list[str], line: int, matches: dict[tuple[int, frozenset[str]], list[str]]
) -> tuple[dict, int]:
    week = _number(cells[0], "week", 1, MAX_WEEKS, line)
    member = _name(cells[1], line)
    # Game and Week_Total_Pts are checked, never stored; scoring uses straight winners with confidence points (P10).
    _number(cells[2], "game", 1, MAX_GAMES, line)
    favored = franchise(cells[3].upper())
    if not re.fullmatch(SPREAD_PATTERN, cells[4]):
        raise GroupImportError(f"line {line}: spread is invalid")
    underdog = franchise(cells[5].upper())
    confidence = _number(cells[8], "confidence", 1, MAX_CONFIDENCE, line) if cells[8] else None
    _number(cells[9], "total", 0, MAX_POINTS, line)
    games = matches.get((week, frozenset((favored, underdog))), [])
    if len(games) != 1:
        raise GroupImportError(f"line {line}: no game matches this matchup")
    side = cells[7]
    if side not in ("Favorite", "Underdog", "none"):
        raise GroupImportError(f"line {line}: side is invalid")
    if side == "none":
        if cells[6]:
            raise GroupImportError(f"line {line}: pick must be empty")
        if confidence is not None:
            raise GroupImportError(f"line {line}: confidence must be empty")
        picked_team = None
    else:
        picked_team = franchise(cells[6].upper()) if cells[6] else None
        if picked_team != (favored if side == "Favorite" else underdog):
            raise GroupImportError(f"line {line}: pick is invalid")
        if confidence is None:
            raise GroupImportError(f"line {line}: confidence is missing")
    value = {"game_id": games[0], "member": member, "picked_team": picked_team, "confidence": confidence}
    return value, week


def _pick_rows(rows: Iterator[list[str]], session: Session, season: int) -> list[dict]:
    matches = _games(session, season)
    values = []
    seen_games: set[tuple[str, str]] = set()
    seen_confidence: set[tuple[str, int, int]] = set()
    for line, cells in _rows(rows):
        if len(cells) != len(PICKS_HEADER):
            raise GroupImportError(f"line {line}: wrong number of cells")
        value, week = _pick_row(cells, line, matches)
        confidence = value["confidence"]
        game_key = (value["game_id"], value["member"])
        if game_key in seen_games:
            raise GroupImportError(f"line {line}: entry appears twice")
        seen_games.add(game_key)
        if confidence is not None:
            confidence_key = (value["member"], week, confidence)
            if confidence_key in seen_confidence:
                raise GroupImportError(f"line {line}: confidence is repeated")
            seen_confidence.add(confidence_key)
        values.append(value)
    if not values:
        raise GroupImportError("no rows")
    return values


def _standing_rows(rows: Iterator[list[str]], weeks: int, season: int) -> list[dict]:
    values = []
    seen_members: set[str] = set()
    for line, cells in _rows(rows):
        if len(cells) != weeks + 3:
            raise GroupImportError(f"line {line}: wrong number of cells")
        rank = _number(cells[0], "rank", 1, MAX_RANK, line)
        member = _name(cells[1], line)
        points = [_number(cell, "points", 0, MAX_POINTS, line) for cell in cells[2:-1]]
        total = _number(cells[-1], "total", 0, MAX_TOTAL_POINTS, line)
        if total != sum(points):
            raise GroupImportError(f"line {line}: total does not match the weeks")
        if member in seen_members:
            raise GroupImportError(f"line {line}: member appears twice")
        seen_members.add(member)
        values.extend({"season": season, "week": week, "member": member, "points": score,
                       "rank": rank if week == weeks else None} for week, score in enumerate(points, start=1))
    if not values:
        raise GroupImportError("no rows")
    return values


def _write_picks(session: Session, rows: list[dict]) -> None:
    statement = insert(GroupPick)
    session.execute(statement.on_conflict_do_update(
        index_elements=[GroupPick.game_id, GroupPick.member],
        set_={"picked_team": statement.excluded.picked_team, "confidence": statement.excluded.confidence,
              "imported_at": statement.excluded.imported_at},
    ), rows)


def _write_standings(session: Session, rows: list[dict]) -> None:
    statement = insert(GroupStanding)
    session.execute(statement.on_conflict_do_update(
        index_elements=[GroupStanding.season, GroupStanding.week, GroupStanding.member],
        set_={"points": statement.excluded.points,
              "rank": func.coalesce(statement.excluded.rank, GroupStanding.rank),
              "imported_at": statement.excluded.imported_at},
    ), rows)


def import_group_csv(session: Session, season: int, data: bytes) -> ImportResult:
    """Import one fully checked picks or weekly standings file."""
    if len(data) > MAX_BYTES:
        raise GroupImportError("file is too large")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GroupImportError("file is not UTF-8") from exc
    kind, weeks, rows = _csv_rows(text)
    try:
        if kind == "picks":
            values = _pick_rows(rows, session, season)
            _write_picks(session, values)
        else:
            values = _standing_rows(rows, weeks, season)
            _write_standings(session, values)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise RuntimeError(f"group import: database error ({type(exc).__name__})") from None
    except Exception:
        session.rollback()
        raise
    return ImportResult(kind, len(values))
