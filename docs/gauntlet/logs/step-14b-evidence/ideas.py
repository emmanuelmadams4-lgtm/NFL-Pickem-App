"""Step 14b bench: score ONE idea per run, in the plan's order, against live nflverse files.

Run from backend/:  uv run python ../docs/gauntlet/logs/step-14b-evidence/ideas.py <stage> > run-<stage>.json
Stages, in order: cluster, devig, inputs, calibration, recency, split (idea 5, only after the gate in the log opened).
The protocol (tune and confirm seasons, variants, ship rule, "signal") is frozen in step-14b.md section 2.
Every variant's tune numbers are printed; only the variant chosen on the tune seasons is scored on the confirm seasons.
"""

import collections
import csv
import gzip
import io
import json
import math
import sys
import time
from pathlib import Path

import pandas as pd

from nflpi.analytics import backtest as bt
from nflpi.analytics.metrics import calibration, summarize
from nflpi.config import get_settings
from nflpi.ingestion import nflverse
from nflpi.predictions.features import offence_defence, team_game_epa

TUNE, CONFIRM = list(range(2012, 2022)), list(range(2022, 2026))
CLUSTER = ["season", "week"]  # games of one NFL week move together
FIRST_CALIBRATION_SEASON = 2008  # first season with two priced seasons (2006, 2007) behind it
STEP14 = Path(__file__).parent.parent / "step-14-evidence" / "run-3-candidates.json"
RULE_KEYS = ("n", "log_loss_gain", "log_loss_gain_ci", "accuracy_diff", "accuracy_diff_ci", "ships")
CANDIDATES = {
    "cluster": {"inseason_refit": ["p_inseason"], "epa_rating": [f"p_epa_{h}" for h in bt.EPA_HALF_LIVES]},
    "devig": {"devig": [f"p_devig_{m}" for m in ("additive", "shin", "power", "odds_ratio")]},
    "inputs": {"line_inputs": [f"p_in_{v}" for v in ("spread", "total", "both", "ratio")]},
    "calibration": {"calibrated_blend": ["p_cal_platt", "p_cal_isotonic"]},
    "recency": {"recency_weights": [f"p_recency_{h}" for h in (2, 4, 8)]},
    "split": {"offence_defence_split": [f"p_split{sr}_{h}" for sr in ("", "_sr") for h in (4, 8, 16)]},
}


def games() -> pd.DataFrame:
    rows = nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)
    names = {"_home_ml": "home_ml", "_away_ml": "away_ml", "_spread": "spread_line", "_total": "total_line"}
    return pd.DataFrame(rows).rename(columns=names).sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def play_sums(first: int, last: int) -> list[dict]:
    """Per team and game: scrimmage plays (pass or run with an EPA value), their EPA and how many succeeded.

    Source: nflverse play-by-play, through the app's own download function (same host, retries, timeout).
    """
    settings = get_settings()
    sums: dict[tuple[str, str], list[float]] = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for season in range(first, last + 1):
        raw = nflverse._fetch(f"{settings.nflverse_base}/pbp/play_by_play_{season}.csv.gz", settings).content
        with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                values = (row["epa"], row["success"], row["posteam"])
                if row["play_type"] in ("pass", "run") and not any(value in ("", "NA") for value in values):
                    total = sums[(row["game_id"], nflverse.franchise(row["posteam"]))]
                    total[0] += 1
                    total[1] += float(row["epa"])
                    total[2] += float(row["success"])
    return [{"game_id": game_id, "team": team, "plays": plays, "epa": epa, "success": success}
            for (game_id, team), (plays, epa, success) in sums.items()]


def baseline(rows: pd.DataFrame) -> dict:
    y = rows["home_win"].to_numpy()
    return {model: summarize(rows[f"p_{model}"].to_numpy(), y) for model in ("market", "blend")}


