"""Simulator bench (step 18c section 2): tune on 2012-2021, confirm once on 2022-2025, walk-forward throughout."""

import csv
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from nflpi.analytics import metrics
from nflpi.analytics.backtest import candidate_preds
from nflpi.ingestion import nflverse
from nflpi.picks import home_spread_from_nflverse
from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import games_frame
from nflpi.predictions.scores import STATS_FEATURES, ScoreModel, add_score_features
from nflpi.sim import DISTRIBUTIONS, SimParams, TeamFeatures, keys, learn_params, simulate_game

MIN_TRAIN_SEASON = 2004
WINDOW = 10
TUNE_SEASONS = list(range(2012, 2022))
CONFIRM_SEASONS = list(range(2022, 2026))
SOURCES = ("football_only", "market_informed")
LEVELS = (0.5, 0.8, 0.95)
BASE_SEED = 20261013
N_SIMULATIONS = 10_000
KEY_ALPHAS = (1.0, 0.9, 0.8, 0.75, 0.5)
N_BOOT = 2000
ALPHA_RULE = ("largest alpha whose cover-Brier, over-Brier and CRPS paired-bootstrap 95% intervals versus "
              "paired_residual have a lower end at or below zero for both sources; 0.0 if none")
PREFIX = {"football_only": "fb_", "market_informed": "mk_"}
TABLE_COLUMNS = [
    "game_id", "season", "week", "kickoff_utc", "game_type", "home_team", "away_team", "home_score", "away_score",
    "overtime", "neutral_site", "spread_line", "total_line", "fb_home", "fb_away", "mk_home", "mk_away", "home_win",
]
EXPECTED_COLUMNS = ["fb_home", "fb_away", "mk_home", "mk_away"]
DEFAULT_RULE = ("lowest pooled mean of CRPS(margin)+CRPS(total) over the tuning seasons and both sources; "
                "ties to the earlier distribution")
SOURCES_NOTE = (
    "market_informed variants are priced at the closing line's own score, so cover and over probabilities sit near "
    "50 percent by construction; they are a reference, not an independent discovery."
)
LARGEST_GAPS = 5
WIN_GAP_FLAG = 0.10


# --- data -----------------------------------------------------------------------------------------

def load_games(rows: list[dict[str, str]]) -> pd.DataFrame:
    games = nflverse.parse_games(rows, 2002)
    for g in games:
        g["home_ml"], g["away_ml"] = g.pop("_home_ml"), g.pop("_away_ml")
        g["spread_line"], g["total_line"] = g.pop("_spread"), g.pop("_total")
    frame = games_frame(games)
    raw = {r["game_id"]: r.get("overtime", "") for r in rows}
    frame["overtime"] = [0 if raw[g] in ("", "NA") else int(float(raw[g])) for g in frame["game_id"]]
    return frame


def _expected_points(frame: pd.DataFrame) -> pd.DataFrame:
    """Football-only expected points per season, fit only on the WINDOW seasons before it."""
    out = frame.assign(fb_home=np.nan, fb_away=np.nan)
    for season in sorted(s for s in frame["season"].unique() if s >= MIN_TRAIN_SEASON):
        train = frame[frame["season"].between(season - WINDOW, season - 1)]
        try:
            model = ScoreModel.fit(train, STATS_FEATURES)
        except ValueError:
            continue  # too few training rows: skipped, not guessed
        test = frame["season"] == season
        out.loc[test, "fb_home"], out.loc[test, "fb_away"] = model.predict(frame[test])
    return out


