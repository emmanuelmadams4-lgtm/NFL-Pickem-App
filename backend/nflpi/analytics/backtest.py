"""Walk-forward backtest.

To test season S, every choice (Elo settings, model weights, home rate) is
made on seasons before S only. Elo is online and only sees finished games.
The market line is the closing line, so it is a benchmark, not a fair
mid-week input; the "blend" model inherits that advantage and is labeled so.
"""

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from nflpi.analytics.metrics import (
    EARLY_WEEK_END,
    bootstrap_ci,
    calibration,
    log_loss,
    paired_gain,
    pick_label,
    summarize,
    uncertainty_grade,
    upset_watch,
)
from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES, add_features, epa_diff, market_logit
from nflpi.predictions.market import DEVIG_METHODS
from nflpi.predictions.model import LogitModel

ELO_GRID = [EloParams(k=k, hfa=h) for k in (15.0, 20.0, 25.0) for h in (30.0, 48.0, 65.0)]
EPA_HALF_LIVES = (4, 8, 16)
SPLIT_HALF_LIVES = (4, 8, 16)
SPLIT_EPA_SCALE = 10
SPLIT_SR_SCALE = 20
RECENCY_HALF_LIVES = (2, 4, 8)
SPREAD_SCALE = 7
TOTAL_CENTER = 45
TOTAL_SCALE = 10
CALIBRATION_MIN = 0.01
CALIBRATION_MAX = 0.99
MODELS = ["home", "elo", "logistic", "market", "blend"]
ABLATE = ["home_qb_change", "away_qb_change"]
LABELS = {
    "home": "Always pick home team",
    "elo": "Elo ratings only",
    "logistic": "Stats model (Elo + QB + home)",
    "market": "Betting market (closing line)",
    "blend": "Stats model + market (uses closing line)",
}


def elo_frames(df: pd.DataFrame) -> dict[EloParams, pd.DataFrame]:
    base = add_features(df, ELO_GRID[0])
    frames = {}
    for params in ELO_GRID:
        e = run_elo(df, params)
        f = base.copy()
        f[["home_elo", "away_elo", "elo_prob"]] = e[["home_elo", "away_elo", "elo_prob"]]
        f["elo_diff"] = (f["home_elo"] - f["away_elo"]) / 100
        frames[params] = f
    return frames


def tune_elo(frames: dict[EloParams, pd.DataFrame], seasons: list[int]) -> EloParams:
    def loss(params: EloParams) -> float:
        f = frames[params]
        m = f["season"].isin(seasons) & f["home_win"].notna()
        return log_loss(f.loc[m, "elo_prob"].to_numpy(), f.loc[m, "home_win"].to_numpy())

    return min(ELO_GRID, key=loss)


def _train_rows(
    frames: dict[EloParams, pd.DataFrame], season: int, window: int
) -> tuple[EloParams, pd.DataFrame]:
    train_seasons = list(range(season - window, season))
    params = tune_elo(frames, train_seasons)
    frame = frames[params]
    train = frame[frame["season"].isin(train_seasons) & frame["home_win"].notna()]
    return params, train


def _predict_or_blend(model: LogitModel, test: pd.DataFrame) -> pd.Series:
    """A game missing an input keeps the blend's number."""
    return pd.Series(model.predict(test), index=test.index).fillna(test["p_blend"])


def _market_games(by_season: list[pd.DataFrame]) -> pd.DataFrame:
    preds = pd.concat(by_season, ignore_index=True)
    return preds[preds["p_market"].notna()]


