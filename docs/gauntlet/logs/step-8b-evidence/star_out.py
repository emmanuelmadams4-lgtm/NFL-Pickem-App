"""Step 8b bench: does knowing which stars are out before kickoff beat the blend? Scored on live nflverse files.

Run from backend/:  uv run python ../docs/gauntlet/logs/step-8b-evidence/star_out.py > run-1.json
The protocol (tune and confirm seasons, six variants, two candidates, ship rule) is frozen in step-8b.md section 2.
Every variant's tune numbers are printed; only the variant chosen on the tune seasons is scored on the confirm seasons.
Files are read through the app's own download function (same host, timeout and retries). Nothing is written.
"""

import collections
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from nflpi.analytics import backtest as bt
from nflpi.analytics import star_backtest as sb
from nflpi.analytics.metrics import summarize
from nflpi.ingestion import nflverse
from nflpi.predictions.features import BLEND_FEATURES
from nflpi.predictions.model import LogitModel

TUNE, CONFIRM = list(range(2012, 2022)), list(range(2022, 2026))
CLUSTER = ["season", "week"]  # games of one NFL week move together
FIRST_REPORT_SEASON = 2009  # the first season nflverse holds an official injury report for
LAST_SEASON = CONFIRM[-1]
RESERVE_CHECK_LIMIT = 0.01  # share of reserve player-weeks with a stat line that same week
STEP14 = Path(__file__).parent.parent / "step-14-evidence" / "run-3-candidates.json"
CANDIDATES = {
    "star_out_report": ["p_star_count", "p_star_weighted", "p_star_count_qb", "p_star_weighted_qb"],
    "star_out_reserve": ["p_star_res_count", "p_star_res_weighted"],
}


def games() -> pd.DataFrame:
    rows = nflverse.parse_games(nflverse.fetch_csv("schedules/games.csv"), 2002)
    names = {"_home_ml": "home_ml", "_away_ml": "away_ml", "_spread": "spread_line", "_total": "total_line"}
    return pd.DataFrame(rows).rename(columns=names).sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def number(value: str) -> float:
    result = 0.0 if value in ("", "NA") else float(value)
    if not math.isfinite(result):
        raise ValueError(f"not a finite number: {value[:40]}")
    return result


def fetch(path: str, season: int) -> list[dict[str, str]]:
    """One season file; a file that is empty or holds another season is an error, never a quiet zero."""
    rows = nflverse.fetch_csv(path.format(season=season))
    if not rows or any(int(row["season"]) != season for row in rows):
        sys.exit(f"{path.format(season=season)}: empty, or rows of another season")
    return rows


def stat_rows(season: int) -> list[dict]:
    """Player-week production. Rows with no player id are club totals and are skipped."""
    return [
        {"season": season, "week": int(row["week"]), "season_type": row["season_type"],
         "player_id": row["player_id"], "position": row["position"],
         **{name: number(row[name]) for name in nflverse.STAR_STATS}}
        for row in fetch("stats_player/stats_player_week_{season}.csv", season) if row["player_id"]
    ]


def report_rows(season: int) -> list[dict]:
    """The official injury report, every row (a row with no game status still shows the week had a report)."""
    return [
        {"season": season, "week": int(row["week"]), "team": nflverse.franchise(row["team"]),
         "player_id": row["gsis_id"], "status": row["report_status"] or None,
         "modified": datetime.fromisoformat(row["date_modified"].replace("Z", "+00:00"))
         if row.get("date_modified") else None}
        for row in fetch("injuries/injuries_{season}.csv", season) if row["gsis_id"]
    ]


def roster_rows(season: int) -> list[dict]:
    return [
        {"season": season, "week": int(row["week"]), "team": nflverse.franchise(row["team"]),
         "player_id": row["gsis_id"], "status": row["status"] or None}
        for row in fetch("weekly_rosters/roster_weekly_{season}.csv", season) if row["gsis_id"]
    ]


def reserve_check(roster: list[dict], stats: list[dict]) -> dict:
    """Is a reserve status a pregame fact? Count reserve player-weeks that have a stat line in that same week."""
    played = {(row["season"], row["week"], row["player_id"]) for row in stats}
    total, hits = collections.Counter(), collections.Counter()
    for row in roster:
        if row["status"] in sb.ROSTER_OUT:
            total[row["season"]] += 1
            hits[row["season"]] += (row["season"], row["week"], row["player_id"]) in played
    return {str(season): {"reserve_player_weeks": total[season], "played_that_week": hits[season],
                          "share": hits[season] / total[season]} for season in sorted(total)}