def build_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Eligible games: regular-season finals with scores, both lines and finite positive expected points."""
    t = _expected_points(add_score_features(frame, EloParams()))
    t["mk_home"], t["mk_away"] = t["implied_home"], t["implied_away"]
    t["home_win"] = np.select([t["home_score"] > t["away_score"], t["home_score"] < t["away_score"]], [1.0, 0.0], 0.5)
    ok = (t["game_type"] == "REG") & (t["status"] == "final") & t["home_score"].notna() & t["away_score"].notna()
    ok &= np.isfinite(t[["spread_line", "total_line"]].astype(float)).all(axis=1)
    values = t[EXPECTED_COLUMNS].astype(float)
    ok &= np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)
    out = t.loc[ok, TABLE_COLUMNS]
    return out.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def learn_for_season(table: pd.DataFrame, season: int, source: str) -> SimParams:
    window = table[table["season"].between(max(MIN_TRAIN_SEASON, season - WINDOW), season - 1)]
    p = PREFIX[source]
    return learn_params(
        mu_a=window[f"{p}home"].to_numpy(float), mu_b=window[f"{p}away"].to_numpy(float),
        score_a=window["home_score"].to_numpy(), score_b=window["away_score"].to_numpy(),
        overtime=window["overtime"].to_numpy(), seasons=window["season"].to_numpy(), target_season=season,
    )


# --- scoring --------------------------------------------------------------------------------------

def crps(samples: np.ndarray, actual: float) -> float:
    """Sample CRPS: mean|x-y| - 0.5*E|X-X'| (V-statistic over the sorted samples)."""
    x = np.sort(np.asarray(samples, dtype=float))
    n = len(x)
    spread = 2 / n**2 * float(np.sum((2 * np.arange(1, n + 1) - n - 1) * x))
    return float(np.mean(np.abs(x - actual)) - 0.5 * spread)


def pick_default(scores: dict[str, float]) -> str:
    return min(scores, key=lambda d: (scores[d], DISTRIBUTIONS.index(d)))


def _nopush(p_win: float | None, p_push: float | None) -> float:
    if p_win is None or p_push is None or p_push >= 1:
        return float("nan")
    return p_win / (1 - p_push)


def _game_row(game, source: str, distribution: str, params: SimParams, n: int, base_seed: int) -> dict:
    p = PREFIX[source]
    res = simulate_game(
        TeamFeatures(getattr(game, f"{p}home")), TeamFeatures(getattr(game, f"{p}away")), n_simulations=n,
        params=params, seed=zlib.crc32(game.game_id.encode()) ^ base_seed,
        spread=home_spread_from_nflverse(game.spread_line), total=game.total_line,
        neutral_site=bool(game.neutral_site), distribution=distribution,
    )
    margin, points = res.a_score - res.b_score, res.a_score + res.b_score
    actual_margin, actual_total = game.home_score - game.away_score, game.home_score + game.away_score
    row = {
        "game_id": game.game_id, "season": int(game.season), "source": source, "distribution": distribution,
        "crps_margin": crps(margin, actual_margin), "crps_total": crps(points, actual_total),
        "mean_margin": res.expected_margin, "mean_total": res.expected_total,
        "p_win_half": res.p_a_win + res.p_tie / 2, "p_tie": res.p_tie,
        "p_cover_nopush": _nopush(res.p_a_cover, res.p_spread_push),
        "p_over_nopush": _nopush(res.p_over, res.p_total_push),
        "p_abs3": float(np.mean(np.abs(margin) == 3)), "p_abs7": float(np.mean(np.abs(margin) == 7)),
    }
    for level in LEVELS:
        pct = int(level * 100)
        (m_lo, m_hi), (t_lo, t_hi) = res.margin_intervals[level], res.total_intervals[level]
        row[f"margin_in_{pct}"] = int(m_lo <= actual_margin <= m_hi)
        row[f"total_in_{pct}"] = int(t_lo <= actual_total <= t_hi)
    return row


def simulate_table(
    table: pd.DataFrame, seasons: list[int], *, distributions=DISTRIBUTIONS, n_simulations: int = N_SIMULATIONS,
    base_seed: int = BASE_SEED,
) -> pd.DataFrame:
    rows = []
    for season in seasons:
        games = list(table[table["season"] == season].itertuples(index=False))
        for source in SOURCES:
            params = learn_for_season(table, season, source)
            rows += [_game_row(g, source, d, params, n_simulations, base_seed) for g in games for d in distributions]
    return pd.DataFrame(rows)


