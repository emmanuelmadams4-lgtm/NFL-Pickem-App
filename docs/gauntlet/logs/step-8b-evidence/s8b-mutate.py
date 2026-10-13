"""Break each frozen step 8b clause on purpose and check that a test in tests/test_star_backtest.py fails.

Run from backend/ with the lane's test database, holding the machine's gate lock:
    DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_test uv run python \
        ../docs/gauntlet/logs/step-8b-evidence/s8b-mutate.py
Each change is made in the working tree, tested, and undone. Exit code 1 if any change survives.
Never commit while this runs; if it is killed, `git checkout backend/nflpi/analytics/star_backtest.py`.
Not mutated: F8 and P5 have no line of their own (the functions take no result as input); they are pinned by the
bare-frame test, the score-flip tests, and the F1 and P3 mutants that feed the game's own season in.
X1 (nothing existing changes) is checked by `git diff --stat a71e112 -- backend/nflpi backend/tests` and lane-guard.
"""
# ruff: noqa: E501  (the strings below must match source lines exactly)

import subprocess
import sys
from pathlib import Path

S = "nflpi/analytics/star_backtest.py"
TESTS = ["uv", "run", "pytest", "-q", "-x", "tests/test_star_backtest.py"]
REPORT_KEY = 'indexed.setdefault((*season_week, row["team"]), []).append(row)'
ROSTER_KEY = 'indexed.setdefault((*season_week, row["team"]), set()).add(row["player_id"])'
GROUP = 'group = "qb" if player["position"] == "QB" else "off" if off >= defense else "def"'
GUARD = '(row["modified"] is None or row["modified"] < kickoff)'
ROSTER_KNOWN = "if game.season < ROSTER_FIRST_SEASON or season_week not in roster_weeks:"
CLUB_OUT = '''    return {row["player_id"] for row in reports if (row["status"] or "").lower() in REPORT_OUT
            and (row["modified"] is None or row["modified"] < kickoff)}'''
RESERVE = "result += [h - a for h, a in zip(reserve_home[:2], reserve_away[:2], strict=True)]"
FEW = 'if rows["season"].nunique() < MIN_FIT_SEASONS:'

