"""Step 9 mutation pass: break each frozen clause once and show that test_scores.py goes red.

Run from backend/ with DATABASE_URL set to the lane's test database:
    uv run python ../docs/gauntlet/logs/step-9-evidence/s9-mutate.py
Each mutant is one text replacement in one module; the file is restored after every run.
"""

import subprocess
import sys
from pathlib import Path

SCORES = Path("nflpi/predictions/scores.py")
BACK = Path("nflpi/analytics/score_backtest.py")

LEAK_OLD = '''            past = history.get(team, [])[-games:] if games else []'''
LEAK_NEW = '''            past = (history.get(team, []) + ([(float(getattr(row, f"{side}_score")), 0.0)]
                    if pd.notna(row.home_score) else []))[-games:] if games else []'''

MUTANTS = [
    ("S1 home/road swapped", SCORES, "float((total_line + spread_line) / 2), float((total_line - spread_line) / 2)",
     "float((total_line - spread_line) / 2), float((total_line + spread_line) / 2)"),
    ("S1 zero total allowed", SCORES, "total_line <= 0", "total_line < 0"),
    ("S1 spread equal to total refused", SCORES, "abs(spread_line) > total_line", "abs(spread_line) >= total_line"),
    ("S1 spread larger than total allowed", SCORES, " or abs(spread_line) > total_line", ""),
    ("S1 non-finite spread allowed", SCORES, "not isfinite(spread_line) or ", ""),
    ("S1 non-finite total allowed", SCORES, "not isfinite(total_line) or ", ""),
    ("S2 banker's rounding", SCORES, "floor(points + 0.5)", "round(points)"),
    ("S2 rounds down", SCORES, "floor(points + 0.5)", "floor(points)"),
    ("S2 negative allowed", SCORES, "max(0, floor(points + 0.5))", "floor(points + 0.5)"),
    ("S3 wrong method name", SCORES, '"method": "line_implied"', '"method": "model"'),
    ("S3 home/away swapped", SCORES, "home, away = entry_pair(*implied)", "away, home = entry_pair(*implied)"),
    ("S3 answer rounds each side alone", SCORES, "home, away = entry_pair(*implied)",
     "home, away = entry(implied[0]), entry(implied[1])"),
    ("S2 pair rule on one half", SCORES, "home % 1 == 0.5 and away % 1 == 0.5", "home % 1 == 0.5 or away % 1 == 0.5"),
    ("S2 pair rule rounds both up", SCORES, "return entry(home), max(0, floor(away))", "return entry(home), entry(away)"),
    ("S2 pair rule rounds the home side down", SCORES, "return entry(home), max(0, floor(away))",
     "return floor(home), entry(away)"),
    ("S4 first n games, not last n", SCORES, "[-games:]", "[:games]"),
    ("S4 unfinished game counted", SCORES, 'row.status == "final" and pd.notna', "pd.notna"),
    ("S4 missing road score counted", SCORES, " and pd.notna(row.away_score)", ""),
    ("S4 points for and against swapped", SCORES, "history.setdefault(row.home_team, []).append((home, away))",
     "history.setdefault(row.home_team, []).append((away, home))"),
    ("S4 window is 8", SCORES, "FORM_GAMES = 16", "FORM_GAMES = 8"),
    ("S4 default window is 15", SCORES,
     "def scoring_form(df: pd.DataFrame, games: int = FORM_GAMES)",
     "def scoring_form(df: pd.DataFrame, games: int = 15)"),
    ("S4 add_score_features window is 8", SCORES, "scoring_form(out)", "scoring_form(out, games=8)"),
    ("S5 own result leaks into the form", SCORES, LEAK_OLD, LEAK_NEW),
    ("S6 implied home takes the road number", SCORES, 'out["implied_home"] = [pair[0]', 'out["implied_home"] = [pair[1]'),
    ("S6 missing line becomes zero", SCORES, "pair[1] if pair is not None else np.nan", "pair[1] if pair is not None else 0.0"),
    ("S6 blend loses a line column", SCORES, '["implied_home", "implied_away", *STATS_FEATURES]', '["implied_home", *STATS_FEATURES]'),
    ("S7 no intercept", SCORES, "np.ones(len(train))", "np.zeros(len(train))"),
    ("S7 unfinished rows fitted", SCORES, 'df.loc[df["status"] == "final"].dropna', "df.dropna"),
    ("S7 missing road score fitted", SCORES, '[*features, "home_score", "away_score"]', '[*features, "home_score"]'),
    ("S7 one row too few accepted", SCORES, "len(train) < len(features) + 1", "len(train) < len(features)"),
    ("S7 missing feature predicts zero", SCORES, "home = np.full(len(x), np.nan)", "home = np.zeros(len(x))"),
    ("S7 road model is the home model", SCORES, 'train["away_score"].to_numpy(dtype=float), rcond', 'train["home_score"].to_numpy(dtype=float), rcond'),
    ("S8 test season in the fit", BACK, "between(season - window, season - 1)", "between(season - window, season)"),
    ("S8 one season too many", BACK, "between(season - window, season - 1)", "between(season - window - 1, season - 1)"),
    ("S8 playoff games tested", BACK, ' & (frame["game_type"] == "REG")', ""),
    ("S8 unplayed games tested", BACK, '& (frame["status"] == "final")\n        & frame["home_score"].notna() & frame["away_score"].notna()', ""),
    ("S8 tuned Elo", BACK, "add_score_features(ordered, EloParams())", "add_score_features(ordered, EloParams(k=25.0))"),
    ("S8 window default 5", BACK, "window: int = 10", "window: int = 5"),
    ("S9 entries not rounded", BACK, "entry_pair(h, a) if np.isfinite(h)", "(h, a) if np.isfinite(h)"),
    ("S9 backtest rounds each side alone", BACK, "entry_pair(h, a) if np.isfinite(h)",
     "(max(0, int(h + 0.5)), max(0, int(a + 0.5))) if np.isfinite(h)"),
    ("S9 stats model reads the line", BACK, '"stats": ScoreModel.fit(train, STATS_FEATURES)', '"stats": ScoreModel.fit(train, BLEND_FEATURES)'),
    ("S10 team error not halved", BACK, "np.abs(away - actual_away)) / 2", "np.abs(away - actual_away))"),
    ("S10 total error is the sum of misses", BACK, "np.abs(home + away - actual_home - actual_away)", "np.abs(home - actual_home) + np.abs(away - actual_away)"),
    ("S10 team gain sign flipped", BACK, 'errors["implied"][0] - errors[candidate][0]', 'errors[candidate][0] - errors["implied"][0]'),
    ("S10 total gain sign flipped", BACK, 'errors["implied"][1] - errors[candidate][1]', 'errors[candidate][1] - errors["implied"][1]'),
    ("S10 total interval from team gains", BACK, "list(bootstrap_ci(total_gain))", "list(bootstrap_ci(team_gain))"),
    ("S10 empty team error is NaN", BACK, '"team_mae": float(team.mean()) if n else None', '"team_mae": float("nan")'),
    ("S10 empty interval is NaN", BACK, "team_ci = list(bootstrap_ci(team_gain)) if n else [None, None]", "team_ci = list(bootstrap_ci(team_gain))"),
    ("S11 zero gain wins", BACK, "team_ci[0] > 0 and", "team_ci[0] >= 0 and"),
    ("S11 mean gain is enough", BACK, "team_ci[0] > 0 and", "team_gain.mean() > 0 and"),
    ("S11 upper end is enough", BACK, "team_ci[0] > 0 and", "team_ci[1] > 0 and"),
    ("S11 equal total refused", BACK, "total_mean >= 0)", "total_mean > 0)"),
    ("S11 total points ignored", BACK, " and total_mean >= 0)", ")"),
    ("S11 total tolerance", BACK, "total_mean >= 0)", "total_mean >= -0.5)"),
    ("S11 minimum is 100 games", BACK, "MIN_SHIP_GAMES = 200", "MIN_SHIP_GAMES = 100"),
    ("S11 exactly the minimum refused", BACK, "n >= MIN_SHIP_GAMES and", "n > MIN_SHIP_GAMES and"),
    ("S11 no minimum", BACK, "n >= MIN_SHIP_GAMES and", "n and"),
    ("S10 missing values accepted", BACK, "if preds[required].isna().any().any():", "if False:"),
    ("S10 missing score accepted", BACK, '[*PRED_COLS, "home_score", "away_score"]', "[*PRED_COLS]"),
    ("S13 games not put in order", BACK, 'df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)', "df"),
    ("S13 empty season list accepted", BACK, "if not seasons or len(set(seasons)) != len(seasons):", "if len(set(seasons)) != len(seasons):"),
    ("S13 repeated season accepted", BACK, "if not seasons or len(set(seasons)) != len(seasons):", "if not seasons:"),
    ("S13 excluded count always zero", BACK, '"excluded": int(excluded)', '"excluded": 0'),
    ("S11 smaller gain picked", BACK, "return max(winners", "return min(winners"),
    ("S11 first winner picked", BACK,
     'max(winners, key=lambda row: row["team_mae_gain"])["candidate"]', 'winners[0]["candidate"]'),
    ("S11 decided on the tiebreak slots", BACK, '"ships": pick_winner(overall["comparisons"])', '"ships": pick_winner(summary(predictions.loc[slots])["comparisons"])'),
    ("S12 Sunday from 8 pm", BACK, ".hour >= 19", ".hour >= 20"),
    ("S12 Sunday after 7 pm only", BACK, ".hour >= 19", ".hour > 19"),
    ("S12 UTC hour", BACK, 'kickoff_utc.astimezone(ZoneInfo("America/New_York")).hour', "kickoff_utc.hour"),
    ("S12 Monday dropped", BACK, 'weekday == "Monday" or\n                (weekday', "(weekday"),
    ("S12 every Sunday game", BACK, ' and kickoff_utc.astimezone(ZoneInfo("America/New_York")).hour >= 19', ""),
    ("S13 slots are all games", BACK, '"tiebreak_slots": summary(predictions.loc[slots])', '"tiebreak_slots": summary(predictions)'),
    ("S13 season rows use every game", BACK, 'summary(predictions.loc[predictions["season"] == season])', "summary(predictions)"),
    ("S14 unpredicted games kept", BACK, "predictions = predictions.dropna(subset=PRED_COLS)", "pass"),
    ("S14 only line columns checked", BACK, "dropna(subset=PRED_COLS)", "dropna(subset=PRED_COLS[:2])"),
    ("S15 reads the environment", SCORES, "import numpy as np", "import os\nimport numpy as np\n_ = os.environ"),
    ("S15 pandas read_csv", SCORES, "import pandas as pd", "import pandas as pd\n_ = pd.read_csv"),
    ("S15 imports a database driver", SCORES, "import numpy as np", "import psycopg\nimport numpy as np"),
    ("S15 np.loadtxt", SCORES, "import numpy as np", "import numpy as np\n_ = np.loadtxt"),
    ("S15 pd.read_json", SCORES, "import pandas as pd", "import pandas as pd\n_ = pd.read_json"),
]


def main() -> int:
    survived = []
    for name, path, old, new in MUTANTS:
        original = path.read_text()
        if original.count(old) != 1:
            print(f"SKIPPED (text found {original.count(old)} times): {name}")
            survived.append(name)
            continue
        path.write_text(original.replace(old, new))
        try:
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "tests/test_scores.py"], capture_output=True)
        finally:
            path.write_text(original)
        caught = run.returncode != 0
        print(f"{'CAUGHT ' if caught else 'SURVIVED'}  {name}")
        if not caught:
            survived.append(name)
    print(f"{len(MUTANTS) - len(survived)} of {len(MUTANTS)} caught")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