# --- tune -----------------------------------------------------------------------------------------

def _pooled(rows: pd.DataFrame) -> dict[str, float]:
    both = rows["crps_margin"] + rows["crps_total"]
    return {d: float(both[rows["distribution"] == d].mean()) for d in DISTRIBUTIONS}


def tune(table: pd.DataFrame, *, seasons=TUNE_SEASONS, n_simulations: int = N_SIMULATIONS,
         base_seed: int = BASE_SEED) -> dict:
    if any(s >= CONFIRM_SEASONS[0] for s in seasons):
        raise ValueError(f"tuning may not touch the confirm seasons ({CONFIRM_SEASONS[0]} on)")
    table = table[table["season"] < CONFIRM_SEASONS[0]]
    rows = simulate_table(table, list(seasons), n_simulations=n_simulations, base_seed=base_seed)
    pooled = _pooled(rows)
    return {
        "seasons": [int(s) for s in seasons], "n_simulations": n_simulations, "games": int(rows["game_id"].nunique()),
        "pooled_crps": pooled, "by_source": {s: _pooled(rows[rows["source"] == s]) for s in SOURCES},
        "default": pick_default(pooled), "rule": DEFAULT_RULE,
    }


def write_tune(path, result: dict) -> None:
    with open(path, "w") as f:
        json.dump(result, f, indent=2)


def live_blend(frame: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    return candidate_preds(frame, seasons)[["game_id", "p_blend", "p_market", "home_win"]]


# --- metric helpers -------------------------------------------------------------------------------

def interval_coverage(flags: np.ndarray) -> float:
    return float(np.mean(flags))


def reliability_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict]:
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    slot = np.minimum((p * bins).astype(int), bins - 1)
    return [
        {"lo": b / bins, "hi": (b + 1) / bins, "n": int(m.sum()), "mean_pred": float(p[m].mean()),
         "observed": float(y[m].mean())}
        for b in range(bins) if (m := slot == b).any()
    ]


