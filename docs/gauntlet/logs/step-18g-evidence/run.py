"""Step 18g bench: score ONE idea per run, in the plan's order, against live nflverse files.

Run from backend/:  uv run python ../docs/gauntlet/logs/step-18g-evidence/run.py <stage> > run-<stage>.json
Stages, in order: pythag, qb, travel, matchup.
The protocol (tune and confirm seasons, variants, ship rule, labels) is frozen in step-18g.md section 2.
Football-only variants are judged against the live stats-only model (p_logistic) and, beside it, against the live
blend (p_blend); the variant is chosen on the tune seasons against p_logistic and only that variant is scored.
"""

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from nflpi.analytics import backtest as bt
from nflpi.analytics import bench_18g as b
from nflpi.analytics.metrics import paired_gain, summarize
from nflpi.ingestion import nflverse

TUNE, CONFIRM = list(range(2012, 2022)), list(range(2022, 2026))
CLUSTER = ["season", "week"]  # games of one NFL week move together
STEP14 = Path(__file__).parent.parent / "step-14-evidence" / "run-3-candidates.json"
FIRST_STATS_SEASON = 2002


def games() -> pd.DataFrame:
    """The 14c frame plus the starting quarterbacks' ids, read from the same schedule file."""
    raw = nflverse.fetch_csv("schedules/games.csv")
    rows = nflverse.parse_games(raw, FIRST_STATS_SEASON)
    names = {"_home_ml": "home_ml", "_away_ml": "away_ml", "_spread": "spread_line", "_total": "total_line"}
    frame = pd.DataFrame(rows).rename(columns=names).sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    ids = {r["game_id"]: (r["home_qb_id"], r["away_qb_id"]) for r in raw}
    for side, position in (("home", 0), ("away", 1)):
        values = [ids[g][position] for g in frame["game_id"]]
        frame[f"{side}_qb_id"] = [v if v not in ("", "NA") else None for v in values]
    return frame


def player_rows() -> list[dict]:
    """Quarterback rows of every player-week file from 2002 to the last confirm season."""
    keep = ("player_id", "game_id", "position", "passing_epa", "rushing_epa", "attempts", "sacks_suffered", "carries")
    rows = []
    for season in range(FIRST_STATS_SEASON, CONFIRM[-1] + 1):
        for row in nflverse.fetch_csv(f"stats_player/stats_player_week_{season}.csv"):
            if row["position"] == "QB":
                rows.append({k: row[k] for k in keep})
    return rows


def baseline(rows: pd.DataFrame) -> dict:
    y = rows["home_win"].to_numpy()
    return {model: summarize(rows[f"p_{model}"].to_numpy(), y) for model in ("market", "blend")}


def same(a, c) -> bool:
    return a == c if isinstance(a, bool | int) else math.isclose(a, c, rel_tol=1e-9, abs_tol=1e-12)


def check_baseline(out: dict) -> None:
    stored = json.loads(STEP14.read_text())
    if not all(same(out[key][model][field], stored[key][model][field]) for key in ("baseline", "baseline_confirm")
               for model in ("market", "blend") for field in ("n", "accuracy", "log_loss")):
        sys.exit("baseline differs from step 14's stored numbers: the data changed or a download was cut short")


def judge(preds: pd.DataFrame, name: str, columns: list[str], football: bool) -> dict:
    """One candidate, one confirm look. Football-only: chosen against p_logistic, also scored against p_blend."""
    primary = "p_logistic" if football else "p_blend"
    row = b.evaluate_vs(preds, {name: columns}, TUNE, CONFIRM, primary, CLUSTER)[0]
    chosen = row["chosen"]
    row["label"] = b.label(chosen)
    row["verdict"] = b.verdict(row["confirm"])
    lo, hi = row["confirm"]["log_loss_gain_ci"]
    clo, chi = row["confirm"]["log_loss_gain_ci_cluster"]
    row["confirm_half_width"] = {"game": (hi - lo) / 2, "cluster": (chi - clo) / 2}
    if football:
        rows = preds[preds["season"].isin(CONFIRM)]
        clusters = rows.groupby(CLUSTER, sort=True).ngroup().to_numpy()
        against_blend = paired_gain(rows[chosen].to_numpy(), rows["p_blend"].to_numpy(),
                                    rows["home_win"].to_numpy(), clusters=clusters)
        row["confirm_vs_blend"] = against_blend
        row["verdict_vs_blend"] = b.verdict(against_blend)
    return row


def main(stage: str) -> dict:
    started = time.monotonic()
    frame = games()
    seasons = TUNE + CONFIRM
    out: dict = {"stage": stage, "confirm_looks_before": 15}
    if stage == "pythag":
        preds = b.pythag_preds(frame, seasons)
        cands = {"pythag_market": ([b.pythag_column("blend", h) for h in b.PYTH_HALF_LIVES], False),
                 "pythag_football": ([b.pythag_column("base", h) for h in b.PYTH_HALF_LIVES], True)}
    elif stage == "qb":
        log = b.qb_games(player_rows())
        preds = b.qb_preds(frame, seasons, log)
        cands = {"qb_market": ([b.qb_column("blend", h) for h in b.QB_HALF_LIVES], False),
                 "qb_football": ([b.qb_column("base", h) for h in b.QB_HALF_LIVES], True)}
        out["quarterback_games_in_log"] = int(len(log))
        out["games_missing_a_starter_id"] = int(frame[["home_qb_id", "away_qb_id"]].isna().any(axis=1).sum())
    elif stage == "travel":
        preds = b.travel_preds(frame, seasons)
        features = b.travel_features(frame, b.STADIUM_COORDS, b.STADIUM_ZONES)
        scored = frame[frame["season"].isin(seasons) & (frame["game_type"] == "REG")]
        out["games_without_travel_features"] = int(features.loc[scored.index].isna().any(axis=1).sum())
        out["games_scored_frame"] = int(len(scored))
        out["unknown_stadium_ids"] = sorted(set(scored["stadium_id"].dropna()) - set(b.STADIUM_COORDS))
        cands = {"travel_market": ([b.travel_column("blend", v) for v in b.TRAVEL_VARIANTS], False),
                 "travel_football": ([b.travel_column("base", v) for v in b.TRAVEL_VARIANTS], True)}
    else:  # matchup
        preds = b.matchup_preds(frame, seasons)
        out["input_gap_blend_vs_blend_plus_matchup_logodds"] = b.matchup_input_gap(frame, seasons)
        cands = {"matchup_football": (["p_match_football"], True), "matchup_market": (["p_match_market"], False)}
    scored = preds[preds["season"].isin(seasons)]
    confirm = scored[scored["season"].isin(CONFIRM)]
    out |= {"games": int(len(scored)), "confirm_games": int(len(confirm)),
            "confirm_clusters": int(confirm.groupby(CLUSTER).ngroups),
            "baseline": baseline(scored), "baseline_confirm": baseline(confirm)}
    check_baseline(out)
    out["candidates"] = [judge(scored, name, cols, football) for name, (cols, football) in cands.items()]
    out["variant_columns_equal_to_baseline"] = {
        col: int(np.isclose(scored[col], scored["p_logistic" if "_base_" in col or col == "p_match_football"
                                                  else "p_blend"]).sum())
        for cols, _ in cands.values() for col in cols}
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("pythag", "qb", "travel", "matchup"):
        sys.exit("usage: run.py <pythag|qb|travel|matchup>")
    print(json.dumps(main(sys.argv[1]), indent=1, allow_nan=False))
