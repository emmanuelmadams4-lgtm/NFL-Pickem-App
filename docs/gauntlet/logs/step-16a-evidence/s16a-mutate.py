"""Step 16a mutation pass: break one frozen clause at a time and prove a test in tests/test_group.py fails.

Run from backend/ on the lane database (one run at a time; hold coord lock res:gate):
  DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15445/nflpi_test \
    uv run python ../docs/gauntlet/logs/step-16a-evidence/s16a-mutate.py [id ...]
Each line of output: KILLED or SURVIVED, the criterion, the change. Files are restored after every mutant.
"""

import os
import subprocess
import sys
from pathlib import Path

IMP = Path("nflpi/group/importer.py")
QRY = Path("nflpi/group/queries.py")
# (criterion, file, old text, new text, which occurrence of the old text)
MUTANTS = [
    ("N1", IMP, "len(data) > MAX_BYTES", "len(data) >= MAX_BYTES", 0),
    ("N1", IMP, "MAX_BYTES = 1_000_000", "MAX_BYTES = 2_000_000", 0),
    ("N2", IMP, 'data.decode("utf-8-sig")', 'data.decode("utf-8")', 0),
    ("N2", IMP, 'data.decode("utf-8-sig")', 'data.decode("utf-8-sig", errors="replace")', 0),
    ("N3", IMP, "header == PICKS_HEADER", "header[:10] == PICKS_HEADER", 0),
    ("N3", IMP, "len(header) - 3 <= MAX_WEEKS", "len(header) - 3 <= MAX_WEEKS + 1", 0),
    ("N3", IMP, 'header[2:-1] == [f"Wk{week}" for week in range(1, len(header) - 2)]',
     'all(h.startswith("Wk") for h in header[2:-1])', 0),
    ("N3", IMP, 'header[-1] == "Total_Pts"', "True", 0),
    ("N3", IMP, "len(header) >= 4", "len(header) >= 3", 0),
    ("N3", IMP, 'header[:2] == ["Rank", "Team"]', 'sorted(header[:2]) == ["Rank", "Team"]', 0),
    ("N4", IMP, "if len(cells) != len(PICKS_HEADER):", "if len(cells) < len(PICKS_HEADER):", 0),
    ("N4", IMP, "if len(cells) != len(PICKS_HEADER):", "if len(cells) > len(PICKS_HEADER):", 0),
    ("N4", IMP, "if len(cells) != weeks + 3:", "if len(cells) < weeks + 3:", 0),
    ("N4", IMP, "if len(cells) != weeks + 3:", "if len(cells) > weeks + 3:", 0),
    ("N4", IMP, 'if not values:\n        raise GroupImportError("no rows")', "if False:\n        pass", 0),
    ("N4", IMP, 'if not values:\n        raise GroupImportError("no rows")', "if False:\n        pass", 1),
    ("N5", IMP, 'startswith("C")', 'startswith(("Cc", "Cf"))', 0),
    ("N5", IMP, 'startswith("C")', 'startswith(("Cc", "Co", "Cn", "Cs"))', 0),
    ("N5", IMP, 'normalized = unicodedata.normalize("NFC", cell)', "normalized = cell", 0),
    ("N5", IMP, "not unicodedata.category(ch).startswith(\"C\")).split())",
     "not unicodedata.category(ch).startswith(\"C\")).split(\" \")).strip()", 0),
    ("N5", IMP, 'normalized = unicodedata.normalize("NFC", cell)',
     'normalized = unicodedata.normalize("NFC", cell).replace("\\t", " ").replace("\\n", " ")', 0),
    ("N6", IMP, "len(cleaned) > MAX_NAME_LENGTH", "len(cell) > MAX_NAME_LENGTH", 0),
    ("N6", IMP, "len(cleaned) > MAX_NAME_LENGTH", "len(cleaned) >= MAX_NAME_LENGTH", 0),
    ("N6", IMP, "MAX_NAME_LENGTH = 64", "MAX_NAME_LENGTH = 65", 0),
    ("N6", IMP, "if not cleaned or len(cleaned)", "if len(cleaned)", 0),
    ("P7", IMP, 're.fullmatch(r"[0-9]+", cell)', 're.match(r"[0-9]+$", cell)', 0),
    ("P7", IMP, 'not re.fullmatch(r"[0-9]+", cell)', "not cell.isdigit()", 0),
    ("P7", IMP, 'digits = cell.lstrip("0") or "0"', "digits = cell", 0),
    ("P6", IMP, '"week", 1, MAX_WEEKS', '"week", 0, MAX_WEEKS', 0),
    ("P6", IMP, "MAX_WEEKS = 22", "MAX_WEEKS = 23", 0),
    ("P6", IMP, "MAX_WEEKS = 22", "MAX_WEEKS = 21", 0),
    ("P6", IMP, '"game", 1, MAX_GAMES', '"game", 0, MAX_GAMES', 0),
    ("P6", IMP, "MAX_GAMES = 16", "MAX_GAMES = 17", 0),
    ("P6", IMP, "MAX_GAMES = 16", "MAX_GAMES = 15", 0),
    ("P6", IMP, '"confidence", 1, MAX_CONFIDENCE', '"confidence", 0, MAX_CONFIDENCE', 0),
    ("P6", IMP, "MAX_CONFIDENCE = 16", "MAX_CONFIDENCE = 17", 0),
    ("P6", IMP, "MAX_CONFIDENCE = 16", "MAX_CONFIDENCE = 15", 0),
    ("P6", IMP, "MAX_POINTS = 136", "MAX_POINTS = 137", 0),
    ("P6", IMP, "MAX_POINTS = 136", "MAX_POINTS = 135", 0),
    ("P6", IMP, '"[0-9]{1,2}(?:\\.[0-9])?"', '"[0-9]{1,3}(?:\\.[0-9])?"', 0),
    ("P6", IMP, '"[0-9]{1,2}(?:\\.[0-9])?"', '"[0-9]{1,2}(?:\\.[0-9]*)?"', 0),
    ("P6", IMP, '"[0-9]{1,2}(?:\\.[0-9])?"', '"[0-9]{1,2}"', 0),
    ("P6", IMP, "if not re.fullmatch(SPREAD_PATTERN, cells[4]):", "if not re.match(SPREAD_PATTERN, cells[4]):", 0),
    ("P2", IMP, "favored = franchise(cells[3].upper())", "favored = cells[3].upper()", 0),
    ("P2", IMP, "favored = franchise(cells[3].upper())", "favored = franchise(cells[3])", 0),
    ("P2", IMP, "underdog = franchise(cells[5].upper())", "underdog = franchise(cells[5])", 0),
    ("P2", IMP, "franchise(cells[6].upper()) if cells[6]", "franchise(cells[6]) if cells[6]", 0),
    ("P2", IMP, "franchise(cells[6].upper()) if cells[6]", "cells[6].upper() if cells[6]", 0),
    ("P4", IMP, "if len(games) != 1:", "if not games:", 0),
    ("P4", IMP, "where(Game.season == season)", "where(Game.season >= 0)", 0),
    ("P4", IMP, "matches.setdefault((week, frozenset((away, home))), [])",
     "matches.setdefault((1, frozenset((away, home))), [])", 0),
    ("P4", IMP, "favored = franchise(cells[3].upper())", "favored = franchise(cells[3].strip().upper())", 0),
    ("P5", IMP, 'if side not in ("Favorite", "Underdog", "none"):',
     'if side.lower() not in ("favorite", "underdog", "none"):', 0),
    ("P5", IMP, "        if cells[6]:\n", "        if False:\n", 0),
    ("P5", IMP, '        if confidence is not None:\n            raise GroupImportError(f"line {line}: confidence must',
     '        if False:\n            raise GroupImportError(f"line {line}: confidence must', 0),
    ("P5", IMP, 'if picked_team != (favored if side == "Favorite" else underdog):',
     "if picked_team not in (favored, underdog):", 0),
    ("P5", IMP, 'if picked_team != (favored if side == "Favorite" else underdog):',
     'if picked_team != (underdog if side == "Favorite" else favored):', 0),
    ("P5", IMP, '        if confidence is None:\n', "        if False:\n", 0),
    ("P8", IMP, "if game_key in seen_games:", "if False:", 0),
    ("P8", IMP, 'game_key = (value["game_id"], value["member"])', 'game_key = (value["game_id"], cells[1])', 0),
    ("P9", IMP, 'confidence_key = (value["member"], week, confidence)', 'confidence_key = (value["member"], confidence)', 0),
    ("P9", IMP, 'confidence_key = (value["member"], week, confidence)', "confidence_key = (week, confidence)", 0),
    ("P9", IMP, "if confidence_key in seen_confidence:", "if False:", 0),
    ("P1/P10", IMP, '"picked_team": picked_team, "confidence"', '"picked_team": favored, "confidence"', 0),
    ("P1", IMP, '"member": member, "picked_team"', '"member": cells[1], "picked_team"', 0),
    ("P1", IMP, "return ImportResult(kind, len(values))", "return ImportResult(kind, 0)", 0),
    ("P1", IMP, 'kind, weeks = "picks", 0', 'kind, weeks = "standings", 0', 0),
    ("N8", IMP, '{label} is invalid")', '{label} is invalid {cell[:40]!r}")', 0),
    ("N8", IMP, 'name is empty or too long")', 'name is empty or too long {cell[:10]}")', 0),
    ("N8", IMP, 'spread is invalid")', 'spread is invalid {cells[4][:40]}")', 0),
    ("N8", IMP, 'no game matches this matchup")', 'no game matches this matchup {cells[3][:40]} {cells[5][:40]}")', 0),
    ("N8", IMP, 'side is invalid")', 'side is invalid {side[:40]}")', 0),
    ("N8", IMP, 'pick is invalid")', 'pick is invalid {cells[6][:40]}")', 0),
    ("N8", IMP, 'entry appears twice")', 'entry appears twice {value["member"]}")', 0),
    ("N8", IMP, 'confidence is repeated")', 'confidence is repeated {value["member"]}")', 0),
    ("N8", IMP, 'member appears twice")', 'member appears twice {member}")', 0),
    ("N8", IMP, 'raise GroupImportError("columns are invalid")\n    return',
     'raise GroupImportError(f"columns are invalid {header}")\n    return', 0),
    ("N8", IMP, "    line = 2\n", "    line = 1\n", 0),
    ("N8", IMP, "class GroupImportError(ValueError):", "class GroupImportError(Exception):", 0),
    ("N7", IMP, "        values.append(value)\n",
     "        values.append(value)\n        _write_picks(session, [value])\n        session.commit()\n", 0),
    ("N10", IMP, '"confidence": statement.excluded.confidence,', "", 0),
    ("N10", IMP, '"picked_team": statement.excluded.picked_team, ', "", 0),
    ("N10", IMP, '              "imported_at": statement.excluded.imported_at},', "              },", 0),
    ("N10", IMP, '              "imported_at": statement.excluded.imported_at},', "              },", 1),
    ("N10", IMP, 'set_={"points": statement.excluded.points,', "set_={", 0),
    ("N9", IMP, "statement.on_conflict_do_update(\n        index_elements=[GroupPick.game_id, GroupPick.member],\n"
     '        set_={"picked_team": statement.excluded.picked_team, "confidence": statement.excluded.confidence,\n'
     '              "imported_at": statement.excluded.imported_at},\n    )',
     "statement.on_conflict_do_nothing()", 0),
    ("N11", IMP, "    ), rows)", "    ), rows[:1000])", 0),
    ("N11", IMP, "    ), rows)", "    ), rows[:1000])", 1),
    ("N12", IMP, "from None", "from exc", 0),
    ("N12", IMP, 'raise RuntimeError(f"group import', 'raise GroupImportError(f"group import', 0),
    ("N12", IMP, 'database error ({type(exc).__name__})', "database error ({exc})", 0),
    ("N12", IMP, "    except SQLAlchemyError as exc:\n        session.rollback()", "    except SQLAlchemyError as exc:\n        pass", 0),
    ("N12", IMP, "    except Exception:\n        session.rollback()", "    except Exception:\n        pass", 0),
    ("N12", IMP, "    except Exception:\n        session.rollback()", "    except GroupImportError:\n        session.rollback()", 0),
    ("W1", IMP, '"rank": rank if week == weeks else None}', '"rank": rank}', 0),
    ("W1", IMP, '"rank": rank if week == weeks else None}', '"rank": rank if week == 1 else None}', 0),
    ("W1", IMP, "enumerate(points, start=1)", "enumerate(points, start=0)", 0),
    ("W1", IMP, 'kind, weeks = "standings", len(header) - 3', 'kind, weeks = "picks", len(header) - 3', 0),
    ("W2", IMP, '"rank", 1, MAX_RANK', '"rank", 0, MAX_RANK', 0),
    ("W2", IMP, "MAX_RANK = 9999", "MAX_RANK = 10000", 0),
    ("W2", IMP, "MAX_RANK = 9999", "MAX_RANK = 9998", 0),
    ("W2", IMP, '"points", 0, MAX_POINTS, line) for cell in cells[2:-1]', '"points", 0, 999, line) for cell in cells[2:-1]', 0),
    ("W2", IMP, "if total != sum(points):", "if False:", 0),
    ("W2", IMP, "if member in seen_members:", "if False:", 0),
    ("W2", IMP, "seen_members.add(member)", "seen_members.add(cells[1])", 0),
    ("W3", IMP, "func.coalesce(statement.excluded.rank, GroupStanding.rank)", "statement.excluded.rank", 0),
    ("W3", IMP, "func.coalesce(statement.excluded.rank, GroupStanding.rank)",
     "func.coalesce(GroupStanding.rank, statement.excluded.rank)", 0),
    ("W4", IMP, '{"season": season, "week": week', '{"season": 2023, "week": week', 0),
    ("Q1", QRY, "picked = sum(team is not None for team, _ in picks)", "picked = len(picks)", 0),
    ("Q1", QRY, '"members": len(picks)', '"members": picked', 0),
    ("Q1", QRY, '(("away", game.away_team), ("home", game.home_team))', '(("away", game.home_team), ("home", game.away_team))', 0),
    ("Q1", QRY, "sum(confidence) / len(confidence)", "sum(confidence) / picked", 0),
    ("Q1", QRY, "count = sum(chosen == team for chosen, _ in picks)", "count = sum(chosen is not None for chosen, _ in picks)", 0),
    ("Q2", QRY, '"share": count / picked if picked else None', '"share": count / picked if picked else 0.0', 0),
    ("Q2", QRY, "if confidence else None", "if confidence else 0.0", 0),
    ("Q3", QRY, 'raise LookupError("game not found")', "return {}", 0),
    ("Q4", QRY, "GroupStanding.week <= week", "GroupStanding.week == week", 0),
    ("Q4", QRY, "GroupStanding.season == season, GroupStanding.week", "GroupStanding.season >= 0, GroupStanding.week", 0),
    ("Q4", QRY, '-entry["total"]', 'entry["total"]', 0),
    ("Q4", QRY, 'else float("inf")', "else 0", 0),
    ("Q4", QRY, 'entry["member"].casefold(), ', "", 0),
    ("Q4", QRY, 'if entry["points"] is not None]', "if True]", 0),
    ("Q4", QRY, 'entry["rank"] = row.rank', 'entry["rank"] = None', 0),
    ("Q4", QRY, 'entry["points"] = row.points', 'entry["points"] = entry["total"]', 0),
]


def nth(text: str, old: str, n: int) -> int:
    at = -1
    for _ in range(n + 1):
        at = text.index(old, at + 1)
    return at


def main() -> int:
    assert ":15445/" in os.environ["DATABASE_URL"], "lane database only"
    only = set(sys.argv[1:])
    survived = 0
    for number, (clause, path, old, new, n) in enumerate(MUTANTS, 1):
        if only and str(number) not in only:
            continue
        original = path.read_text()
        at = nth(original, old, n)
        path.write_text(original[:at] + new + original[at + len(old):])
        try:
            run = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
                                  "tests/test_group.py"], capture_output=True, text=True, timeout=600)
        finally:
            path.write_text(original)
        killed = run.returncode != 0
        survived += not killed
        change = f"{old[:60]!r} -> {new[:60]!r}" + (f" (occurrence {n + 1})" if n else "")
        print(f"{'KILLED  ' if killed else 'SURVIVED'} {number:3d} {clause:6s} {path.name}: {change}", flush=True)
    print(f"mutants {len(MUTANTS) if not only else len(only)}, survived {survived}")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
