"""Print the step 18a audit numbers as one JSON object (bench baselines, calibration, sample, 2026 feed state)."""

import json
import subprocess
from datetime import UTC, datetime

import httpx
import numpy as np
import pandas as pd

from nflpi.analytics.backtest import CALIBRATION_MAX, CALIBRATION_MIN, MODELS, _elo_frames, predict_season
from nflpi.analytics.metrics import paired_gain, summarize, wilson_ci
from nflpi.ingestion import nflverse
from nflpi.predictions.model import LogitModel

PERIODS = {"all": range(2012, 2026), "tune": range(2012, 2022), "confirm": range(2022, 2026)}
PAIRS = [("blend", "market"), ("blend", "logistic"), ("logistic", "elo"), ("elo", "home"), ("market", "logistic")]
CALIBRATED = ("blend", "logistic", "market")
TAGS = ("schedules", "pbp", "stats_team", "stats_player", "injuries", "snap_counts", "weekly_rosters",
        "depth_charts", "players", "nextgen_stats")
RELEASES = "https://api.github.com/repos/nflverse/nflverse-data/releases/tags"
NO_VALUE = ("", "NA")


def num(value: float | None) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


def week_clusters(rows: pd.DataFrame) -> np.ndarray:
    return rows.groupby(["season", "week"], sort=True).ngroup().to_numpy()


def reliability(rows: pd.DataFrame, model: str) -> dict:
    p = rows[f"p_{model}"]
    y = rows["home_win"]
    bins = []
    for _, group in rows.groupby(pd.qcut(p, 10, duplicates="drop"), observed=True):
        n = len(group)
        observed = float(group["home_win"].mean())
        predicted = float(group[f"p_{model}"].mean())
        lo, hi = wilson_ci(int(group["home_win"].sum()), n)
        bins.append({"n": n, "lo": num(group[f"p_{model}"].min()), "hi": num(group[f"p_{model}"].max()),
                     "predicted": predicted, "observed": observed, "gap": observed - predicted,
                     "observed_ci95": [lo, hi]})
    ece = sum(b["n"] * abs(b["gap"]) for b in bins) / len(rows)
    clipped = p.clip(CALIBRATION_MIN, CALIBRATION_MAX)
    fit = LogitModel.fit(pd.DataFrame({"x": np.log(clipped / (1 - clipped)), "home_win": y}), ["x"])
    return {"bins": bins, "ece": ece, "slope": fit.coef[0], "intercept": fit.intercept}


def season_2026(raw: list[dict[str, str]]) -> dict:
    rows = [r for r in raw if r["season"] == "2026"]
    finals = [r for r in rows if r["home_score"] not in NO_VALUE]
    pending = [r for r in rows if r["home_score"] in NO_VALUE]

    def carry(group: list[dict[str, str]]) -> dict:
        return {"moneyline": sum(r["home_moneyline"] not in NO_VALUE for r in group),
                "spread": sum(r["spread_line"] not in NO_VALUE for r in group),
                "total": sum(r["total_line"] not in NO_VALUE for r in group),
                "home_qb_name": sum(r["home_qb_name"] not in NO_VALUE for r in group)}

    return {"games": len(rows), "finals": len(finals),
            "latest_final_gameday": max((r["gameday"] for r in finals), default=None),
            "earliest_nonfinal_gameday": min((r["gameday"] for r in pending), default=None),
            "nonfinal_carrying": carry(pending), "final_carrying": carry(finals),
            "weeks_with_finals": sorted({int(r["week"]) for r in finals})}


def feed(tag: str) -> dict:
    try:
        response = httpx.get(f"{RELEASES}/{tag}", timeout=30, headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()
        assets = response.json().get("assets", [])
    except httpx.HTTPStatusError as error:
        return {"error": str(error.response.status_code)}
    except Exception as error:
        return {"error": type(error).__name__}
    picked = [a for a in assets if "2026" in a["name"]] or [a for a in assets if a["name"] == f"{tag}.csv"]
    return {"assets": [{"name": a["name"], "updated_at": a["updated_at"], "size": a["size"]} for a in picked]}


raw = nflverse.fetch_csv("schedules/games.csv")
frame = (
    pd.DataFrame(nflverse.parse_games(raw, 2002))
    .rename(columns={"_home_ml": "home_ml", "_away_ml": "away_ml"})
    .drop(columns=["_spread", "_total"])
    .sort_values(["kickoff_utc", "game_id"])
    .reset_index(drop=True)
)
frames = _elo_frames(frame)
all_preds = pd.concat([predict_season(frames, s, 10) for s in PERIODS["all"]], ignore_index=True)
preds = all_preds[all_preds["p_market"].notna()]
by_period = {name: preds[preds["season"].isin(seasons)] for name, seasons in PERIODS.items()}

reg = frame[frame["season"].between(2012, 2025) & (frame["game_type"] == "REG") & (frame["status"] == "final")]
ties_excluded = int((reg["home_score"] == reg["away_score"]).sum())
no_moneyline_excluded = int(
    ((reg["home_score"] != reg["away_score"]) & (reg["home_ml"].isna() | reg["away_ml"].isna())).sum()
)
if len(preds) != len(reg) - ties_excluded - no_moneyline_excluded:
    raise SystemExit(
        f"sample identity failed: {len(preds)} != {len(reg)} - {ties_excluded} - {no_moneyline_excluded}"
    )
qb_present = {side: preds[f"{side}_qb"].notna() & ~preds[f"{side}_qb"].isin(NO_VALUE) for side in ("home", "away")}
sample = {
    "preds_games": len(preds),
    "regular_season_finals": len(reg),
    "ties_excluded": ties_excluded,
    "no_moneyline_excluded": no_moneyline_excluded,
    "games_per_season": {str(s): int(n) for s, n in preds["season"].value_counts().sort_index().items()},
    "share_with_both_qbs": float((qb_present["home"] & qb_present["away"]).mean()),
    "home_qb_change_rate": float(preds["home_qb_change"].mean()),
    "away_qb_change_rate": float(preds["away_qb_change"].mean()),
}

result = {
    "baselines": {name: {m: summarize(rows[f"p_{m}"].to_numpy(), rows["home_win"].to_numpy()) for m in MODELS}
                  for name, rows in by_period.items()},
    "paired": {name: {f"{new}_vs_{old}": paired_gain(rows[f"p_{new}"].to_numpy(), rows[f"p_{old}"].to_numpy(),
                                                     rows["home_win"].to_numpy(), week_clusters(rows))
                      for new, old in PAIRS} for name, rows in by_period.items()},
    "reliability": {name: {m: reliability(rows, m) for m in CALIBRATED} for name, rows in by_period.items()},
    "sample": sample,
    "season_2026": season_2026(raw),
    "feeds": {tag: feed(tag) for tag in TAGS},
    "run": {"utc": datetime.now(UTC).isoformat(),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                       check=True).stdout.strip()},
}
print(json.dumps(result, indent=1, allow_nan=False))