def predict_season(frames: dict[EloParams, pd.DataFrame], season: int, window: int) -> pd.DataFrame:
    params, train = _train_rows(frames, season, window)
    f = frames[params]
    test = f[(f["season"] == season) & (f["game_type"] == "REG") & f["home_win"].notna()].copy()

    home_rate = train.loc[train["home_field"] == 1, "home_win"].mean()
    test["p_home"] = np.where(test["home_field"] == 1, home_rate, 0.5)
    test["p_elo"] = test["elo_prob"]
    test["p_logistic"] = LogitModel.fit(train, BASE_FEATURES).predict(test)
    test["p_market"] = test["market_prob"]
    blend = LogitModel.fit(train.dropna(subset=["market_logit"]), BLEND_FEATURES)
    has_mkt = test["market_logit"].notna()
    test["p_blend"] = test["p_logistic"]
    test.loc[has_mkt, "p_blend"] = blend.predict(test[has_mkt])
    for feat in ABLATE:  # ablations: does each extra feature add value?
        keep = [x for x in BASE_FEATURES if x != feat]
        test[f"p_without_{feat}"] = LogitModel.fit(train, keep).predict(test)
    test["elo_k"], test["elo_hfa"] = params.k, params.hfa
    return test


def inseason_blend(frames: dict[EloParams, pd.DataFrame], season: int, window: int) -> pd.Series:
    """Refit the blend before each test week using games already played."""
    params, train = _train_rows(frames, season, window)
    f = frames[params]
    test = f[(f["season"] == season) & (f["game_type"] == "REG") & f["home_win"].notna()].copy()
    preds = pd.Series(np.nan, index=test.index, dtype=float)
    for _, games in test.groupby("week", sort=False):
        has_market = games["market_logit"].notna()
        if not has_market.any():
            continue
        played = f[(f["season"] == season) & f["home_win"].notna()
                   & (f["kickoff_utc"] < games["kickoff_utc"].min())]
        model = LogitModel.fit(pd.concat([train, played]).dropna(subset=["market_logit"]), BLEND_FEATURES)
        preds.loc[games.index[has_market]] = model.predict(games[has_market])
    return preds


