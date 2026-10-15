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


def injury_counts(games: pd.DataFrame, injuries: pd.DataFrame) -> pd.DataFrame:
    """Count listed out non-QB players for each game's two teams and week."""
    counts: dict[tuple[int, int, str], int] = {}
    for row in injuries.itertuples(index=False):
        if str(row.report_status).strip().lower() != "out" or str(row.position).strip().upper() == "QB":
            continue
        key = (int(row.season), int(row.week), row.team)
        counts[key] = counts.get(key, 0) + 1
    home, away = [], []
    for row in games.itertuples(index=False):
        home.append(counts.get((int(row.season), int(row.week), row.home_team), 0))
        away.append(counts.get((int(row.season), int(row.week), row.away_team), 0))
    return pd.DataFrame({
        "home_out_nonqb": home, "away_out_nonqb": away,
        "inj_diff": [(h - a) / 5 for h, a in zip(home, away, strict=True)],
    }, index=games.index)


def efficiency_diff(games: pd.DataFrame, plays: pd.DataFrame) -> pd.Series:
    """Pregame rating difference from earlier opponent-adjusted team EPA nets."""
    valid = plays[plays["play_type"].isin(("pass", "run")) & plays["posteam"].notna()
                  & plays["defteam"].notna()].copy()
    valid["epa"] = pd.to_numeric(valid["epa"], errors="coerce")
    valid = valid[np.isfinite(valid["epa"].to_numpy(float))]
    off = valid.groupby(["season", "week", "posteam"])["epa"].mean().to_dict()
    defense = valid.groupby(["season", "week", "defteam"])["epa"].mean().to_dict()
    raw: dict[tuple[int, str], list[float]] = {}
    adjusted: dict[tuple[int, str], list[float]] = {}
    differences = []
    for row in games.itertuples(index=False):
        season, week = int(row.season), int(row.week)
        home, away = row.home_team, row.away_team
        home_key, away_key = (season, home), (season, away)
        home_raw, away_raw = raw.get(home_key, []), raw.get(away_key, [])
        home_adjusted, away_adjusted = adjusted.get(home_key, []), adjusted.get(away_key, [])
        home_strength = float(np.mean(home_raw)) if home_raw else 0.0
        away_strength = float(np.mean(away_raw)) if away_raw else 0.0
        differences.append(
            (float(np.mean(home_adjusted)) if home_adjusted else 0.0)
            - (float(np.mean(away_adjusted)) if away_adjusted else 0.0)
        )
        nets = {}
        for team in (home, away):
            game_key = (season, week, team)
            if game_key in off and game_key in defense:
                nets[team] = off[game_key] - defense[game_key]
        if home in nets:
            raw.setdefault(home_key, []).append(nets[home])
            adjusted.setdefault(home_key, []).append(nets[home] + away_strength)
        if away in nets:
            raw.setdefault(away_key, []).append(nets[away])
            adjusted.setdefault(away_key, []).append(nets[away] + home_strength)
    return pd.Series(differences, index=games.index, name="eff_diff")


def _c1_features(features: list[str]) -> list[str]:
    return [
        column for feature in features
        for column in ((f"{feature.split('_')[0]}_qb_in", f"{feature.split('_')[0]}_qb_back")
                       if feature in ("home_qb_change", "away_qb_change") else (feature,))
    ]


def _feature_season(frames: dict, season: int, features: dict[str, list[str]]) -> pd.Series:
    params, train = backtest._train_rows(frames, season, WINDOW)
    frame = frames[params]
    test = frame[(frame["season"] == season) & (frame["game_type"] == "REG") & frame["home_win"].notna()]
    stats = LogitModel.fit(train, features["stats"]).predict(test)
    result = pd.Series(stats, index=test.index)
    has_market = test["market_logit"].notna()
    blend = LogitModel.fit(train.dropna(subset=["market_logit"]), features["blend"])
    result.loc[has_market] = blend.predict(test[has_market])
    return result