def brier_vs_flat(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    return metrics.brier(np.asarray(p, dtype=float), np.asarray(y, dtype=float)), 0.25


def key_number_rate(margins: np.ndarray, k: int) -> float:
    return float(np.mean(np.abs(np.asarray(margins)) == k))


def win_gap(p_sim: np.ndarray, p_blend: np.ndarray) -> dict:
    gap = np.abs(np.asarray(p_sim, dtype=float) - np.asarray(p_blend, dtype=float))
    return {"mean_abs": float(gap.mean()), "max_abs": float(gap.max()), "n_above_0.10": int((gap > WIN_GAP_FLAG).sum())}


# --- confirm --------------------------------------------------------------------------------------

def _calibration(p: np.ndarray, y: np.ndarray) -> dict:
    keep = np.isfinite(p)
    brier, flat = brier_vs_flat(p[keep], y[keep])
    return {"table": reliability_table(p[keep], y[keep]), "brier": brier, "brier_flat_half": flat}


def _win_block(v: pd.DataFrame) -> tuple[dict, dict]:
    both = v.dropna(subset=["p_blend"])
    gap = both["p_win_half"].to_numpy() - both["p_blend"].to_numpy()
    top = both.assign(gap=np.abs(gap)).nlargest(LARGEST_GAPS, "gap")
    gaps = win_gap(both["p_win_half"].to_numpy(), both["p_blend"].to_numpy())
    gaps["largest"] = [
        {"game_id": r.game_id, "p_sim": float(r.p_win_half), "p_blend": float(r.p_blend), "gap": float(r.gap)}
        for r in top.itertuples()
    ]
    d = both[both["home_win"] != 0.5]
    p, pb, y = d["p_win_half"].to_numpy(), d["p_blend"].to_numpy(), d["home_win"].to_numpy()
    paired = metrics.paired_gain(p, pb, y)
    win = {
        "games": int(len(d)), "excludes_ties": True, "log_loss": metrics.log_loss(p, y),
        "accuracy": metrics.accuracy(p, y), "blend_log_loss": metrics.log_loss(pb, y),
        "market_log_loss": metrics.log_loss(d["p_market"].to_numpy(), y), "accuracy_blend": metrics.accuracy(pb, y),
        "log_loss_gain_vs_blend": paired["log_loss_gain"], "log_loss_gain_ci": paired["log_loss_gain_ci"],
        "accuracy_diff_vs_blend": paired["accuracy_diff"],
    }
    return gaps, win


def _variant(v: pd.DataFrame, source: str, distribution: str, default: str) -> dict:
    spread = home_spread_from_nflverse(v["spread_line"].to_numpy(float))
    margin = (v["home_score"] - v["away_score"]).to_numpy(float)
    total = (v["home_score"] + v["away_score"]).to_numpy(float)
    cover = np.where(margin + spread == 0, np.nan, (margin + spread > 0).astype(float))
    line = v["total_line"].to_numpy(float)
    over = np.where(total == line, np.nan, (total > line).astype(float))
    cal = {}
    for kind, p, y in (("cover", v["p_cover_nopush"], cover), ("over", v["p_over_nopush"], over)):
        keep = np.isfinite(y)  # pushes excluded
        cal[kind] = _calibration(p.to_numpy(float)[keep], y[keep])
    gaps, win = _win_block(v)
    err_m, err_t = v["mean_margin"].to_numpy() - margin, v["mean_total"].to_numpy() - total
    return {
        "games": int(len(v)), "source": source, "distribution": distribution, "is_default": distribution == default,
        "margin_mae": float(np.abs(err_m).mean()), "margin_rmse": float(np.sqrt((err_m**2).mean())),
        "total_mae": float(np.abs(err_t).mean()), "total_rmse": float(np.sqrt((err_t**2).mean())),
        "coverage": {kind: {str(level): interval_coverage(v[f"{kind}_in_{int(level * 100)}"]) for level in LEVELS}
                     for kind in ("margin", "total")},
        "calibration": cal,
        "tie_rate": {"sim": float(v["p_tie"].mean()), "real": float((margin == 0).mean())},
        "key_numbers": {str(k): {"sim": float(v[f"p_abs{k}"].mean()), "real": key_number_rate(margin, k)}
                        for k in (3, 7)},
        "win_gap_vs_blend": gaps, "win_probability": win,
    }


def confirm(
    table: pd.DataFrame, blend: pd.DataFrame, *, tune_path, out_path, seasons=CONFIRM_SEASONS,
    n_simulations: int = N_SIMULATIONS, base_seed: int = BASE_SEED,
) -> dict:
    default = json.loads(Path(tune_path).read_text())["default"]
    with open(out_path, "x") as f:  # opened before the expensive run: the confirm happens once
        try:
            rows = simulate_table(table, list(seasons), n_simulations=n_simulations, base_seed=base_seed)
            cols = ["game_id", "home_score", "away_score", "spread_line", "total_line", "home_win"]
            rows = rows.merge(table[cols], on="game_id").merge(
                blend[["game_id", "p_blend", "p_market"]], on="game_id", how="left")
            groups = rows.groupby(["source", "distribution"], sort=False)
            variants = [_variant(g, s, d, default) for (s, d), g in groups]
            report = {
                "seasons": [int(s) for s in seasons], "n_simulations": n_simulations, "default_distribution": default,
                "sources_note": SOURCES_NOTE, "games": int(rows["game_id"].nunique()), "variants": variants,
            }
            json.dump(report, f, indent=1, allow_nan=False)
        except BaseException:
            Path(out_path).unlink(missing_ok=True)
            raise
    return report


# --- key-number tune and confirm ------------------------------------------------------------------

def pick_alpha(by_alpha: dict[str, dict[str, dict]]) -> float:
    """Choose the strongest weight with no metric significantly worse for either source."""
    for alpha in sorted((float(a) for a in by_alpha), reverse=True):
        if all(by_alpha[str(alpha)][source][metric][1] <= 0
               for source in SOURCES for metric in ("cover_brier_ci", "over_brier_ci", "crps_ci")):
            return alpha
    return 0.0


def _key_game_row(game, source: str, variant: str, a: np.ndarray, b: np.ndarray, pit_u: float) -> dict:
    margin, points = a - b, a + b
    actual_margin, actual_total = game.home_score - game.away_score, game.home_score + game.away_score
    spread = home_spread_from_nflverse(game.spread_line)
    cover_edge = margin + spread
    cover_actual = actual_margin + spread
    total_edge = points - game.total_line
    over_actual = actual_total - game.total_line
    row = {
        "game_id": game.game_id, "source": source, "variant": variant,
        "key3": float(np.mean(np.abs(margin) == 3)), "key7": float(np.mean(np.abs(margin) == 7)),
        "crps": crps(margin, actual_margin) + crps(points, actual_total),
        "p_cover": _nopush(float(np.mean(cover_edge > 0)), float(np.mean(cover_edge == 0))),
        "p_over": _nopush(float(np.mean(total_edge > 0)), float(np.mean(total_edge == 0))),
        "y_cover": float(cover_actual > 0) if cover_actual != 0 else float("nan"),
        "y_over": float(over_actual > 0) if over_actual != 0 else float("nan"),
        "margin_sd": float(margin.std()),
        "pit": float(np.mean(margin < actual_margin) + pit_u * np.mean(margin == actual_margin)),
        "real3": float(abs(actual_margin) == 3), "real7": float(abs(actual_margin) == 7),
    }
    for level in LEVELS:
        lo = np.quantile(margin, (1 - level) / 2, method="lower")
        hi = np.quantile(margin, (1 + level) / 2, method="higher")
        row[f"in_{level}"] = float(lo <= actual_margin <= hi)
    return row


def _key_rows(
    table: pd.DataFrame, seasons: list[int], alphas: tuple[float, ...], n_simulations: int, base_seed: int,
) -> pd.DataFrame:
    rows = []
    for season in seasons:
        games = list(table[table["season"] == season].itertuples(index=False))
        for source in SOURCES:
            params = learn_for_season(table, season, source)
            p = PREFIX[source]
            for game in games:
                seed = zlib.crc32(game.game_id.encode()) ^ base_seed
                res = simulate_game(
                    TeamFeatures(getattr(game, f"{p}home")), TeamFeatures(getattr(game, f"{p}away")),
                    n_simulations=n_simulations, params=params, seed=seed,
                    spread=home_spread_from_nflverse(game.spread_line), total=game.total_line,
                    neutral_site=bool(game.neutral_site), distribution="paired_residual",
                )
                pit_u = float(np.random.default_rng([seed, 999]).random())
                rows.append(_key_game_row(game, source, "baseline", res.a_score, res.b_score, pit_u))
                for alpha in alphas:
                    a, b = keys.key_weight(
                        res.a_score, res.b_score, np.random.default_rng([seed, round(alpha * 100)]),
                        params.key_ratio, alpha,
                    )
                    rows.append(_key_game_row(game, source, str(alpha), a, b, pit_u))
    return pd.DataFrame(rows)


def _key_block(rows: pd.DataFrame) -> dict:
    block = {
        "key3": float(rows["key3"].mean()), "key7": float(rows["key7"].mean()),
        "crps": float(rows["crps"].mean()), "margin_sd": float(rows["margin_sd"].mean()),
    }
    for kind in ("cover", "over"):
        good = rows[[f"p_{kind}", f"y_{kind}"]].dropna()
        block[f"{kind}_brier"] = float(np.mean((good[f"p_{kind}"] - good[f"y_{kind}"]) ** 2))
    block["pit_coverage"] = {str(level): float(np.mean(np.abs(rows["pit"] - 0.5) <= level / 2))
                             for level in LEVELS}
    block["coverage"] = {str(level): float(rows[f"in_{level}"].mean()) for level in LEVELS}
    return block


def _key_ci(base: pd.DataFrame, other: pd.DataFrame, kind: str, n_boot: int, base_seed: int) -> list[float]:
    paired = base.merge(other, on="game_id", suffixes=("_base", "_other"))
    if kind == "crps":
        delta = paired["crps_other"].to_numpy() - paired["crps_base"].to_numpy()
    else:
        y = paired[f"y_{kind}_base"].to_numpy()
        delta = ((paired[f"p_{kind}_other"].to_numpy() - y) ** 2
                 - (paired[f"p_{kind}_base"].to_numpy() - y) ** 2)
        delta = delta[np.isfinite(delta)]  # real or simulated pushes are not scored
    rng = np.random.default_rng(base_seed)
    means = delta[rng.integers(0, len(delta), size=(n_boot, len(delta)))].mean(axis=1)
    return [float(delta.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def _key_comparison(rows: pd.DataFrame, source: str, variant: str, n_boot: int, base_seed: int) -> dict:
    base = rows[(rows["source"] == source) & (rows["variant"] == "baseline")]
    other = rows[(rows["source"] == source) & (rows["variant"] == variant)]
    block = _key_block(other)
    block.update({f"{kind}_ci": _key_ci(base, other, kind.replace("_brier", ""), n_boot, base_seed)
                  for kind in ("cover_brier", "over_brier", "crps")})
    return block


def keys_tune(
    table: pd.DataFrame, *, seasons=TUNE_SEASONS, alphas=KEY_ALPHAS, n_simulations: int = N_SIMULATIONS,
    base_seed: int = BASE_SEED, n_boot: int = N_BOOT,
) -> dict:
    if any(s >= CONFIRM_SEASONS[0] for s in seasons):
        raise ValueError(f"keys tuning may not touch the confirm seasons ({CONFIRM_SEASONS[0]} on)")
    table = table[table["season"] < CONFIRM_SEASONS[0]]
    rows = _key_rows(table, list(seasons), tuple(alphas), n_simulations, base_seed)
    baseline = {source: _key_block(rows[(rows["source"] == source) & (rows["variant"] == "baseline")])
                for source in SOURCES}
    by_alpha = {str(alpha): {source: _key_comparison(rows, source, str(alpha), n_boot, base_seed)
                             for source in SOURCES} for alpha in alphas}
    real = {
        source: {str(k): float(rows[(rows["source"] == source) & (rows["variant"] == "baseline")][f"real{k}"].mean())
                 for k in (3, 7)}
        for source in SOURCES
    }
    return {
        "seasons": [int(s) for s in seasons], "n_simulations": n_simulations, "n_boot": n_boot,
        "games": int(rows["game_id"].nunique()), "real": real, "baseline": baseline, "by_alpha": by_alpha,
        "alpha": pick_alpha(by_alpha), "rule": ALPHA_RULE,
    }


def keys_confirm(
    table: pd.DataFrame, *, keys_path, out_path, seasons=CONFIRM_SEASONS,
    n_simulations: int = N_SIMULATIONS, base_seed: int = BASE_SEED, n_boot: int = N_BOOT,
) -> dict:
    alpha = float(json.loads(Path(keys_path).read_text())["alpha"])
    with open(out_path, "x") as f:
        try:
            rows = _key_rows(table, list(seasons), (alpha,), n_simulations, base_seed)
            by_source = {}
            for source in SOURCES:
                base = rows[(rows["source"] == source) & (rows["variant"] == "baseline")]
                weighted = _key_comparison(rows, source, str(alpha), n_boot, base_seed)
                by_source[source] = {
                    "real": {str(k): float(base[f"real{k}"].mean()) for k in (3, 7)},
                    "baseline": _key_block(base),
                    "key_weighted": {k: v for k, v in weighted.items() if not k.endswith("_ci")},
                    **{k: v for k, v in weighted.items() if k.endswith("_ci")},
                }
            report = {
                "seasons": [int(s) for s in seasons], "alpha": alpha, "games": int(rows["game_id"].nunique()),
                "n_simulations": n_simulations, "n_boot": n_boot, "by_source": by_source,
            }
            json.dump(report, f, indent=1, allow_nan=False)
        except BaseException:
            Path(out_path).unlink(missing_ok=True)
            raise
    return report


# --- command line ---------------------------------------------------------------------------------

def _read(games_csv: str) -> list[dict[str, str]]:
    with open(games_csv, newline="") as f:
        return list(csv.DictReader(f))


def main(argv: list[str]) -> None:
    command, games_csv, out_dir = argv
    frame = load_games(_read(games_csv))
    table = build_table(frame)
    tune_path, out_path = Path(out_dir) / "tune-result.json", Path(out_dir) / "confirm-result.json"
    if command == "tune":
        result = tune(table)
        write_tune(tune_path, result)
        print(f"TUNE {result['seasons'][0]}-{result['seasons'][-1]}: {result['games']} games")
        for d, score in result["pooled_crps"].items():
            print(f"  {d:22s} CRPS(margin)+CRPS(total) {score:.4f}")
        print(f"default: {result['default']}   ({result['rule']})")
    elif command == "confirm":
        report = confirm(table, live_blend(frame, CONFIRM_SEASONS), tune_path=tune_path, out_path=out_path)
        print(f"CONFIRM {report['seasons'][0]}-{report['seasons'][-1]}: {report['games']} games, "
              f"default {report['default_distribution']}")
        for v in report["variants"]:
            w = v["win_probability"]
            print(f"  {v['source']:16s} {v['distribution']:22s} margin MAE {v['margin_mae']:.3f} "
                  f"total MAE {v['total_mae']:.3f} win log-loss gain vs blend {w['log_loss_gain_vs_blend']:+.4f}")
        print(report["sources_note"])
    elif command == "keys-tune":
        result = keys_tune(table)
        write_tune(Path(out_dir) / "keys-tune.json", result)
        for source in SOURCES:
            print(f"KEYS TUNE {source}: real 3/7 {result['real'][source]['3']:.3f}/{result['real'][source]['7']:.3f}")
            for label, block in [("baseline", result["baseline"][source])] + [
                (str(alpha), result["by_alpha"][str(alpha)][source]) for alpha in KEY_ALPHAS
            ]:
                print(f"  {label:10s} 3/7 {block['key3']:.3f}/{block['key7']:.3f} "
                      f"cover {block['cover_brier']:.4f} over {block['over_brier']:.4f} CRPS {block['crps']:.3f}")
        print(f"alpha: {result['alpha']} ({result['rule']})")
    elif command == "keys-confirm":
        report = keys_confirm(table, keys_path=Path(out_dir) / "keys-tune.json",
                              out_path=Path(out_dir) / "keys-confirm.json")
        for source, result in report["by_source"].items():
            print(f"KEYS CONFIRM {source}: real 3/7 {result['real']['3']:.3f}/{result['real']['7']:.3f}")
            for label in ("baseline", "key_weighted"):
                block = result[label]
                print(f"  {label:12s} 3/7 {block['key3']:.3f}/{block['key7']:.3f} "
                      f"cover {block['cover_brier']:.4f} over {block['over_brier']:.4f} CRPS {block['crps']:.3f}")
    else:
        raise SystemExit("usage: python -m nflpi.analytics.sim_backtest "
                         "tune|confirm|keys-tune|keys-confirm <games.csv> <out_dir>")


if __name__ == "__main__":
    main(sys.argv[1:])
