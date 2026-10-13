"""Break each frozen step 14b clause on purpose and check that a test in tests/test_model.py fails.

Run from backend/ with the lane's test database, holding the machine's gate lock:
    DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_red uv run python \
        ../docs/gauntlet/logs/step-14b-evidence/s14b-mutate.py
Each change is made in the working tree, tested, and undone. Exit code 1 if any change survives.
Not mutated, because the change cannot be seen from outside (NumPy raises the same ValueError one line later):
the two `len(clusters)` checks, and the non-finite half of the weights check (scikit-learn refuses a NaN weight
with the same ValueError; that mutant survived the first sweep for this reason and was removed).
Not mutated: `if h + a == 1: return h` (every formula returns h there anyway).
"""
# ruff: noqa: E501  (the strings below must match source lines exactly)

import subprocess
import sys
from pathlib import Path

M = "nflpi/analytics/metrics.py"
B = "nflpi/analytics/backtest.py"
F = "nflpi/predictions/features.py"
K = "nflpi/predictions/market.py"
L = "nflpi/predictions/model.py"
SHIPS_CLUSTER = '"ships_cluster": bool(cluster_ci[0] > 0 and accuracy_diff >= 0),'
WEIGHTS = 'weights = 0.5 ** ((season - 1 - train["season"]) / h)'