def same(a, b) -> bool:
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    return a == b if isinstance(a, bool | int) else math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def matches_step14(report: list[dict]) -> bool:
    """The game-level numbers recomputed here must equal the ones step 14 stored."""
    stored = json.loads(STEP14.read_text())["candidates"]
    pairs = []
    for new, old in zip(report, stored, strict=True):
        pairs.append((new["confirm"], old["confirm"]))
        pairs += [(n["tune"], o["tune"]) for n, o in zip(new["variants"], old["variants"], strict=True)]
        if new["chosen"] != old["chosen"]:
            return False
    return all(same(new[key], old[key]) for new, old in pairs for key in RULE_KEYS)


def main(stage: str) -> dict:
    started = time.monotonic()
    frame = games()
    out: dict = {"stage": stage}
    if stage == "cluster":
        epa_rows = [row for season in range(2002, 2026)
                    for row in nflverse.fetch_csv(f"stats_team/stats_team_week_{season}.csv")]
        preds = bt.candidate_preds(frame, TUNE + CONFIRM, epa=team_game_epa(epa_rows))
    elif stage == "split":
        rows = play_sums(2002, CONFIRM[-1])
        split = offence_defence(rows)
        preds = bt.split_preds(frame, TUNE + CONFIRM, split)
        out |= {"play_by_play_team_games": len(rows), "rated_games": int(split["game_id"].nunique()),
                "scored_games_without_a_rating": int(preds.loc[preds["season"].isin(TUNE + CONFIRM),
                                                               "off_epa_diff_4"].isna().sum())}
    else:
        first = FIRST_CALIBRATION_SEASON if stage == "calibration" else TUNE[0]
        preds = bt.idea_preds(frame, list(range(first, CONFIRM[-1] + 1)))
    if stage == "calibration":
        tune_rows = preds[preds["season"].isin(TUNE)]
        y = tune_rows["home_win"].to_numpy()
        # Printed before any calibrated number: is the blend off at all on the seasons we may tune on?
        out["reliability_tune"] = {m: calibration(tune_rows[f"p_{m}"].to_numpy(), y) for m in ("blend", "market")}
        out["reliability_tune_10_bins_home"] = [
            {"bucket": f"{lo}-{lo + 10}%", "n": int(len(g)), "predicted": float(g["p_blend"].mean()),
             "observed": float(g["home_win"].mean())}
            for lo, g in tune_rows.groupby((tune_rows["p_blend"] * 10).astype(int).clip(0, 9) * 10)
        ]
        for method in ("platt", "isotonic"):
            preds[f"p_cal_{method}"] = bt.calibrated(preds, method)
        out["calibration_seasons_before_2012"] = sorted(int(s) for s in set(preds["season"]) if s < TUNE[0])
    scored = preds[preds["season"].isin(TUNE + CONFIRM)]
    confirm = scored[scored["season"].isin(CONFIRM)]
    report = bt.evaluate(scored, CANDIDATES[stage], tune=TUNE, confirm=CONFIRM, cluster=CLUSTER)
    for row in report:
        chosen_tune = next(v["tune"] for v in row["variants"] if v["variant"] == row["chosen"])
        result = row["confirm"]
        # Frozen meaning of "signal": the chosen variant gains on the tune seasons AND on the confirm seasons.
        row["signal"] = bool(chosen_tune["log_loss_gain"] > 0 and result["log_loss_gain"] > 0)
        row["verdict_flips_with_clusters"] = bool(result["ships"] != result["ships_cluster"])
        lo, hi = result["log_loss_gain_ci"]
        clo, chi = result["log_loss_gain_ci_cluster"]
        row["confirm_half_width"] = {"game": (hi - lo) / 2, "cluster": (chi - clo) / 2}
    out |= {
        "games": int(len(scored)),
        "confirm_games": int(len(confirm)),
        "confirm_clusters": int(confirm.groupby(CLUSTER).ngroups),
        "baseline": baseline(scored),
        "baseline_confirm": baseline(confirm),
        "candidates": report,
    }
    if stage == "cluster":
        out["matches_step14_stored_numbers"] = matches_step14(report)
    else:
        out["scored_games_missing"] = {col: int(scored[col].isna().sum()) for col in ("spread_line", "total_line")}
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CANDIDATES:
        sys.exit(f"usage: ideas.py <{'|'.join(CANDIDATES)}>")
    print(json.dumps(main(sys.argv[1]), indent=1, allow_nan=False))