def mix_c2(preds: pd.DataFrame) -> pd.Series:
    """Fit a model/market mix using only earlier out-of-sample seasons."""
    result = preds["p_blend"].copy()
    columns = ("c2_market_logit", "c2_stats_logit")
    market = preds["p_market"].to_numpy(float)
    stats = preds["p_logistic"].to_numpy(float)
    has_inputs = np.isfinite(market) & np.isfinite(stats)
    frame = preds.copy()
    for column, chances in zip(columns, (market, stats), strict=True):
        clipped = np.clip(chances, 0.01, 0.99)
        frame[column] = np.log(clipped / (1 - clipped))
    for season in sorted(preds["season"].unique()):
        train = frame[(frame["season"] >= 2012) & (frame["season"] < season)
                      & has_inputs & np.isfinite(frame["home_win"].to_numpy(float))]
        test = frame[(frame["season"] == season) & has_inputs]
        if train["home_win"].nunique() < 2 or test.empty:
            continue
        result.loc[test.index] = LogitModel.fit(train, list(columns)).predict(test)
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
    parser.add_argument("candidate", nargs="?", choices=["c1", "c2", "c3", "c4"])
    parser.add_argument("--injuries", type=Path, help="directory of nflverse injuries_*.csv files (required for c3)")
    parser.add_argument("--pbp", type=Path, help="directory of play_by_play_*.csv.gz files (required for c4)")
    args = parser.parse_args()

    with args.games_csv.open(newline="", encoding="utf-8") as handle:
        rows = nflverse.parse_games(list(csv.DictReader(handle)), 2002)
    names = {"_home_ml": "home_ml", "_away_ml": "away_ml", "_spread": "spread_line", "_total": "total_line"}
    games = pd.DataFrame(rows).rename(columns=names).sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    frames = backtest.elo_frames(games)
    if args.candidate == "c1":
        direction = qb_direction(games)
        frames = {params: frame.assign(**direction) for params, frame in frames.items()}
    elif args.candidate == "c3":
        if args.injuries is None:
            parser.error("c3 requires --injuries DIR")
        files = sorted(args.injuries.glob("injuries_*.csv"))
        if not files:
            parser.error("--injuries contains no injuries_*.csv files")
        injuries = []
        for path in files:
            with path.open(newline="", encoding="utf-8") as handle:
                injuries.extend({
                    "season": int(row["season"]), "week": int(row["week"]),
                    "team": nflverse.franchise(row["team"]), "position": row["position"],
                    "report_status": row["report_status"],
                } for row in csv.DictReader(handle))
        counts = injury_counts(games, pd.DataFrame(injuries))
        frames = {params: frame.assign(inj_diff=counts["inj_diff"]) for params, frame in frames.items()}
    elif args.candidate == "c4":
        if args.pbp is None:
            parser.error("c4 requires --pbp DIR")
        files = sorted(args.pbp.glob("play_by_play_*.csv.gz"))
        if not files:
            parser.error("--pbp contains no play_by_play_*.csv.gz files")
        columns = ["season", "week", "posteam", "defteam", "epa", "play_type"]
        plays = pd.concat(
            [pd.read_csv(path, usecols=columns, low_memory=False) for path in files], ignore_index=True
        ).dropna(subset=["posteam", "defteam"])
        for column in ("posteam", "defteam"):
            plays[column] = plays[column].map(nflverse.franchise)
        difference = efficiency_diff(games, plays)
        frames = {params: frame.assign(eff_diff=difference) for params, frame in frames.items()}
    predictions = pd.concat(
        [backtest.predict_season(frames, season, WINDOW) for season in ALL_SEASONS], ignore_index=True
    )
    if args.candidate in ("c1", "c3", "c4"):
        if args.candidate == "c1":
            features = {"stats": _c1_features(BASE_FEATURES), "blend": _c1_features(BLEND_FEATURES)}
        else:
            extra = "inj_diff" if args.candidate == "c3" else "eff_diff"
            features = {"stats": [*BASE_FEATURES, extra], "blend": [*BLEND_FEATURES, extra]}
        candidate = pd.concat([_feature_season(frames, season, features) for season in ALL_SEASONS])
        predictions[f"p_{args.candidate}"] = candidate.to_numpy()
    elif args.candidate == "c2":
        predictions["p_c2"] = mix_c2(predictions)

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
        if args.candidate:
            result["models"][args.candidate] = _summary(predictions, f"p_{args.candidate}", seasons)
            result["comparisons"][f"{args.candidate}_vs_blend"] = compare(
                predictions, f"p_{args.candidate}", "p_blend", seasons,
            )
        output["windows"][name] = result
    if args.candidate:
        comparison = f"{args.candidate}_vs_blend"
        output["decision"] = decide(
            output["windows"]["test"]["comparisons"][comparison],
            output["windows"]["guard"]["comparisons"][comparison],
        )
    args.out_json.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