MUTANTS = [  # clause, file, old, new
    ("B1", M, "means = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)", "means = (sums / counts)[idx].mean(axis=1)"),
    ("B1", M, "idx = rng.integers(0, n_clusters, size=(reps, n_clusters))", "idx = rng.integers(0, n_clusters, size=(reps, len(values)))"),
    ("B1", M, "sums = np.bincount(inverse, weights=values)", "sums = np.bincount(np.arange(len(values)) % n_clusters, weights=values)"),
    ("B2", M, "if clusters is not None:\n        cluster_ci", "if True:\n        cluster_ci"),
    ("B2", M, "cluster_ci = list(bootstrap_ci(loss_diff, clusters=clusters))", "cluster_ci = list(bootstrap_ci(loss_diff))"),
    ("B2", M, '"accuracy_diff_ci_cluster": list(bootstrap_ci(correct_diff, clusters=clusters)),', '"accuracy_diff_ci_cluster": list(bootstrap_ci(loss_diff, clusters=clusters)),'),
    ("B2", M, SHIPS_CLUSTER, '"ships_cluster": bool(cluster_ci[0] > 0),'),
    ("B2", M, SHIPS_CLUSTER, '"ships_cluster": bool(loss_ci[0] > 0 and accuracy_diff >= 0),'),
    ("B2", M, SHIPS_CLUSTER, '"ships_cluster": bool(cluster_ci[1] > 0 and accuracy_diff >= 0),'),
    ("B3", B, 'tune_rows["home_win"].to_numpy(), clusters=tune_clusters)}', 'tune_rows["home_win"].to_numpy())}'),
    ("B3", B, 'confirm_rows["home_win"].to_numpy(), clusters=confirm_clusters)', 'confirm_rows["home_win"].to_numpy())'),
    ("B3", B, "confirm_clusters = confirm_rows.groupby(cluster, sort=True)", "confirm_clusters = confirm_rows.groupby(cluster[:1], sort=True)"),
    ("B3", B, '"ships": result["ships"]})', '"ships": result.get("ships_cluster", result["ships"])})'),
    ("B4", B, "if set(tune) & set(confirm):", "if False:"),
    ("D1", K, "return novig_home_prob(home_ml, away_ml)\n    if method", "return h\n    if method"),
    ("D1", K, "return h - (h + a - 1) / 2", "return h - (h + a - 1)"),
    ("D1", K, "if h**mid + a**mid > 1:", "if h**mid + a**mid < 1:"),
    ("D1", K, "c = math.sqrt(h / (1 - h) * a / (1 - a))", "c = h / (1 - h) * a / (1 - a)"),
    ("D1", K, "z = ((b - 1) * (d * d - b)) / (b * (d * d - 1))", "z = (b - 1) / b"),
    ("D2", K, 'raise ValueError(f"unknown devig method: {method}")', "return None"),
    ("D2", K, "        return None\n    h, a = implied_prob(home_ml), implied_prob(away_ml)\n    if h + a == 1:",
     "        return 0.5\n    h, a = implied_prob(home_ml), implied_prob(away_ml)\n    if h + a == 1:"),
    ("D3", F, "devig_home_prob(h, a, method) if not", 'devig_home_prob(h, a, "multiplicative") if not'),
    ("D3", F, "], index=df.index, dtype=float).clip(0.01, 0.99)", "], index=df.index, dtype=float).clip(0.0001, 0.9999)"),
    ("D3", F, "devig_home_prob(h, a, method) if not (pd.isna(h) or pd.isna(a)) else np.nan", "devig_home_prob(h, a, method) if not (pd.isna(h) or pd.isna(a)) else 0.5"),
    ("R1", L, "sample_weight=weights.loc[train.index] if weights is not None else None)", "sample_weight=None)"),
    ("R1", L, "if weights is not None and (not np.isfinite(weights).all() or (weights < 0).any()):", "if weights is not None and not np.isfinite(weights).all():"),
    ("V1", B, 'return preds[preds["p_market"].notna()]', "return preds"),
    ("V2", B, "train_seasons = list(range(season - window, season))", "train_seasons = list(range(season - window, season + 1))"),
    ("V3", B, 'model = LogitModel.fit(train, [f"market_logit_{method}", *BASE_FEATURES])', 'model = LogitModel.fit(train, ["market_logit", *BASE_FEATURES])'),
    ("V3", B, "for method in DEVIG_METHODS[1:]}", 'for method in DEVIG_METHODS[1:] for df in [df.assign(away_ml=df["home_ml"], home_ml=df["away_ml"])]}'),
    ("V4", B, '"spread_pts": df["spread_line"] / SPREAD_SCALE,', '"spread_pts": df["spread_line"],'),
    ("V4", B, '"total_pts": (df["total_line"] - TOTAL_CENTER) / TOTAL_SCALE,', '"total_pts": df["total_line"] / TOTAL_SCALE,'),
    ("V4", B, '"spread_per_total": (TOTAL_SCALE * df["spread_line"] / df["total_line"])', '"spread_per_total": (df["spread_line"] / df["total_line"])'),
    ("V4", B, '("both", ["spread_pts", "total_pts"]), ("ratio", ["spread_per_total"])):', '("both", ["spread_pts"]), ("ratio", ["spread_per_total"])):'),
    ("V4", B, 'return pd.Series(model.predict(test), index=test.index).fillna(test["p_blend"])', "return pd.Series(model.predict(test), index=test.index).fillna(0.5)"),
    ("V5", B, WEIGHTS, 'weights = 0.5 ** ((season - train["season"]) / h)'),
    ("V5", B, WEIGHTS, 'weights = 0.5 ** ((season - 1 - train["season"]) * h)'),
    ("V5", B, "model = LogitModel.fit(train, BLEND_FEATURES, weights=weights)", "model = LogitModel.fit(train, BLEND_FEATURES)"),
    ("V5", B, "RECENCY_HALF_LIVES = (2, 4, 8)", "RECENCY_HALF_LIVES = (2, 4, 16)"),
    ("V6", B, '    test = f[(f["season"] == season) & (f["game_type"] == "REG") & f["home_win"].notna()].copy()\n\n    home_rate',
     '    test = f[(f["season"] == season) & (f["game_type"] == "REG") & f["home_win"].notna()].copy()\n    train = pd.concat([train, test])\n\n    home_rate'),
    ("C1", B, 'earlier = preds[preds["season"] < season]', 'earlier = preds[preds["season"] <= season]'),
    ("C1", B, 'raise ValueError(f"unknown calibration method: {method}")', "method = 'isotonic'"),
    ("C1", B, "result.loc[current.index] = np.clip(values, CALIBRATION_MIN, CALIBRATION_MAX)", "result.loc[current.index] = values"),
    ("C1", B, "        if earlier.empty:\n            continue\n        if method", "        if earlier.empty:\n            earlier = current\n        if method"),
    ("C3", B, 'model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")', 'model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip", increasing=False)'),
    ("E1", F, "result.append((index, game_id, team, epa / plays, opp_epa / opp_plays,", "result.append((index, game_id, team, epa / plays, epa / plays,"),
    ("E1", F, "success / plays, opp_success / opp_plays))", "opp_success / opp_plays, success / plays))"),
    ("E1", F, "if any(plays <= 0 or not all", "if any(plays < 0 or not all"),
    ("E1", F, "if len(sides) != 2 or sides[0][1] == sides[1][1]:\n            continue\n        parsed", "if len(sides) > 2 or sides[0][1] == sides[1][1]:\n            continue\n        parsed"),
    ("E2", B, "SPLIT_EPA_SCALE = 10", "SPLIT_EPA_SCALE = 1"),
    ("E2", B, "SPLIT_SR_SCALE = 20", "SPLIT_SR_SCALE = 2"),
    ("E2", B, '(f"p_split_sr_{h}", [*BLEND_FEATURES, *epa_features, *sr_features])):', '(f"p_split_sr_{h}", [*BLEND_FEATURES, *epa_features])):'),
    ("E2", B, "SPLIT_HALF_LIVES = (4, 8, 16)", "SPLIT_HALF_LIVES = (4, 8, 12)"),
    # C2 is one change in two parts (fit and predict on the raw probability instead of its log-odds): keep these last.
    ("C2", B, "fit = earlier.assign(blend_logit=np.log(fit_prob / (1 - fit_prob)))", "fit = earlier.assign(blend_logit=fit_prob)"),
    ("C2", B, "test = current.assign(blend_logit=np.log(test_prob / (1 - test_prob)))", "test = current.assign(blend_logit=test_prob)"),
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