MUTANTS = [  # clause, old, new
    ("L1", 'if row["season_type"] != "REG":', "if False:"),
    ("L1", 'row["season"]: {} for row in stats if row["season_type"] == "REG"', 'row["season"]: {} for row in stats'),
    ("L1", 'season, pid = row["season"], row["player_id"]', 'season, pid = max(r["season"] for r in stats), row["player_id"]'),
    ("L1", 'player["totals"][name] += row[name]', 'player["totals"][name] = row[name]'),
    ("L2", 'if row["week"] > player["week"]:', 'if player["week"] < 0:'),
    ("L2", GROUP, 'group = "off" if off >= defense else "def"'),
    ("L2", GROUP, 'group = "qb" if player["position"] == "QB" else "off" if off > defense else "def"'),
    ("L2", GROUP, 'group = "qb" if player["position"] == "QB" else "def" if off >= defense else "off"'),
    ("L2", 'score = totals["attempts"] if group == "qb" else', 'score = off if group == "qb" else'),
    ("L2", '"rushing_yards": 0.1,', '"rushing_yards": 0.2,'),
    ("L2", '"receiving_yards": 0.1,', '"receiving_yards": 0.2,'),
    ("L2", '"rushing_tds": 6,', '"rushing_tds": 4,'),
    ("L2", '"receiving_tds": 6,', '"receiving_tds": 4,'),
    ("L2", '"receptions": 0.5}', '"receptions": 1}'),
    ("L2", '"def_tackles_solo": 1,', '"def_tackles_solo": 2,'),
    ("L2", '"def_tackles_with_assist": 1,', '"def_tackles_with_assist": 2,'),
    ("L2", '"def_tackle_assists": 0.5,', '"def_tackle_assists": 1,'),
    ("L2", '"def_sacks": 6,', '"def_sacks": 4,'),
    ("L2", '"def_qb_hits": 2,', '"def_qb_hits": 1,'),
    ("L2", '"def_tackles_for_loss": 2,', '"def_tackles_for_loss": 1,'),
    ("L2", '"def_interceptions": 6,', '"def_interceptions": 4,'),
    ("L2", '"def_pass_defended": 3,', '"def_pass_defended": 2,'),
    ("L2", '"def_fumbles_forced": 4,', '"def_fumbles_forced": 3,'),
    ("L2", '"def_tds": 6,', '"def_tds": 4,'),
    ("L2", '"def_safeties": 2}', '"def_safeties": 1}'),
    ("L3", 'STAR_LIMITS = {"qb": 32, "off": 64, "def": 64}', 'STAR_LIMITS = {"qb": 32, "off": 64, "def": 32}'),
    ("L3", "[:STAR_LIMITS[group]]", '[:STAR_LIMITS["qb"]]'),
    ("L3", "if score > 0:", "if score >= 0:"),
    ("L3", "key=lambda item: (-item[1], item[0])", "key=lambda item: -item[1]"),
    ("L3", "key=lambda item: (-item[1], item[0])", "key=lambda item: (item[1], item[0])"),
    ("L3", "(group, score / mean) for pid, score in chosen", "(group, score) for pid, score in chosen"),
    ("L3", "mean = sum(score for _, score in chosen) / len(chosen)", "mean = max(score for _, score in chosen)"),
    ("F1", "stars_by_season.get(game.season - 1)", "stars_by_season.get(game.season)"),
    ("F1", "stars_by_season.get(game.season - 1)", "stars_by_season.get(game.season - 2)"),
    ("F1", "stars_by_season.get(game.season - 1)", "stars_by_season.get(game.season - 1, {})"),
    ("F2", '(row["status"] or "").lower() in REPORT_OUT', '(row["status"] or "") in REPORT_OUT'),
    ("F2", 'REPORT_OUT = frozenset({"out", "doubtful"})', 'REPORT_OUT = frozenset({"out", "doubtful", "questionable"})'),
    ("F2", 'REPORT_OUT = frozenset({"out", "doubtful"})', 'REPORT_OUT = frozenset({"out"})'),
    ("F2", REPORT_KEY, '[indexed.setdefault((row["season"], w, row["team"]), []).append(row) for w in range(1, 23)]'),
    ("F2", REPORT_KEY, '[indexed.setdefault((s, row["week"], row["team"]), []).append(row) for s in (row["season"], row["season"] + 1)]'),
    ("F2", REPORT_KEY, '[indexed.setdefault((*season_week, t), []).append(row) for t in ("BUF", "MIA", "NE", "NYJ", "KC", "LV")]'),
    ("F2", "found = [stars[pid] for pid in sorted(ids) if pid in stars]", "found = [stars[pid] for pid in sorted(ids) if pid in stars or stars.setdefault(pid, ('off', 1.0))]"),
    ("F2", CLUB_OUT, CLUB_OUT.replace("return {", "return _Bag(").replace("kickoff)}", "kickoff))")),
    ("F3", GUARD, '(row["modified"] is None or row["modified"] <= kickoff)'),
    ("F3", GUARD, "True"),
    ("F3", GUARD, '(row["modified"] is not None and row["modified"] < kickoff)'),
    ("F4", 'float(sum(group != "qb" for group, _ in found)),', "float(len(found)),"),
    ("F4", 'float(sum(weight for group, weight in found if group != "qb")),', "float(sum(weight for group, weight in found)),"),
    ("F4", 'float(sum(group == "qb" for group, _ in found)))', "0.0)"),
    ("F5", "result = [h - a for h, a in zip(", "result = [a - h for h, a in zip("),
    ("F5", 'float(sum(weight for group, weight in found if group != "qb")),', 'float(sum(1.0 for group, weight in found if group != "qb")),'),
    ("F6", "if stars is None or season_week not in report_weeks:", "if stars is None:"),
    ("F7", 'if row["status"] in ROSTER_OUT:', "if True:"),
    ("F7", 'ROSTER_OUT = frozenset({"RES", "PUP", "SUS"})', 'ROSTER_OUT = frozenset({"RES", "PUP"})'),
    ("F7", 'ROSTER_OUT = frozenset({"RES", "PUP", "SUS"})', 'ROSTER_OUT = frozenset({"RES", "PUP", "SUS", "INA"})'),
    ("F7", "ROSTER_FIRST_SEASON = 2016", "ROSTER_FIRST_SEASON = 2015"),
    ("F7", ROSTER_KNOWN, "if season_week not in roster_weeks:"),
    ("F7", ROSTER_KNOWN, "if game.season < ROSTER_FIRST_SEASON:"),
    ("F7", "_counts(home | roster_rows.get(home_key, set()), stars)", "_counts(roster_rows.get(home_key, set()), stars)"),
    ("F7", "_counts(home | roster_rows.get(home_key, set()), stars)", "_counts(list(home) + list(roster_rows.get(home_key, set())), stars)"),
    ("F7", "_counts(away | roster_rows.get(away_key, set()), stars)", "_counts(roster_rows.get(away_key, set()), stars)"),
    ("F7", RESERVE, RESERVE.replace("reserve_home[:2], reserve_away[:2]", "reserve_home[1:], reserve_away[1:]")),
    ("F7", RESERVE, RESERVE.replace("[h - a", "[a - h")),
    ("F7", ROSTER_KEY, '[indexed.setdefault((row["season"], w, row["team"]), set()).add(row["player_id"]) for w in range(1, 23)]'),
    ("F7", ROSTER_KEY, '[indexed.setdefault((s, row["week"], row["team"]), set()).add(row["player_id"]) for s in (row["season"], row["season"] + 1)]'),
    ("F7", ROSTER_KEY, '[indexed.setdefault((*season_week, t), set()).add(row["player_id"]) for t in ("BUF", "MIA", "NE", "NYJ", "KC", "LV")]'),
    ("F7", "if roster is not None:\n        columns +=", "if True:\n        columns +="),
    ("P1", "return _market_games(by_season)", "return pd.concat(by_season, ignore_index=True)"),
    ("P2", '"p_star_count_qb": ["star_out_diff", "qb_out_diff"],', '"p_star_count_qb": ["star_out_diff"],'),
    ("P2", "LogitModel.fit(rows, [*BLEND_FEATURES, *extra])", "LogitModel.fit(rows, [*BLEND_FEATURES, extra[0]])"),
    ("P3", "_, train = _train_rows(frames, season, window)", "_, train = _train_rows(frames, season, window + 1)"),
    ("P3", "_, train = _train_rows(frames, season, window)", "_, train = _train_rows(frames, season + 1, window)"),
    ("P3", 'train = train.dropna(subset=["market_logit"])', "train = train.copy()"),
    ("P3", "rows = train.dropna(subset=extra)", "rows = train"),
    ("P4", FEW, 'if rows["season"].nunique() <= MIN_FIT_SEASONS:'),
    ("P4", FEW, "if rows.empty:"),
    ("P4", "MIN_FIT_SEASONS = 3", "MIN_FIT_SEASONS = 2"),
    ("P4", 'test[name] = test["p_blend"]', "test[name] = 0.5"),
    ("P4", "test[name] = _predict_or_blend(model, test)", "test[name] = model.predict(test)"),
]
BAG = "\n\nclass _Bag(list):  # a list that still takes `|`, so a player can be counted twice\n    def __or__(self, other):\n        return _Bag([*self, *other])\n"


def run(old: str, new: str) -> bool:
    """Apply one change, run the tests, undo it. True when a test failed."""
    path = Path(S)
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"cannot apply: {old!r} appears {text.count(old)} times")
    try:
        path.write_text(text.replace(old, new) + (BAG if "_Bag(" in new else ""))
        return subprocess.run(TESTS, capture_output=True).returncode != 0
    finally:
        path.write_text(text)


if subprocess.run(TESTS, capture_output=True).returncode != 0:
    raise SystemExit("the unchanged code does not pass: fix that first")
survived = 0
for clause, old, new in MUTANTS:
    caught = run(old, new)
    survived += not caught
    print(f"{'CAUGHT  ' if caught else 'SURVIVED'} {clause:3} {old.strip()[:62]!r} -> {new.strip()[:56]!r}", flush=True)
print(f"{len(MUTANTS) - survived} of {len(MUTANTS)} caught")
sys.exit(1 if survived else 0)
