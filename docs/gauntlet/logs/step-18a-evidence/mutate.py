"""Mutation check for tests/test_model_audit.py: each planted defect must make at least one test fail.

Run from backend/ with DATABASE_URL pointing at the test database.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

TEST_CMD = ["uv", "run", "pytest", "-q", "tests/test_model_audit.py", "-p", "no:cacheprovider", "--color=no"]

MUTATIONS = {
    "M1 own score leaks into a feature": (
        "nflpi/predictions/features.py",
        'out["elo_diff"] = (out["home_elo"] - out["away_elo"]) / 100',
        'out["elo_diff"] = (out["home_elo"] - out["away_elo"]) / 100 + out["home_score"].fillna(0) / 1000',
    ),
    "M2 live path ignores the market": (
        "nflpi/predictions/engine.py",
        "        prob = model.predict_one(row)",
        "        prob = base_p",
    ),
    "M3 the fit sees the test season": (
        "nflpi/analytics/backtest.py",
        "train_seasons = list(range(season - window, season))",
        "train_seasons = list(range(season - window, season + 1))",
    ),
    "M4 the home rate is taken from the test games": (
        "nflpi/analytics/backtest.py",
        'home_rate = train.loc[train["home_field"] == 1, "home_win"].mean()',
        'home_rate = test.loc[test["home_field"] == 1, "home_win"].mean()',
    ),
    "M5 the job trains through the current season": (
        "nflpi/jobs.py",
        "return engine.train(session, through_season=season - 1)",
        "return engine.train(session, through_season=season)",
    ),
    "M7 own score leaks into the bench's own copy of the feature": (
        "nflpi/analytics/backtest.py",
        'f["elo_diff"] = (f["home_elo"] - f["away_elo"]) / 100',
        'f["elo_diff"] = (f["home_elo"] - f["away_elo"]) / 100 + f["home_score"].fillna(0) / 1000',
    ),
    "M8 every line is labelled closing": (
        "nflpi/ingestion/service.py",
        'kind = "closing" if g["status"] == "final" else "latest"',
        'kind = "closing"',
    ),
    "M9 the live fit window reaches into the season it predicts": (
        "nflpi/predictions/engine.py",
        "seasons = list(range(through_season - settings.train_window_seasons + 1, through_season + 1))",
        "seasons = list(range(through_season - settings.train_window_seasons + 2, through_season + 2))",
    ),
    "M10 the game's total points leak into a feature on both paths": (
        "nflpi/predictions/features.py",
        'out["home_field"] = (~out["neutral_site"].astype(bool)).astype(float)',
        'out["home_field"] = (~out["neutral_site"].astype(bool)).astype(float)'
        ' + (out["home_score"].fillna(0) + out["away_score"].fillna(0)) / 1000',
    ),
    "M6 live features differ from the bench": (
        "nflpi/predictions/engine.py",
        '    f = add_features(load_frame(session), EloParams(**p["elo"]))',
        "    f = add_features(load_frame(session), EloParams(k=40.0, hfa=0.0))",
    ),
}


def run_tests() -> tuple[int, list[str]]:
    done = subprocess.run(TEST_CMD, capture_output=True, text=True, env=os.environ.copy())
    failed = [line.split()[1] for line in done.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
    return done.returncode, failed


def mutate(path: str, old: str, new: str) -> dict:
    file = Path(path)
    original = file.read_bytes()
    text = original.decode()
    if text.count(old) != 1:
        return {"status": "not-applied", "occurrences": text.count(old), "failed_tests": []}
    try:
        file.write_bytes(text.replace(old, new).encode())
        code, failed = run_tests()
    finally:
        file.write_bytes(original)
    return {"status": "KILLED" if failed else "SURVIVED", "exit_code": code, "failed_tests": failed}


def main() -> int:
    try:
        url = make_url(os.environ.get("DATABASE_URL", ""))
    except ArgumentError:
        url = None
    if url is None or not (url.database or "").endswith("_test") or url.port in (None, 5432):
        print("refusing to run: DATABASE_URL must name a database ending in _test on an explicit port other "
              "than 5432", file=sys.stderr)
        return 2
    if subprocess.run(["git", "diff", "--quiet", "--", "nflpi"]).returncode != 0:
        print("refusing to run: git diff -- nflpi is not clean; commit or revert those edits first", file=sys.stderr)
        return 2
    code, failed = run_tests()
    if code != 0:
        print(f"unmutated tests failed (exit {code}): {failed}", file=sys.stderr)
        return 1
    results = {}
    for name, (path, old, new) in MUTATIONS.items():
        results[name] = {"file": path, **mutate(path, old, new)}
        print(f"{results[name]['status']} {name}: {', '.join(results[name]['failed_tests'])}")
    changed = subprocess.run(["git", "diff", "--quiet", "--", "nflpi"]).returncode != 0
    ok = all(r["status"] == "KILLED" for r in results.values()) and not changed
    print(json.dumps({"results": results, "files_left_changed": changed, "ok": ok}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
