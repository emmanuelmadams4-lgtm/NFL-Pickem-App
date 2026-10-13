"""Break each frozen clause on purpose and check that a test in tests/test_model.py fails.

Run from backend/ with the lane's test database, holding the machine's gate lock:
    DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15442/nflpi_red uv run python \
        ../docs/gauntlet/logs/step-14-evidence/s14-mutate.py
Each change is made in the working tree, tested, and undone. Exit code 1 if any change survives.
"""
# ruff: noqa: E501  (the strings below must match source lines exactly)

import subprocess
import sys
from pathlib import Path

M = "nflpi/analytics/metrics.py"
B = "nflpi/analytics/backtest.py"
F = "nflpi/predictions/features.py"
FIT = 'model = LogitModel.fit(pd.concat([train, played]).dropna(subset=["market_logit"]), BLEND_FEATURES)'
PLAYED = '& (f["kickoff_utc"] < games["kickoff_utc"].min())]'
SHIPS = "loss_ci[0] > 0 and accuracy_diff >= 0"
FINITE = "for values in (p_new, p_old, y)"
RATING = "home[0] / home[1] - away[0] / away[1] if home and away else np.nan"

MUTANTS = [  # clause, file, old, new
    ("S1", M, "return float(game_log_loss(p, y).mean())", "return float(game_log_loss(p, y).sum())"),
    ("S1", M, "return -(y * np.log(p) + (1 - y) * np.log(1 - p))", "return -(y * np.log(p))"),
    ("S2", M, "loss_diff = game_log_loss(p_old, y) - game_log_loss(p_new, y)",
     "loss_diff = game_log_loss(p_new, y) - game_log_loss(p_old, y)"),
    ("S2", M, "correct_diff = ((p_new > 0.5) == (y == 1)).astype(float) - ((p_old > 0.5) == (y == 1)).astype(float)",
     "correct_diff = ((p_old > 0.5) == (y == 1)).astype(float) - ((p_new > 0.5) == (y == 1)).astype(float)"),
    ("S2", M, "loss_ci = list(bootstrap_ci(loss_diff))",
     "loss_ci = [a - b for a, b in zip(bootstrap_ci(game_log_loss(p_old, y)), bootstrap_ci(game_log_loss(p_new, y)))]"),
    ("S2", M, '"accuracy_diff_ci": list(bootstrap_ci(correct_diff)),', '"accuracy_diff_ci": list(bootstrap_ci(loss_diff)),'),
    ("S2", M, 'accuracy_diff = float(correct_diff.mean())\n    return {\n        "n": int(len(y)),',
     'accuracy_diff = float(correct_diff.mean())\n    return {\n        "n": int(len(y)) + 1,'),
    ("S3", M, SHIPS, "loss_ci[1] > 0 and accuracy_diff >= 0"),
    ("S3", M, SHIPS, "float(loss_diff.mean()) > 0 and accuracy_diff >= 0"),
    ("S3", M, SHIPS, "loss_ci[0] > 0"),
    ("S3", M, SHIPS, "loss_ci[0] > 0 and accuracy_diff > 0"),
    ("S13", M, "if len(p_new) != len(p_old) or len(p_new) != len(y) or len(y) == 0:",
     "if len(p_new) != len(p_old) or len(p_new) != len(y):"),
    ("S13", M, "if len(p_new) != len(p_old) or len(p_new) != len(y) or len(y) == 0:", "if len(y) == 0:"),
    ("S13", M, FINITE, "for values in (p_new, p_old)"),
    ("S13", M, FINITE, "for values in (p_old, y)"),
    ("S13", M, FINITE, "for values in (p_new, y)"),
    ("S4", B, FIT, 'model = LogitModel.fit(train.dropna(subset=["market_logit"]), BLEND_FEATURES)'),
    ("S5", B, PLAYED, '& (f["kickoff_utc"] <= games["kickoff_utc"].min())]'),
    ("S5", B, PLAYED, '& (f["week"] < games["week"].iloc[0])]'),
    ("S5", B, PLAYED, '& (f["kickoff_utc"] <= games["kickoff_utc"].max())]'),
    ("S6", B, 'played = f[(f["season"] == season) & f["home_win"].notna()', 'played = f[f["home_win"].notna()'),
    ("S6", B, "train_seasons = list(range(season - window, season))",
     "train_seasons = list(range(season - window - 1, season))"),
    ("S7", B, "chosen = max(variants,", "chosen = min(variants,"),
    ("S7", B, 'key=lambda row: row["tune"]["log_loss_gain"]',
     'key=lambda row: paired_gain(confirm_rows[row["variant"]].to_numpy(), confirm_rows["p_blend"].to_numpy(), '
     'confirm_rows["home_win"].to_numpy())["log_loss_gain"]'),
    ("S7", B, '"ships": result["ships"]}', '"ships": variants[0]["tune"]["ships"]}'),
    ("S7", B, 'tune_rows = preds[preds["season"].isin(tune)]', "tune_rows = preds"),
    ("S7", B, 'confirm_rows = preds[preds["season"].isin(confirm)]', "confirm_rows = preds"),
    ("S8", B, 'return preds[preds["p_market"].notna()]', "return preds"),
    ("S8", B, 'test["p_inseason"] = inseason_blend(frames, season, window)',
     'test["p_inseason"] = inseason_blend(frames, season, 10)'),
    ("S11", B, '.fillna(test["p_blend"])', ""),
    ("S11", B, "_, train = _train_rows(frames, season, window)", "_, train = _train_rows(frames, season + 1, window + 1)"),
    ("S11", B, "[*BLEND_FEATURES, feature])", "[feature])"),
    ("S9", F, "(passing + rushing) / plays", "passing / plays"),
    ("S9", F, "plays = attempts + sacks + carries", "plays = attempts + carries"),
    ("S9", F, "first_epa - second_epa),", "first_epa),"),
    ("S9", F, "if len(sides) != 2 or", "if len(sides) > 2 or"),
    ("S9", F, "if plays == 0:", "if plays < 0:"),
    ("S9", F, 'if any(value in ("", "NA") for value in values):', 'if any(value in ("",) for value in values):'),
    ("S9", F, "if not all(math.isfinite(value) for value in (passing, rushing, attempts, sacks, carries)):", "if False:"),
    ("S10", F, "ratings[team] = (weighted * decay + net_epa, weight * decay + 1)",
     "ratings[team] = (weighted + net_epa, weight + 1)"),
    ("S10", F, "decay = 0.5 ** (1 / half_life)", "decay = 0.5**half_life"),
    ("S10", F, RATING, "home[0] / home[1] - away[0] / away[1] if home and away else 0.0"),
    ("S10", F, RATING, "away[0] / away[1] - home[0] / home[1] if home and away else np.nan"),
    ("S10", F, 'if not df["kickoff_utc"].is_monotonic_increasing:', "if False:"),
    # S10 "earlier games only": read the rating after this game's own EPA is added.
    ("S10", F, "        differences.append(" + RATING + ")\n", ""),
    ("S10", F, "            ratings[team] = (weighted * decay + net_epa, weight * decay + 1)\n",
     "            ratings[team] = (weighted * decay + net_epa, weight * decay + 1)\n"
     "        home, away = ratings.get(row.home_team), ratings.get(row.away_team)\n"
     "        differences.append(" + RATING + ")\n"),
]
# The last two entries are one change in two parts: apply them together.
PAIRS = {len(MUTANTS) - 2: len(MUTANTS) - 1}
TESTS = ["uv", "run", "pytest", "-q", "-x", "--color=no", "tests/test_model.py",
         "-k", "not predictions_are_valid and not qb_change_creates and not backfill"]


