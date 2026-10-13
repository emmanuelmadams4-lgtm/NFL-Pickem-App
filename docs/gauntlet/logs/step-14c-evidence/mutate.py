"""Step 14c mutation sweep: break each frozen clause in model_c.py one way at a time; a test must fail.

Run from backend/ (needs DATABASE_URL and the gate lock):  uv run python ../docs/gauntlet/logs/step-14c-evidence/mutate.py
Prints CAUGHT or SURVIVED per mutant; the file is restored after each one and at the end.
"""

import subprocess
import sys
from pathlib import Path

TARGET = Path("nflpi/analytics/model_c.py")
M = [  # (clause, old text, new text)
    ("T1", "TREE_LEARNING_RATE = 0.05", "TREE_LEARNING_RATE = 0.1"),
    ("T1", "TREE_MAX_ITER = 300", "TREE_MAX_ITER = 200"),
    ("T1", "TREE_GRID = ((2, 30), (2, 80), (3, 30), (3, 80))", "TREE_GRID = ((2, 30), (2, 80), (3, 30), (4, 80))"),
    ("T1", '"temp_f", "wind_mph",\n             "div_flag"]', '"temp_f", "wind_mph"]'),
    ("T1", '"core": BLEND_FEATURES,', '"core": BLEND_FEATURES[:-1],'),
    ("T2", '"closed": 1.0', '"closed": 0.0'),
    ("T2", 'out["div_flag"] = out["div_game"].fillna(False).astype(bool).astype(float)', 'out["div_flag"] = 1.0'),
    ("T2", "out = frame.copy()", "out = frame"),
    ("T3", 'rows[rows["season"] < last]', 'rows[rows["season"] <= last]'),
    ("T3", "n_iter = int(np.argmin(losses)) + 1", "n_iter = TREE_MAX_ITER"),
    ("T3", 'cls._classifier(depth, leaf, n_iter).fit(rows[features], rows["home_win"])',
     'cls._classifier(depth, leaf, n_iter).fit(fit[features], fit["home_win"])'),
    ("T3", 'held = rows[rows["season"] == last]', 'held = rows[rows["season"] == rows["season"].min()]'),
    ("T3", 'rows = train[train["home_win"].notna()]', "rows = train"),
    ("T4", "test = backtest.predict_season(frames, season, window)\n        _, train = backtest._train_rows(frames, season, window)\n        train = train.dropna(subset=[\"market_logit\"])\n        for set_name",
     "test = backtest.predict_season(frames, season, window)\n        _, train = backtest._train_rows(frames, season, window + 1)\n        train = train.dropna(subset=[\"market_logit\"])\n        for set_name"),
    ("T4", "frames = backtest._elo_frames(tree_inputs(df))", "frames = backtest._elo_frames(df.assign(roof_indoor=0.0, div_flag=0.0))"),
    ("S1", "+ STACK_TIE_PENALTY * w", "- STACK_TIE_PENALTY * w"),
    ("S1", "STACK_GRID = tuple(round(0.05 * i, 2) for i in range(21))", "STACK_GRID = tuple(round(0.05 * i, 2) for i in range(20))"),
    ("S2", '(preds["season"] < season) & preds[tree_col]', '(preds["season"] <= season) & preds[tree_col]'),
    ("S2", "(1 - w) * current[\"p_blend\"] + w * current[tree_col]", "w * current[\"p_blend\"] + (1 - w) * current[tree_col]"),
    ("G1", "math.sqrt(2)", "1.0"),
    ("G1", "or sigma <= 0", "or sigma < 0"),
    ("G2", "ScoreModel.fit(train[~held], features)", "ScoreModel.fit(train, features)"),
    ("G2", "miss[np.isfinite(miss)]", "miss"),
    ("G3", "MARGIN_SCALE = 7", "MARGIN_SCALE = 14"),
    ("G3", "TOTAL_CENTER = 45", "TOTAL_CENTER = 40"),
    ("G3", "home, away = ScoreModel.fit(train, features).predict(test)", "home, away = ScoreModel.fit(test, features).predict(test)"),
    ("G3", "sigma = _miss_sigma(train, *folds[name])", "sigma = 13.0"),
    ("G3", 'chance.fillna(test["p_blend"])', "chance.fillna(0.5)"),
    ("G3", "f(*folds[source[c]])", 'f(*folds["stats"])'),
    ("E1", "explosive / plays - opp_explosive / opp_plays", "explosive / plays"),
    ("E1", "if len(sides) != 2 or sides[0][1] == sides[1][1]:\n            continue\n        if any(plays <= 0",
     "if len(sides) != 2:\n            continue\n        if any(plays <= 0"),
    ("E2", "EXPLOSIVE_SCALE = 50", "EXPLOSIVE_SCALE = 20"),
    ("E2", "EXPLOSIVE_HALF_LIVES = (4, 8, 16)", "EXPLOSIVE_HALF_LIVES = (4, 8, 12)"),
    ("P1", "range(len(ids), 0, -1)", "range(1, len(ids) + 1)"),
    ("P1", '(week["p_blend"] > 0.5)', '(week["p_blend"] >= 0.5)'),
    ("P1", 'ascending=[False, True]', 'ascending=[False, False]'),
    ("P1", "return by_sort[::-1]", "return by_sort"),
    ("P1", "raise ValueError(f\"unknown points order: {order}\")", "return by_sort if False else week[\"game_id\"].tolist()"),
    ("P3", "            i += 2\n", "            i += 1\n"),
    ("P3", "if gap < TIE_BAND:", "if gap < 2 * TIE_BAND:"),
    ("P4", 'r["sort"]["actual"] - r[name]["actual"]', 'r[name]["actual"] - r["sort"]["actual"]'),
    ("C1", '"gap": tune_gain - confirm_gain', '"gap": confirm_gain - tune_gain'),
    ("C1", "results = backtest.evaluate(preds, candidates, tune, confirm, cluster)", "results = backtest.evaluate(preds, candidates, tune, confirm)"),
]


def passes() -> bool:
    out = subprocess.run(["uv", "run", "pytest", "-x", "-q", "tests/test_model_c.py"], capture_output=True, text=True)
    return out.returncode == 0


def main() -> int:
    original = TARGET.read_text()
    survived = 0
    try:
        for clause, old, new in M:
            if original.count(old) != 1:
                print(f"SKIPPED  {clause}  (text not found once): {old[:60]!r}")
                survived += 1
                continue
            TARGET.write_text(original.replace(old, new))
            caught = not passes()
            survived += not caught
            print(f"{'CAUGHT  ' if caught else 'SURVIVED'} {clause}  {old[:60]!r} -> {new[:40]!r}", flush=True)
    finally:
        TARGET.write_text(original)
    print(f"{len(M) - survived} of {len(M)} caught")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
