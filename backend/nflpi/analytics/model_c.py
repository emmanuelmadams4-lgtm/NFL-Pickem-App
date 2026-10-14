"""Step 14c candidates: boosted trees and a stacked blend, judged by the walk-forward ship rule."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from nflpi.analytics import backtest
from nflpi.analytics.metrics import bootstrap_ci, log_loss, paired_gain
from nflpi.predictions import scores
from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import BLEND_FEATURES, epa_diff
from nflpi.predictions.model import LogitModel
from nflpi.predictions.scores import STATS_FEATURES, ScoreModel
from nflpi.predictions.sheet import TIE_BAND

TREE_SETS = {
    "core": BLEND_FEATURES,
    "wide": [*BLEND_FEATURES, "spread_line", "total_line", "rest_diff", "roof_indoor", "temp_f", "wind_mph",
             "div_flag"],
}
TREE_GRID = ((2, 30), (2, 80), (3, 30), (3, 80))
TREE_LEARNING_RATE = 0.05
TREE_MAX_ITER = 300
STACK_GRID = tuple(round(0.05 * i, 2) for i in range(21))
STACK_TIE_PENALTY = 1e-12  # floating-point noise must not beat a smaller weight
INDOOR_ROOFS = {"dome": 1.0, "closed": 1.0, "outdoors": 0.0, "open": 0.0}
MARGIN_SCALE = 7
TOTAL_CENTER = 45
TOTAL_SCALE = 10
SCORE_COLUMNS = ["home_pf", "home_pa", "away_pf", "away_pa", "implied_home", "implied_away"]
EXPLOSIVE_HALF_LIVES = (4, 8, 16)
EXPLOSIVE_SCALE = 50
POINT_ORDERS = ("sort", "market", "kickoff", "reverse", "oracle")


def tree_column(set_name: str, depth: int, leaf: int) -> str:
    """Name of one tree variant's prediction column."""
    return f"p_tree_{set_name}_d{depth}_l{leaf}"