def candidate_preds(
    df: pd.DataFrame, seasons: list[int], window: int = 10, epa: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Score market games with the in-season blend and EPA rating candidates."""
    frames = elo_frames(df)
    if epa is not None:
        differences = {h: epa_diff(df, epa, h) for h in EPA_HALF_LIVES}
        frames = {params: frame.assign(**{f"epa_diff_{h}": diff for h, diff in differences.items()})
                  for params, frame in frames.items()}
    by_season = []
    for season in seasons:
        test = predict_season(frames, season, window)
        test["p_inseason"] = inseason_blend(frames, season, window)
        if epa is not None:
            _, train = _train_rows(frames, season, window)
            for h in EPA_HALF_LIVES:
                feature = f"epa_diff_{h}"
                model = LogitModel.fit(train.dropna(subset=["market_logit"]), [*BLEND_FEATURES, feature])
                test[f"p_epa_{h}"] = _predict_or_blend(model, test)
        by_season.append(test)
    return _market_games(by_season)


def split_preds(df: pd.DataFrame, seasons: list[int], split: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with offence, defence, and success-rate candidates."""
    differences = {
        f"{column}_diff_{h}": scale * epa_diff(
            df, split[["game_id", "team", column]].rename(columns={column: "net_epa"}), h
        )
        for h in SPLIT_HALF_LIVES
        for column, scale in (("off_epa", SPLIT_EPA_SCALE), ("def_epa", SPLIT_EPA_SCALE),
                              ("off_sr", SPLIT_SR_SCALE), ("def_sr", SPLIT_SR_SCALE))
    }
    frames = {params: frame.assign(**differences) for params, frame in elo_frames(df).items()}
    by_season = []
    for season in seasons:
        test = predict_season(frames, season, window)
        _, train = _train_rows(frames, season, window)
        train = train.dropna(subset=["market_logit"])
        for h in SPLIT_HALF_LIVES:
            epa_features = [f"off_epa_diff_{h}", f"def_epa_diff_{h}"]
            sr_features = [f"off_sr_diff_{h}", f"def_sr_diff_{h}"]
            for name, features in ((f"p_split_{h}", [*BLEND_FEATURES, *epa_features]),
                                   (f"p_split_sr_{h}", [*BLEND_FEATURES, *epa_features, *sr_features])):
                model = LogitModel.fit(train, features)
                test[name] = _predict_or_blend(model, test)
        by_season.append(test)
    return _market_games(by_season)


def idea_preds(df: pd.DataFrame, seasons: list[int], window: int = 10) -> pd.DataFrame:
    """Score eleven pregame model variants on held-out seasons."""
    columns = {f"market_logit_{method}": market_logit(df, method) for method in DEVIG_METHODS[1:]}
    columns.update({
        "spread_pts": df["spread_line"] / SPREAD_SCALE,
        "total_pts": (df["total_line"] - TOTAL_CENTER) / TOTAL_SCALE,
        "spread_per_total": (TOTAL_SCALE * df["spread_line"] / df["total_line"]).where(df["total_line"] > 0),
    })
    frames = {params: frame.assign(**columns) for params, frame in elo_frames(df).items()}
    by_season = []
    for season in seasons:
        test = predict_season(frames, season, window)
        _, train = _train_rows(frames, season, window)
        train = train.dropna(subset=["market_logit"])
        for method in DEVIG_METHODS[1:]:
            model = LogitModel.fit(train, [f"market_logit_{method}", *BASE_FEATURES])
            test[f"p_devig_{method}"] = _predict_or_blend(model, test)
        for name, extra in (("spread", ["spread_pts"]), ("total", ["total_pts"]),
                            ("both", ["spread_pts", "total_pts"]), ("ratio", ["spread_per_total"])):
            model = LogitModel.fit(train, [*BLEND_FEATURES, *extra])
            test[f"p_in_{name}"] = _predict_or_blend(model, test)
        for h in RECENCY_HALF_LIVES:
            weights = 0.5 ** ((season - 1 - train["season"]) / h)
            model = LogitModel.fit(train, BLEND_FEATURES, weights=weights)
            test[f"p_recency_{h}"] = _predict_or_blend(model, test)
        by_season.append(test)
    return _market_games(by_season)


def calibrated(preds: pd.DataFrame, method: str) -> pd.Series:
    """Calibrate each season using earlier seasons, clipping values to 1% to 99%."""
    if method not in ("platt", "isotonic"):
        raise ValueError(f"unknown calibration method: {method}")
    result = pd.Series(np.nan, index=preds.index, dtype=float)
    for season in sorted(preds["season"].unique()):
        earlier = preds[preds["season"] < season]
        current = preds[preds["season"] == season]
        if earlier.empty:
            continue
        if method == "platt":
            fit_prob = earlier["p_blend"].clip(CALIBRATION_MIN, CALIBRATION_MAX)
            test_prob = current["p_blend"].clip(CALIBRATION_MIN, CALIBRATION_MAX)
            fit = earlier.assign(blend_logit=np.log(fit_prob / (1 - fit_prob)))
            test = current.assign(blend_logit=np.log(test_prob / (1 - test_prob)))
            values = LogitModel.fit(fit, ["blend_logit"]).predict(test)
        else:
            model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            model.fit(earlier["p_blend"], earlier["home_win"])
            values = model.predict(current["p_blend"])
        result.loc[current.index] = np.clip(values, CALIBRATION_MIN, CALIBRATION_MAX)
    return result


def evaluate(
    preds: pd.DataFrame, candidates: dict[str, list[str]], tune: list[int], confirm: list[int],
    cluster: list[str] | None = None
) -> list[dict]:
    """Choose variants on tune seasons and judge them on confirm seasons."""
    if set(tune) & set(confirm):
        raise ValueError("tune and confirm seasons must not overlap")
    tune_rows = preds[preds["season"].isin(tune)]
    confirm_rows = preds[preds["season"].isin(confirm)]
    tune_clusters = tune_rows.groupby(cluster, sort=True).ngroup().to_numpy() if cluster is not None else None
    confirm_clusters = confirm_rows.groupby(cluster, sort=True).ngroup().to_numpy() if cluster is not None else None
    out = []
    for name, columns in candidates.items():
        variants = [
            {"variant": col, "tune": paired_gain(tune_rows[col].to_numpy(), tune_rows["p_blend"].to_numpy(),
                                                   tune_rows["home_win"].to_numpy(), clusters=tune_clusters)}
            for col in columns
        ]
        chosen = max(variants, key=lambda row: row["tune"]["log_loss_gain"])["variant"]
        result = paired_gain(confirm_rows[chosen].to_numpy(), confirm_rows["p_blend"].to_numpy(),
                             confirm_rows["home_win"].to_numpy(), clusters=confirm_clusters)
        out.append({"candidate": name, "variants": variants, "chosen": chosen, "confirm": result,
                    "ships": result["ships"]})
    return out


def signal_report(preds: pd.DataFrame) -> dict:
    """Count only games scored by all three recommendation benchmarks."""
    flags = np.array([upset_watch(s, m) for s, m in zip(preds["p_logistic"], preds["p_market"], strict=True)])
    market = preds["p_market"].to_numpy()
    y = preds["home_win"].to_numpy()
    flagged_dogs = flags & (market != 0.5)
    unflagged_dogs = ~flags & (market != 0.5)
    dog_wins = np.where(market < 0.5, y == 1, y == 0)
    grades = np.array([
        uncertainty_grade(abs(s - m), bool(h or a), w <= EARLY_WEEK_END)[0]
        for s, m, h, a, w in zip(
            preds["p_logistic"], preds["p_market"], preds["home_qb_change"],
            preds["away_qb_change"], preds["week"], strict=True
        )
    ])
    correct = (preds["p_blend"].to_numpy() > 0.5) == (y == 1)
    pick_prob = np.maximum(preds["p_blend"].to_numpy(), 1 - preds["p_blend"].to_numpy())
    n = len(preds)
    by_grade = {}
    for grade in ("low", "moderate", "high"):
        mask = grades == grade
        by_grade[grade] = {
            "games": int(mask.sum()),
            "share": float(mask.sum() / n),
            "correct": int(correct[mask].sum()),
            "accuracy": float(correct[mask].mean()) if mask.any() else None,
        }
    by_band = {}
    for label, lo, hi in (("below 60%", 0.5, 0.6), ("60 to 70%", 0.6, 0.7), ("70% and above", 0.7, 1.0)):
        band = (pick_prob >= lo) & (pick_prob < hi if hi < 1 else pick_prob <= hi)
        by_band[label] = {
            grade: {"games": int(mask.sum()), "accuracy": float(correct[mask].mean()) if mask.any() else None}
            for grade in ("low", "moderate", "high")
            for mask in [band & (grades == grade)]
        }
    return {
        "games": n,
        "upset_flagged": int(flags.sum()),
        "upset_flag_rate": float(flags.mean()),
        "flagged_underdogs": int(flagged_dogs.sum()),
        "flagged_underdog_wins": int((flagged_dogs & dog_wins).sum()),
        "flagged_underdog_win_rate": float(dog_wins[flagged_dogs].mean()) if flagged_dogs.any() else None,
        "unflagged_underdogs": int(unflagged_dogs.sum()),
        "unflagged_underdog_wins": int((unflagged_dogs & dog_wins).sum()),
        "unflagged_underdog_win_rate": float(dog_wins[unflagged_dogs].mean()) if unflagged_dogs.any() else None,
        "grades": by_grade,
        "probability_bands": by_band,
    }


def label_report(preds: pd.DataFrame) -> list[dict]:
    p = preds["p_blend"].to_numpy()
    y = preds["home_win"].to_numpy()
    labels = np.array([pick_label(max(prob, 1 - prob)) for prob in p])
    correct = (p > 0.5) == (y == 1)
    return [
        {"label": label, "games": int(mask.sum()), "share": float(mask.mean()) if len(mask) else 0.0,
         "hit_rate": float(correct[mask].mean()) if mask.any() else None}
        for label in ("coin_flip", "tough_matchup", "easy_pick")
        for mask in [labels == label]
    ]


def run_backtest(df: pd.DataFrame, seasons: list[int], window: int = 10) -> dict:
    frames = elo_frames(df)
    preds = pd.concat([predict_season(frames, s, window) for s in seasons], ignore_index=True)
    # Compare every model on the same games: those with a market line.
    preds = preds[preds["p_market"].notna()]
    y = preds["home_win"].to_numpy()

    models = []
    for m in MODELS:
        p = preds[f"p_{m}"].to_numpy()
        models.append({"model": m, "label": LABELS[m], **summarize(p, y)})

    ablations = []
    base_ll = log_loss(preds["p_logistic"].to_numpy(), y)
    for feat in ABLATE:
        ll = log_loss(preds[f"p_without_{feat}"].to_numpy(), y)
        ablations.append({"feature": feat, "log_loss_without": ll, "log_loss_gain": ll - base_ll})

    by_season = []
    for s, g in preds.groupby("season"):
        yy = g["home_win"].to_numpy()
        row = {"season": int(s), "n": len(g)}
        for m in MODELS:
            row[m] = float(np.mean((g[f"p_{m}"].to_numpy() > 0.5) == (yy == 1)))
        by_season.append(row)

    comparisons = []
    correct = {m: ((preds[f"p_{m}"].to_numpy() > 0.5) == (y == 1)).astype(float) for m in MODELS}
    for a, b in (("logistic", "market"), ("blend", "market"), ("logistic", "elo"), ("logistic", "home")):
        diff = correct[a] - correct[b]
        lo, hi = bootstrap_ci(diff)
        comparisons.append(
            {"a": a, "b": b, "accuracy_diff": float(diff.mean()), "ci": [lo, hi], "significant": lo > 0 or hi < 0}
        )

    fav_split = []
    market_fav_home = preds["p_market"].to_numpy() > 0.5
    for m in MODELS:
        picks_home = preds[f"p_{m}"].to_numpy() > 0.5
        agrees = picks_home == market_fav_home
        ok = correct[m]
        fav_split.append(
            {
                "model": m,
                "picked_favorite": int(agrees.sum()),
                "favorite_accuracy": float(ok[agrees].mean()) if agrees.any() else None,
                "picked_underdog": int((~agrees).sum()),
                "underdog_accuracy": float(ok[~agrees].mean()) if (~agrees).any() else None,
            }
        )

    return {
        "seasons": [int(s) for s in seasons],
        "games": int(len(preds)),
        "models": models,
        "comparisons": comparisons,
        "ablations": ablations,
        "by_season": by_season,
        "calibration": {m: calibration(preds[f"p_{m}"].to_numpy(), y) for m in ("logistic", "blend", "market")},
        "favorite_split": fav_split,
        "labels": label_report(preds),
        "signals": signal_report(preds),
        "signals_2012_2021": signal_report(preds[preds["season"].between(2012, 2021)])
        if any(2012 <= s <= 2021 for s in seasons)
        else None,
        "labels_2012_2021": label_report(preds[preds["season"].between(2012, 2021)])
        if any(2012 <= s <= 2021 for s in seasons)
        else None,
        "signals_2022_2025": signal_report(preds[preds["season"].between(2022, 2025)])
        if any(2022 <= s <= 2025 for s in seasons)
        else None,
        "labels_2022_2025": label_report(preds[preds["season"].between(2022, 2025)])
        if any(2022 <= s <= 2025 for s in seasons)
        else None,
        "elo_settings": sorted({(float(k), float(h)) for k, h in zip(preds["elo_k"], preds["elo_hfa"], strict=True)}),
    }