def late_rows(frame: pd.DataFrame, reports: list[dict]) -> int:
    """Out or Doubtful rows dated at or after that club's kickoff (rule F3 drops them)."""
    kickoff = {}
    for row in frame.itertuples():
        for team in (row.home_team, row.away_team):
            kickoff[(row.season, row.week, team)] = row.kickoff_utc
    return sum(
        1 for row in reports
        if (row["status"] or "").lower() in sb.REPORT_OUT and row["modified"] is not None
        and (row["season"], row["week"], row["team"]) in kickoff
        and row["modified"] >= kickoff[(row["season"], row["week"], row["team"])]
    )


def baseline(rows: pd.DataFrame) -> dict:
    y = rows["home_win"].to_numpy()
    return {model: summarize(rows[f"p_{model}"].to_numpy(), y) for model in ("market", "blend")}


def same(a, b) -> bool:
    return a == b if isinstance(a, bool | int) else math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def main() -> dict:
    started = time.monotonic()
    frame = games()
    stats = [row for season in range(FIRST_REPORT_SEASON - 1, LAST_SEASON + 1) for row in stat_rows(season)]
    reports = [row for season in range(FIRST_REPORT_SEASON, LAST_SEASON + 1) for row in report_rows(season)]
    roster = [row for season in range(sb.ROSTER_FIRST_SEASON, LAST_SEASON + 1) for row in roster_rows(season)]
    check = reserve_check(roster, stats)
    if any(row["share"] >= RESERVE_CHECK_LIMIT for row in check.values()):
        sys.exit(f"a reserve status is not a pregame fact in some season: {check}")

    stars = sb.league_stars(stats)
    inputs = sb.star_out_features(frame, stats, reports, roster)
    preds = sb.star_preds(frame, TUNE + CONFIRM, inputs)
    confirm = preds[preds["season"].isin(CONFIRM)]
    report = bt.evaluate(preds, CANDIDATES, tune=TUNE, confirm=CONFIRM, cluster=CLUSTER)
    for row in report:
        result = row["confirm"]
        row["verdict_flips_with_clusters"] = bool(result["ships"] != result["ships_cluster"])
        lo, hi = result["log_loss_gain_ci"]
        row["confirm_half_width"] = (hi - lo) / 2

    variants = [name for names in CANDIDATES.values() for name in names]
    tune_rows = preds[preds["season"].isin(TUNE)]
    out = {
        "games": int(len(preds)),
        "confirm_games": int(len(confirm)),
        "confirm_clusters": int(confirm.groupby(CLUSTER).ngroups),
        "baseline": baseline(preds),
        "baseline_confirm": baseline(confirm),
        "candidates": report,
        "data": {
            "stat_rows": len(stats), "report_rows": len(reports), "roster_rows": len(roster),
            "report_rows_dated_at_or_after_kickoff": late_rows(frame, reports),
            "stars_per_season": {str(season): dict(collections.Counter(group for group, _ in found.values()))
                                 for season, found in sorted(stars.items())},
            "reserve_check": check,
        },
        # Scored games where an input was missing, so the variant kept the blend's own number.
        "scored_games_missing_an_input": {col: int(preds[col].isna().sum()) for col in inputs.columns},
        "scored_games_with_a_nonzero_input": {col: int((preds[col].fillna(0) != 0).sum()) for col in inputs.columns},
        "scored_games_equal_to_the_blend": {
            name: {"tune": int((tune_rows[name] == tune_rows["p_blend"]).sum()),
                   "confirm": int((confirm[name] == confirm["p_blend"]).sum())} for name in variants
        },
        # Diagnostic only, tune seasons only: the weight one fit on 2012 to 2021 gives each star input.
        "tune_only_weights": {
            name: dict(zip(sb.STAR_VARIANTS[name], model.coef[len(BLEND_FEATURES):], strict=True))
            for name in variants
            for model in [LogitModel.fit(tune_rows, [*BLEND_FEATURES, *sb.STAR_VARIANTS[name]])]
        },
    }
    stored = json.loads(STEP14.read_text())
    if not all(same(out[key][model][field], stored[key][model][field]) for key in ("baseline", "baseline_confirm")
               for model in ("market", "blend") for field in ("n", "accuracy", "log_loss")):
        sys.exit("baseline differs from step 14's stored numbers: the data changed or a download was cut short")
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, allow_nan=False))