def tree_inputs(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with the roof and division game coded as numbers."""
    out = frame.copy()
    out["roof_indoor"] = out["roof"].map(INDOOR_ROOFS).astype(float)
    out["div_flag"] = out["div_game"].fillna(False).astype(bool).astype(float)
    return out


@dataclass
class TreeModel:
    features: list[str]
    n_iter: int
    model: HistGradientBoostingClassifier

    @classmethod
    def _classifier(cls, depth: int, leaf: int, max_iter: int) -> HistGradientBoostingClassifier:
        return HistGradientBoostingClassifier(
            max_depth=depth, min_samples_leaf=leaf, learning_rate=TREE_LEARNING_RATE, max_iter=max_iter,
            l2_regularization=1.0, early_stopping=False, random_state=0,
        )

    @classmethod
    def fit_early(cls, train: pd.DataFrame, features: list[str], depth: int, leaf: int) -> "TreeModel":
        """Pick the tree count on the last training season, then refit on every training season."""
        rows = train[train["home_win"].notna()]
        last = rows["season"].max()
        fit, held = rows[rows["season"] < last], rows[rows["season"] == last]
        first = cls._classifier(depth, leaf, TREE_MAX_ITER).fit(fit[features], fit["home_win"])
        y = held["home_win"].to_numpy()
        losses = [log_loss(p[:, 1], y) for p in first.staged_predict_proba(held[features])]
        n_iter = int(np.argmin(losses)) + 1
        model = cls._classifier(depth, leaf, n_iter).fit(rows[features], rows["home_win"])
        return cls(list(features), n_iter, model)

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        """Home win chance per row."""
        return self.model.predict_proba(x[self.features])[:, 1]


def tree_preds(df: pd.DataFrame, seasons: list[int], window: int = 10, grid=TREE_GRID) -> pd.DataFrame:
    """Score held-out seasons with boosted-tree variants beside the blend."""
    frames = backtest._elo_frames(tree_inputs(df))
    by_season = []
    for season in seasons:
        test = backtest.predict_season(frames, season, window)
        _, train = backtest._train_rows(frames, season, window)
        train = train.dropna(subset=["market_logit"])
        for set_name, features in TREE_SETS.items():
            for depth, leaf in grid:
                model = TreeModel.fit_early(train, features, depth, leaf)
                test[tree_column(set_name, depth, leaf)] = backtest._predict_or_blend(model, test)
        by_season.append(test)
    return backtest._market_games(by_season)


def stack_weight(p_blend: np.ndarray, p_tree: np.ndarray, y: np.ndarray) -> float:
    """Grid weight on the tree with the lowest log loss; a tie goes to the smaller weight."""
    return min(STACK_GRID, key=lambda w: log_loss((1 - w) * p_blend + w * p_tree, y) + STACK_TIE_PENALTY * w)


def stacked(preds: pd.DataFrame, tree_col: str) -> pd.Series:
    """Blend and tree mixed with a weight fitted on earlier seasons only."""
    result = pd.Series(np.nan, index=preds.index, dtype=float)
    for season in sorted(preds["season"].unique()):
        earlier = preds[(preds["season"] < season) & preds[tree_col].notna() & preds["home_win"].notna()]
        if earlier.empty:
            continue
        w = stack_weight(earlier["p_blend"].to_numpy(), earlier[tree_col].to_numpy(), earlier["home_win"].to_numpy())
        current = preds[preds["season"] == season]
        result.loc[current.index] = (1 - w) * current["p_blend"] + w * current[tree_col]
    return result


def evaluate_c(
    preds: pd.DataFrame, candidates: dict[str, list[str]], tune: list[int], confirm: list[int],
    cluster: list[str] | None = None
) -> list[dict]:
    """backtest.evaluate plus every variant's tune gain, confirm gain and the gap between them."""
    results = backtest.evaluate(preds, candidates, tune, confirm, cluster)
    rows = preds[preds["season"].isin(confirm)]
    for result in results:
        all_variants = []
        for variant in result["variants"]:
            confirm_gain = paired_gain(rows[variant["variant"]].to_numpy(), rows["p_blend"].to_numpy(),
                                       rows["home_win"].to_numpy())["log_loss_gain"]
            tune_gain = variant["tune"]["log_loss_gain"]
            all_variants.append({"variant": variant["variant"], "tune_gain": tune_gain,
                                 "confirm_gain": confirm_gain, "gap": tune_gain - confirm_gain})
        result["all_variants"] = all_variants
    return results


def margin_to_prob(margin: np.ndarray, sigma: float) -> np.ndarray:
    """Normal cdf of the home margin over sigma; a missing margin stays missing."""
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be positive and finite")
    return np.array([0.5 * (1 + math.erf(m / (sigma * math.sqrt(2)))) for m in np.asarray(margin, dtype=float)])


def _fold_scores(train: pd.DataFrame, features: list[str]) -> tuple[pd.Series, pd.Series]:
    """Home and away points for each training row from a model fitted on the other training seasons."""
    home = pd.Series(np.nan, index=train.index, dtype=float)
    away = home.copy()
    for season in sorted(train["season"].unique()):
        held = train["season"] == season
        home.loc[held], away.loc[held] = ScoreModel.fit(train[~held], features).predict(train[held])
    return home, away


def _miss_sigma(train: pd.DataFrame, home: pd.Series, away: pd.Series) -> float:
    miss = ((train["home_score"] - train["away_score"]) - (home - away)).to_numpy(dtype=float)
    return float(np.std(miss[np.isfinite(miss)], ddof=1))


def margin_sigma(train: pd.DataFrame, features: list[str]) -> float:
    """Spread of the home margin miss, each season scored by a model that did not see it."""
    return _miss_sigma(train, *_fold_scores(train, features))


def margin_preds(df: pd.DataFrame, seasons: list[int], window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with win chances taken from predicted score margins."""
    form = scores.add_score_features(df, EloParams())[SCORE_COLUMNS]
    frames = {params: frame.assign(**{c: form[c] for c in SCORE_COLUMNS})
              for params, frame in backtest._elo_frames(df).items()}
    by_season = []
    for season in seasons:
        test = backtest.predict_season(frames, season, window)
        _, train = backtest._train_rows(frames, season, window)
        folds, margin = {}, {}
        for name, features in (("stats", STATS_FEATURES), ("line", scores.BLEND_FEATURES)):
            folds[name] = _fold_scores(train, features)
            sigma = _miss_sigma(train, *folds[name])
            home, away = ScoreModel.fit(train, features).predict(test)
            margin[name] = (home - away, home + away)
            chance = pd.Series(margin_to_prob(home - away, sigma), index=test.index)
            test[f"p_m_{name}"] = chance.fillna(test["p_blend"])
        test["m_margin_stats"], test["m_total_stats"] = margin["stats"]
        test["m_margin_line"] = margin["line"][0]
        inputs = {
            "in_margin_stats": lambda h, a: (h - a) / MARGIN_SCALE,
            "in_total_stats": lambda h, a: (h + a - TOTAL_CENTER) / TOTAL_SCALE,
            "in_margin_line": lambda h, a: (h - a) / MARGIN_SCALE,
        }
        source = {"in_margin_stats": "stats", "in_total_stats": "stats", "in_margin_line": "line"}
        fit_rows = train.assign(**{c: f(*folds[source[c]]) for c, f in inputs.items()}).dropna(subset=["market_logit"])
        test_rows = test.assign(
            in_margin_stats=test["m_margin_stats"] / MARGIN_SCALE,
            in_total_stats=(test["m_total_stats"] - TOTAL_CENTER) / TOTAL_SCALE,
            in_margin_line=test["m_margin_line"] / MARGIN_SCALE,
        )
        for name, extra in (("stats", ["in_margin_stats"]), ("stats_total", ["in_margin_stats", "in_total_stats"]),
                            ("line", ["in_margin_line"])):
            model = LogitModel.fit(fit_rows, [*BLEND_FEATURES, *extra])
            test[f"p_m_in_{name}"] = backtest._predict_or_blend(model, test_rows)
        by_season.append(test)
    return backtest._market_games(by_season)


def explosive_net(rows: list[dict]) -> pd.DataFrame:
    """Each team's explosive-play rate minus its opponent's in the same game."""
    games: dict[str, list[tuple[int, str, float, float]]] = {}
    for i, row in enumerate(rows):
        games.setdefault(row["game_id"], []).append((i, row["team"], float(row["plays"]), float(row["explosive"])))
    result = []
    for game_id, sides in games.items():
        if len(sides) != 2 or sides[0][1] == sides[1][1]:
            continue
        if any(plays <= 0 or not math.isfinite(plays) or not math.isfinite(boom) for _, _, plays, boom in sides):
            continue
        for (index, team, plays, explosive), (_, _, opp_plays, opp_explosive) in (sides, sides[::-1]):
            result.append((index, game_id, team, explosive / plays - opp_explosive / opp_plays))
    result.sort(key=lambda row: row[0])
    return pd.DataFrame([row[1:] for row in result], columns=["game_id", "team", "net_epa"])


def explosive_preds(df: pd.DataFrame, seasons: list[int], explosive: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with a pregame explosive-play rating added to the blend."""
    differences = {f"explosive_diff_{h}": EXPLOSIVE_SCALE * epa_diff(df, explosive, h) for h in EXPLOSIVE_HALF_LIVES}
    frames = {params: frame.assign(**differences) for params, frame in backtest._elo_frames(df).items()}
    by_season = []
    for season in seasons:
        test = backtest.predict_season(frames, season, window)
        _, train = backtest._train_rows(frames, season, window)
        train = train.dropna(subset=["market_logit"])
        for h in EXPLOSIVE_HALF_LIVES:
            model = LogitModel.fit(train, [*BLEND_FEATURES, f"explosive_diff_{h}"])
            test[f"p_expl_{h}"] = backtest._predict_or_blend(model, test)
        by_season.append(test)
    return backtest._market_games(by_season)


def _by_pick_prob(week: pd.DataFrame, column: str) -> list[str]:
    ranked = week.assign(_pick=np.maximum(week[column], 1 - week[column]))
    return ranked.sort_values(["_pick", "game_id"], ascending=[False, True])["game_id"].tolist()


def _picked_right(week: pd.DataFrame) -> pd.Series:
    return pd.Series((week["p_blend"] > 0.5).to_numpy() == (week["home_win"] == 1).to_numpy(), index=week["game_id"])


def points_order(week: pd.DataFrame, order: str) -> list[str]:
    """Game ids of one week, most points first."""
    if order not in POINT_ORDERS:
        raise ValueError(f"unknown points order: {order}")
    if order == "market":
        return _by_pick_prob(week, "p_market")
    if order == "kickoff":
        return week.sort_values(["kickoff_utc", "game_id"])["game_id"].tolist()
    by_sort = _by_pick_prob(week, "p_blend")
    if order == "reverse":
        return by_sort[::-1]
    if order == "oracle":
        right = _picked_right(week)
        return [g for g in by_sort if right[g]] + [g for g in by_sort if not right[g]]
    return by_sort


def week_points(week: pd.DataFrame, order: str) -> dict:
    """Expected and actual points of one week when points run from its size down to one."""
    ids = points_order(week, order)
    points = pd.Series(range(len(ids), 0, -1), index=ids, dtype=float)
    p = week.set_index("game_id")["p_blend"].loc[ids]
    pick = np.maximum(p, 1 - p)
    right = _picked_right(week).loc[ids]
    return {"expected": float((points * pick).sum()), "actual": float(points[right].sum())}


def swap_ceiling(week: pd.DataFrame) -> float:
    """Most expected points the sheet's tie rule could give up in one week."""
    p = week["p_blend"].to_numpy()
    probs = sorted(np.maximum(p, 1 - p), reverse=True)
    total, i = 0.0, 0
    while i < len(probs) - 1:
        gap = probs[i] - probs[i + 1]
        if gap < TIE_BAND:
            total += gap
            i += 2
        else:
            i += 1
    return float(total)


def points_report(preds: pd.DataFrame) -> dict:
    """Mean expected and actual points per week for each order, and how far the sort is from each."""
    rows = []
    for (season, _), week in preds.groupby(["season", "week"], sort=True):
        row = {"season": int(season), "swap": swap_ceiling(week)}
        for name in POINT_ORDERS:
            row[name] = week_points(week, name)
        rows.append(row)

    def summary(chosen: list[dict]) -> dict:
        return {name: {"expected_per_week": float(np.mean([r[name]["expected"] for r in chosen])),
                       "actual_per_week": float(np.mean([r[name]["actual"] for r in chosen]))}
                for name in POINT_ORDERS}

    orders = summary(rows)
    for name in POINT_ORDERS:
        gap = np.array([r["sort"]["actual"] - r[name]["actual"] for r in rows])
        orders[name]["sort_minus_order_actual"] = {"mean": float(gap.mean()), "ci": list(bootstrap_ci(gap))}
    by_season = []
    for season in sorted({r["season"] for r in rows}):
        chosen = [r for r in rows if r["season"] == season]
        by_season.append({"season": season, "weeks": len(chosen), "orders": summary(chosen)})
    return {"weeks": len(rows), "orders": orders, "by_season": by_season,
            "swap_ceiling_per_week": float(np.mean([r["swap"] for r in rows]))}
