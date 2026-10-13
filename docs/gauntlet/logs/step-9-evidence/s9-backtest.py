"""Step 9 real-data run: score methods on 2022 to 2025, walk-forward.

Run from backend/:  uv run python ../docs/gauntlet/logs/step-9-evidence/s9-backtest.py <games.csv> <report.json>
<games.csv> is the nflverse schedule file (schedules/games.csv). Prints the table and writes the full report.
"""

import csv
import json
import sys

from nflpi.analytics.score_backtest import run_score_backtest
from nflpi.ingestion import nflverse
from nflpi.predictions.features import games_frame

SEASONS = list(range(2022, 2026))


def main(games_csv: str, report_json: str) -> None:
    with open(games_csv, newline="") as f:
        games = nflverse.parse_games(list(csv.DictReader(f)), 2002)
    for g in games:
        g["home_ml"], g["away_ml"] = g.pop("_home_ml"), g.pop("_away_ml")
        g["spread_line"], g["total_line"] = g.pop("_spread"), g.pop("_total")
    report = run_score_backtest(games_frame(games), SEASONS)
    with open(report_json, "w") as f:
        json.dump(report, f, indent=1)

    for title, part in (("ALL REGULAR-SEASON GAMES", report), ("SUNDAY NIGHT + MONDAY GAMES (reported only)", report["tiebreak_slots"])):
        print(f"\n{title}: {part['games']} games, seasons {SEASONS[0]}-{SEASONS[-1]}")
        for m in part["methods"]:
            print(f"  {m['method']:8s} team-score miss {m['team_mae']:.3f}   total-points miss {m['total_mae']:.3f}   {m['label']}")
        for c in part["comparisons"]:
            print(
                f"  {c['candidate']:8s} vs line: team gain {c['team_mae_gain']:+.3f} "
                f"(95% {c['team_ci'][0]:+.3f} to {c['team_ci'][1]:+.3f})   total gain {c['total_mae_gain']:+.3f} "
                f"(95% {c['total_ci'][0]:+.3f} to {c['total_ci'][1]:+.3f})   wins={c['wins']}"
            )
    print("\nBY SEASON (team-score miss / total-points miss)")
    for row in report["by_season"]:
        cells = "   ".join(f"{m} {row[m]['team_mae']:.3f}/{row[m]['total_mae']:.3f}" for m in ("implied", "stats", "blend"))
        print(f"  {row['season']} n={row['n']}   {cells}")
    print(f"\nSHIPS: {report['ships']}   (None = the line-implied score stays the answer)")
    print("Positive gain = the candidate was closer than the line. Two candidates, one benchmark, no correction.")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
