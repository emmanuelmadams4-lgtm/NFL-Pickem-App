"""Step 14c bench: score ONE idea per run, in the plan's order, against live nflverse files.

Run from backend/:  uv run python ../docs/gauntlet/logs/step-14c-evidence/run.py <stage> > run-<stage>.json
Stages, in order: trees, stack, margin, explosive, points.
The protocol (tune and confirm seasons, variants, ship rule) is frozen in step-14c.md section 2.
Every variant's tune gain is printed with its confirm gain and the gap; only the variant chosen on the tune
seasons decides anything on the confirm seasons.
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

import numpy as np
import pandas as pd

from nflpi.analytics import backtest as bt
from nflpi.analytics import model_c as mc
from nflpi.analytics.metrics import summarize
from nflpi.config import get_settings
from nflpi.ingestion import nflverse

TUNE, CONFIRM = list(range(2012, 2022)), list(range(2022, 2026))
HISTORY_FROM = 2008  # first season with two priced seasons behind it; used only to give the stack weights a past
CLUSTER = ["season", "week"]  # games of one NFL week move together
STEP14 = Path(__file__).parent.parent / "step-14-evidence" / "run-3-candidates.json"
TREE_COLUMNS = {s: [mc.tree_column(s, d, leaf) for d, leaf in mc.TREE_GRID] for s in mc.TREE_SETS}
CANDIDATES = {
    "trees": {"tree_core": TREE_COLUMNS["core"], "tree_wide": TREE_COLUMNS["wide"]},
    "stack": {"stack": ["p_stack_fit", "p_stack_half"]},
    "margin": {"margin_alone": ["p_m_stats", "p_m_line"],
               "margin_input": ["p_m_in_stats", "p_m_in_stats_total", "p_m_in_line"]},
    "explosive": {"explosive_rate": [f"p_expl_{h}" for h in mc.EXPLOSIVE_HALF_LIVES]},
}
EXPLOSIVE_PASS, EXPLOSIVE_RUN = 20, 10  # yards gained that make a pass or a run explosive


def games() -> pd.DataFrame:
    rows = nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)
    names = {"_home_ml": "home_ml", "_away_ml": "away_ml", "_spread": "spread_line", "_total": "total_line"}
    return pd.DataFrame(rows).rename(columns=names).sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def play_sums(first: int, last: int) -> list[dict]:
    """Per team and game: scrimmage plays (pass or run with an EPA value) and how many were explosive.

    Source: nflverse play-by-play, through the app's own download function (same host, retries, timeout).
    """
    settings = get_settings()
    sums: dict[tuple[str, str], list[float]] = collections.defaultdict(lambda: [0.0, 0.0])
    for season in range(first, last + 1):
        raw = nflverse._fetch(f"{settings.nflverse_base}/pbp/play_by_play_{season}.csv.gz", settings).content
        with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                values = (row["epa"], row["yards_gained"], row["posteam"])
                if row["play_type"] in ("pass", "run") and not any(value in ("", "NA") for value in values):
                    total = sums[(row["game_id"], nflverse.franchise(row["posteam"]))]
                    total[0] += 1
                    cut = EXPLOSIVE_PASS if row["play_type"] == "pass" else EXPLOSIVE_RUN
                    total[1] += float(float(row["yards_gained"]) >= cut)
    return [{"game_id": game_id, "team": team, "plays": plays, "explosive": explosive}
            for (game_id, team), (plays, explosive) in sums.items()]


def baseline(rows: pd.DataFrame) -> dict:
    y = rows["home_win"].to_numpy()
    return {model: summarize(rows[f"p_{model}"].to_numpy(), y) for model in ("market", "blend")}


def same(a, b) -> bool:
    return a == b if isinstance(a, bool | int) else math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def check_baseline(out: dict) -> None:
    stored = json.loads(STEP14.read_text())
    if not all(same(out[key][model][field], stored[key][model][field]) for key in ("baseline", "baseline_confirm")
               for model in ("market", "blend") for field in ("n", "accuracy", "log_loss")):
        sys.exit("baseline differs from step 14's stored numbers: the data changed or a download was cut short")


def tree_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return mc.tree_preds(frame, list(range(HISTORY_FROM, CONFIRM[-1] + 1)))


def best_tree_column(preds: pd.DataFrame) -> str:
    """The tree variant with the largest gain over the blend on the TUNE seasons only."""
    tune = preds[preds["season"].isin(TUNE)]
    y, base = tune["home_win"].to_numpy(), tune["p_blend"].to_numpy()
    columns = [c for cols in TREE_COLUMNS.values() for c in cols]
    return max(columns, key=lambda c: bt.log_loss(base, y) - bt.log_loss(tune[c].to_numpy(), y))


def main(stage: str) -> dict:
    started = time.monotonic()
    frame = games()
    out: dict = {"stage": stage}
    if stage == "trees":
        preds = tree_frame(frame)
    elif stage == "stack":
        preds = tree_frame(frame)
        tree = best_tree_column(preds)
        out["tree_chosen_on_tune"] = tree
        preds["p_stack_fit"] = mc.stacked(preds, tree)
        preds["p_stack_half"] = 0.5 * preds["p_blend"] + 0.5 * preds[tree]
        out["weights_by_season"] = {
            int(s): mc.stack_weight(g["p_blend"].to_numpy(), g[tree].to_numpy(), g["home_win"].to_numpy())
            for s in sorted(preds["season"].unique()) if s >= TUNE[0] - 1
            for g in [preds[preds["season"] < s]] if len(g)}
    elif stage == "margin":
        preds = mc.margin_preds(frame, TUNE + CONFIRM)
    elif stage == "explosive":
        rows = play_sums(2002, CONFIRM[-1])
        explosive = mc.explosive_net(rows)
        preds = mc.explosive_preds(frame, TUNE + CONFIRM, explosive)
        out |= {"play_by_play_team_games": len(rows), "rated_games": int(explosive["game_id"].nunique())}
    else:  # points
        frames = bt._elo_frames(frame)
        preds = bt._market_games([bt.predict_season(frames, s, 10) for s in TUNE + CONFIRM])
    scored = preds[preds["season"].isin(TUNE + CONFIRM)]
    confirm = scored[scored["season"].isin(CONFIRM)]
    out |= {"games": int(len(scored)), "confirm_games": int(len(confirm)),
            "confirm_clusters": int(confirm.groupby(CLUSTER).ngroups),
            "baseline": baseline(scored), "baseline_confirm": baseline(confirm)}
    check_baseline(out)
    if stage == "points":
        out["points"] = {"all": mc.points_report(scored), "tune": mc.points_report(scored[scored["season"].isin(TUNE)]),
                         "confirm": mc.points_report(confirm)}
    else:
        report = mc.evaluate_c(scored, CANDIDATES[stage], tune=TUNE, confirm=CONFIRM, cluster=CLUSTER)
        for row in report:
            chosen_tune = next(v["tune"] for v in row["variants"] if v["variant"] == row["chosen"])
            result = row["confirm"]
            row["signal"] = bool(chosen_tune["log_loss_gain"] > 0 and result["log_loss_gain"] > 0)
            row["verdict_flips_with_clusters"] = bool(result["ships"] != result["ships_cluster"])
            lo, hi = result["log_loss_gain_ci"]
            clo, chi = result["log_loss_gain_ci_cluster"]
            row["confirm_half_width"] = {"game": (hi - lo) / 2, "cluster": (chi - clo) / 2}
        out["candidates"] = report
        out["scored_games_missing_an_input"] = {
            col: int(scored[col].isna().sum()) for col in scored if col.startswith(("m_", "spread_", "total_"))}
        out["variant_columns_equal_to_blend"] = {
            col: int(np.isclose(scored[col], scored["p_blend"]).sum())
            for cols in CANDIDATES[stage].values() for col in cols}
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in (*CANDIDATES, "points"):
        sys.exit(f"usage: run.py <{'|'.join((*CANDIDATES, 'points'))}>")
    print(json.dumps(main(sys.argv[1]), indent=1, allow_nan=False))
