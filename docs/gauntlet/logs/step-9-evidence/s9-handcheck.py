"""Step 9 hand check: the line-implied numbers, counted with no project code (csv and math only).

Run:  python3 s9-handcheck.py <games.csv> <report.json>
Compares its own count with the `implied` rows of the report written by s9-backtest.py.
"""

import csv
import json
import math
import sys
from collections import defaultdict

SEASONS = {"2022", "2023", "2024", "2025"}
SHOW = ("2022_01_BUF_LA", "2023_18_BUF_MIA", "2024_10_MIA_LA")


def main(games_csv: str, report_json: str) -> int:
    team, total = defaultdict(list), defaultdict(list)
    slot_team, slot_total = [], []
    with open(games_csv, newline="") as f:
        for r in csv.DictReader(f):
            if r["season"] not in SEASONS or r["game_type"] != "REG" or r["home_score"] in ("", "NA"):
                continue
            spread, line_total = float(r["spread_line"]), float(r["total_line"])
            home, away = int(r["home_score"]), int(r["away_score"])
            pred_home = math.floor((line_total + spread) / 2 + 0.5)
            pred_away = math.floor((line_total - spread) / 2 + 0.5)
            team_miss = (abs(pred_home - home) + abs(pred_away - away)) / 2
            total_miss = abs(pred_home + pred_away - home - away)
            team[r["season"]].append(team_miss)
            total[r["season"]].append(total_miss)
            # gametime is US Eastern in this file
            if r["weekday"] == "Monday" or (r["weekday"] == "Sunday" and int(r["gametime"].split(":")[0]) >= 19):
                slot_team.append(team_miss)
                slot_total.append(total_miss)
            if r["game_id"] in SHOW:
                print(
                    f"{r['game_id']}: spread {spread:+g} total {line_total:g} -> line score {pred_home}-{pred_away}; "
                    f"final {home}-{away}; team miss {team_miss:g}; total miss {total_miss:g}"
                )

    def mean(xs: list) -> float:
        return sum(xs) / len(xs)

    all_team = [x for s in sorted(team) for x in team[s]]
    all_total = [x for s in sorted(total) for x in total[s]]
    report = json.load(open(report_json))
    line = next(m for m in report["methods"] if m["method"] == "implied")
    slot = next(m for m in report["tiebreak_slots"]["methods"] if m["method"] == "implied")
    checks = [
        ("games", len(all_team), report["games"]),
        ("team-score miss", mean(all_team), line["team_mae"]),
        ("total-points miss", mean(all_total), line["total_mae"]),
        ("slot games", len(slot_team), report["tiebreak_slots"]["games"]),
        ("slot team-score miss", mean(slot_team), slot["team_mae"]),
        ("slot total-points miss", mean(slot_total), slot["total_mae"]),
    ]
    for row in report["by_season"]:
        s = str(row["season"])
        checks += [
            (f"{s} games", len(team[s]), row["n"]),
            (f"{s} team-score miss", mean(team[s]), row["implied"]["team_mae"]),
            (f"{s} total-points miss", mean(total[s]), row["implied"]["total_mae"]),
        ]
    bad = 0
    for name, mine, theirs in checks:
        ok = abs(mine - theirs) < 1e-9
        bad += not ok
        print(f"{'MATCH' if ok else 'MISMATCH'}  {name}: hand {mine:.6f}  report {theirs:.6f}")
    print(f"{len(checks) - bad} of {len(checks)} MATCH")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