def run(changes: list[tuple[str, str, str]]) -> bool:
    """Apply the changes, run the tests, undo. True when a test failed (the change was caught)."""
    originals = {path: Path(path).read_text() for path, _, _ in changes}
    try:
        for path, old, new in changes:
            text = Path(path).read_text()
            if text.count(old) != 1:
                raise SystemExit(f"cannot apply: {old!r} appears {text.count(old)} times in {path}")
            Path(path).write_text(text.replace(old, new))
        return subprocess.run(TESTS, capture_output=True).returncode != 0
    finally:
        for path, text in originals.items():
            Path(path).write_text(text)


clean = subprocess.run(TESTS, capture_output=True)
if clean.returncode != 0:
    raise SystemExit("the unchanged code does not pass: fix that first")
survived = 0
skip = set(PAIRS.values())
for i, (clause, path, old, new) in enumerate(MUTANTS):
    if i in skip:
        continue
    changes = [(path, old, new)]
    if i in PAIRS:
        changes.append(MUTANTS[PAIRS[i]][1:])
    caught = run(changes)
    survived += not caught
    print(f"{'CAUGHT  ' if caught else 'SURVIVED'} {clause:4} {path.split('/')[-1]:12} {old.strip()[:60]!r} -> {new.strip()[:50]!r}", flush=True)
total = len(MUTANTS) - len(skip)
print(f"{total - survived} of {total} caught")
sys.exit(1 if survived else 0)
