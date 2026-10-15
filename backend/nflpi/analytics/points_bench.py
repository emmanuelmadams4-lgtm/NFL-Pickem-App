"""Walk-forward confidence-pool points bench over completed games."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nflpi.analytics import backtest, metrics, report
from nflpi.ingestion import nflverse
from nflpi.picks.pool import confidence_pool
from nflpi.picks.types import GameInputs
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES
from nflpi.predictions.model import LogitModel

TEST_SEASONS = range(2022, 2026)
GUARD_SEASONS = range(2012, 2022)
ALL_SEASONS = range(2012, 2026)
WINDOW = 10
QB_COLUMNS = ("home_qb_in", "home_qb_back", "away_qb_in", "away_qb_back")


def points_week(frame: pd.DataFrame, prob_col: str) -> pd.DataFrame:
    """Score each week with the live confidence-pool pick and weight rules."""
    rows = []
    for (season, week), games in frame.groupby(["season", "week"], sort=True):
        pool = confidence_pool([
            GameInputs(game_id=str(row.game_id), p_home_win=float(getattr(row, prob_col)),
                       p_away_win=1 - float(getattr(row, prob_col)))
            for row in games.itertuples(index=False)
        ])
        winners = dict(zip(games["game_id"], games["home_win"], strict=True))
        correct = [pick for pick in pool.picks if (pick.selection == "home") == (winners[pick.game_id] == 1)]
        rows.append({
            "season": int(season), "week": int(week),
            "points": int(sum(pick.weight for pick in correct)),
            "max_points": int(sum(pick.weight for pick in pool.picks)),
            "correct": len(correct), "n": len(pool.picks),
        })
    return pd.DataFrame(rows, columns=["season", "week", "points", "max_points", "correct", "n"])


def compare(
    frame: pd.DataFrame, cand_col: str, base_col: str, seasons: list[int] | range,
    reps: int = 2000, seed: int = 7,
) -> dict:
    """Compare both models on the same games, resampling whole weeks for points."""
    seasons = list(seasons)
    report.guard_scored(frame, seasons)
    paired = frame[frame["season"].isin(seasons)].copy()
    paired = paired[np.isfinite(paired[cand_col].to_numpy(float)) & np.isfinite(paired[base_col].to_numpy(float))]
    if paired.empty:
        raise ValueError("no paired games to score")
    cand_weeks = points_week(paired, cand_col)
    base_weeks = points_week(paired, base_col)
    differences = cand_weeks["points"].to_numpy(float) - base_weeks["points"].to_numpy(float)
    cand = paired[cand_col].to_numpy(float)
    base = paired[base_col].to_numpy(float)
    won = paired["home_win"].to_numpy(float)
    correct_diff = ((cand >= 0.5) == (won == 1)).astype(float) - ((base >= 0.5) == (won == 1)).astype(float)
    return {
        "n_weeks": int(len(differences)),
        "n_games": int(len(paired)),
        "points_gain": float(differences.mean()),
        "points_gain_ci": list(metrics.bootstrap_ci(differences, reps=reps, seed=seed)),
        "accuracy_diff": float(correct_diff.mean()),
        "log_loss_gain": float((metrics.game_log_loss(base, won) - metrics.game_log_loss(cand, won)).mean()),
    }


def decide(test: dict, guard: dict) -> dict:
    """Apply the pre-registered points rule and its three guards."""
    checks = {
        "test_points_ci_positive": test["points_gain_ci"][0] > 0,
        "test_accuracy_not_lower": test["accuracy_diff"] >= 0,
        "test_log_loss_not_worse": test["log_loss_gain"] >= 0,
        "guard_points_not_lower": guard["points_gain"] >= 0,
    }
    return {"ship": bool(all(checks.values())), "reasons": [name for name, passed in checks.items() if not passed]}


def qb_direction(df: pd.DataFrame) -> pd.DataFrame:
    """Separate a returning team starter from a backup coming in, using only earlier starts."""
    starts: dict[tuple[int, str, str], int] = {}
    previous: dict[tuple[int, str], str | None] = {}
    values = {column: [] for column in QB_COLUMNS}
    for row in df.itertuples(index=False):
        for side in ("home", "away"):
            team = getattr(row, f"{side}_team")
            qb = getattr(row, f"{side}_qb")
            qb = qb if isinstance(qb, str) and qb else None
            team_key = (int(row.season), team)
            old_qb = previous.get(team_key)
            coming_in = returning = 0.0
            if qb and old_qb and qb != old_qb:
                new_starts = starts.get((*team_key, qb), 0)
                old_starts = starts.get((*team_key, old_qb), 0)
                returning = float(new_starts > 0 and new_starts >= old_starts)
                coming_in = 1.0 - returning
            values[f"{side}_qb_in"].append(coming_in)
            values[f"{side}_qb_back"].append(returning)
            previous[team_key] = qb
            if qb:
                key = (*team_key, qb)
                starts[key] = starts.get(key, 0) + 1
    return pd.DataFrame(values, index=df.index)


def _c1_features(features: list[str]) -> list[str]:
    return [
        column for feature in features
        for column in ((f"{feature.split('_')[0]}_qb_in", f"{feature.split('_')[0]}_qb_back")
                       if feature in ("home_qb_change", "away_qb_change") else (feature,))
    ]


def _c1_season(frames: dict, season: int) -> pd.Series:
    params, train = backtest._train_rows(frames, season, WINDOW)
    frame = frames[params]
    test = frame[(frame["season"] == season) & (frame["game_type"] == "REG") & frame["home_win"].notna()]
    stats = LogitModel.fit(train, _c1_features(BASE_FEATURES)).predict(test)
    result = pd.Series(stats, index=test.index)
    has_market = test["market_logit"].notna()
    blend = LogitModel.fit(train.dropna(subset=["market_logit"]), _c1_features(BLEND_FEATURES))
    result.loc[has_market] = blend.predict(test[has_market])
    return result


def _summary(frame: pd.DataFrame, column: str, seasons: range) -> dict:
    scored = frame[frame["season"].isin(seasons)].copy()
    scored = scored[np.isfinite(scored[column].to_numpy(float))]
    weeks = points_week(scored, column)
    chances = scored[column].to_numpy(float)
    won = scored["home_win"].to_numpy(float)
    return {
        "n_games": int(len(scored)), "n_weeks": int(len(weeks)),
        "mean_points_per_week": float(weeks["points"].mean()),
        "points_ci": list(metrics.bootstrap_ci(weeks["points"].to_numpy(float))),
        "accuracy": float(((chances >= 0.5) == (won == 1)).mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games_csv", type=Path)
    parser.add_argument("out_json", type=Path)
    parser.add_argument("candidate", nargs="?", choices=["c1"])
    args = parser.parse_args()

    with args.games_csv.open(newline="", encoding="utf-8") as handle:
        rows = nflverse.parse_games(list(csv.DictReader(handle)), 2002)
    names = {"_home_ml": "home_ml", "_away_ml": "away_ml", "_spread": "spread_line", "_total": "total_line"}
    games = pd.DataFrame(rows).rename(columns=names).sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    frames = backtest.elo_frames(games)
    if args.candidate == "c1":
        direction = qb_direction(games)
        frames = {params: frame.assign(**direction) for params, frame in frames.items()}
    predictions = pd.concat(
        [backtest.predict_season(frames, season, WINDOW) for season in ALL_SEASONS], ignore_index=True
    )
    if args.candidate == "c1":
        c1 = pd.concat([_c1_season(frames, season) for season in ALL_SEASONS])
        predictions["p_c1"] = c1.to_numpy()

    windows = {"test": TEST_SEASONS, "guard": GUARD_SEASONS}
    output = {"windows": {}}
    for name, seasons in windows.items():
        result = {
            "seasons": list(seasons),
            "models": {model: _summary(predictions, f"p_{model}", seasons)
                       for model in ("market", "blend", "logistic")},
            "comparisons": {
                "market_vs_blend": compare(predictions, "p_market", "p_blend", seasons),
                "stats_vs_blend": compare(predictions, "p_logistic", "p_blend", seasons),
            },
        }
        if args.candidate == "c1":
            result["models"]["c1"] = _summary(predictions, "p_c1", seasons)
            result["comparisons"]["c1_vs_blend"] = compare(predictions, "p_c1", "p_blend", seasons)
        output["windows"][name] = result
    if args.candidate == "c1":
        output["decision"] = decide(
            output["windows"]["test"]["comparisons"]["c1_vs_blend"],
            output["windows"]["guard"]["comparisons"]["c1_vs_blend"],
        )
    args.out_json.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
