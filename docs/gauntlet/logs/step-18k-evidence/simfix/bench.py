"""Double-count fix bench: current pool vs (1) centred pool vs (2) in-sample pool. Public nflverse rows before
2026-10-15 only (D72). No database, no paid call. usage: bench.py games.csv out.json"""
import csv
import dataclasses
import json
import sys

import numpy as np
import pandas as pd

from nflpi.analytics import metrics, run_check as rc, sim_backtest as sb
from nflpi.picks import home_spread_from_nflverse
from nflpi.predictions import engine
from nflpi.predictions.elo import EloParams
from nflpi.predictions.scores import STATS_FEATURES, ScoreModel, add_score_features
sys.path.insert(0, __import__("os").path.dirname(__file__))
from params_old import learn_params as old_learn_params  # the simulator at fd86c67

BENCH = [2022, 2023, 2024, 2025]
CHECK = [2024, 2025, 2026]
SRC = "football_only"
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["gameday"] < "2026-10-15"]
frame = sb.load_games(rows)
table = sb.build_table(frame)
feat = add_score_features(frame, EloParams())


def window(season):
    return table[table["season"].between(max(sb.MIN_TRAIN_SEASON, season - sb.WINDOW), season - 1)]


def params_for(season, variant):
    if variant == "centred":
        return sb.learn_for_season(table, season, SRC)  # the code under test
    w = window(season)
    mu_a, mu_b = w["fb_home"].to_numpy(float), w["fb_away"].to_numpy(float)
    if variant == "in_sample":
        model = ScoreModel.fit(feat[feat["season"].between(season - sb.WINDOW, season - 1)], STATS_FEATURES)
        mu_a, mu_b = model.predict(feat.set_index("game_id").loc[w["game_id"]].reset_index())
    return old_learn_params(mu_a, mu_b, w["home_score"].to_numpy(), w["away_score"].to_numpy(),
                            w["overtime"].to_numpy(), w["season"].to_numpy(), season)


VARIANTS = ("current", "centred", "in_sample")
P = {(s, v): params_for(s, v) for s in sorted(set(BENCH + CHECK)) for v in VARIANTS}
pool_means = {f"{s}/{v}": {"margin": float(np.mean(p.residual_a - p.residual_b)),
                           "total": float(np.mean(p.residual_a + p.residual_b))} for (s, v), p in P.items()}

# --- bench 2022-2025 -------------------------------------------------------------------------------
per = {}
for v in VARIANTS:
    out = []
    for s in BENCH:
        out += [sb._game_row(g, SRC, "paired_residual", P[(s, v)], sb.N_SIMULATIONS, sb.BASE_SEED)
                for g in table[table["season"] == s].itertuples(index=False)]
    per[v] = pd.DataFrame(out).merge(table[["game_id", "week", "home_score", "away_score", "spread_line",
                                            "total_line", "home_win", "fb_home", "fb_away"]], on="game_id")
base = per["current"]
margin = (base.home_score - base.away_score).to_numpy(float)
total = (base.home_score + base.away_score).to_numpy(float)
spread = home_spread_from_nflverse(base.spread_line.to_numpy(float))
cover = np.where(margin + spread == 0, np.nan, (margin + spread > 0).astype(float))
over = np.where(total == base.total_line, np.nan, (total > base.total_line).astype(float))
clusters = (base.season.astype(str) + "-" + base.week.astype(str)).to_numpy()


def ci(x, cl=None):
    return [round(float(c), 4) for c in metrics.bootstrap_ci(np.asarray(x, float), clusters=cl)]


RNG_REPS = 2000


def closeness_gain(old, new, target, cl):
    """Week-cluster paired bootstrap of |old - target| - |new - target| for a mean (> 0: new is closer)."""
    old, new = np.asarray(old, float), np.asarray(new, float)
    keys, inv = np.unique(cl, return_inverse=True)
    rng = np.random.default_rng(7)
    so, sn, cnt = (np.bincount(inv, w, len(keys)) for w in (old, new, np.ones_like(old)))
    point = abs(old.mean() - target) - abs(new.mean() - target)
    draws = []
    for _ in range(RNG_REPS):
        pick = np.bincount(rng.integers(0, len(keys), len(keys)), minlength=len(keys))
        n = (pick * cnt).sum()
        draws.append(abs((pick * so).sum() / n - target) - abs((pick * sn).sum() / n - target))
    return {"value": round(float(point), 4), "ci": [round(float(x), 4) for x in np.quantile(draws, [0.025, 0.975])]}


def measures(d):
    em, et = margin - d.mean_margin.to_numpy(), total - d.mean_total.to_numpy()
    out = {"bias_margin": em, "bias_total": et, "mse_margin": em**2, "mse_total": et**2,
           "crps_margin": d.crps_margin.to_numpy(), "crps_total": d.crps_total.to_numpy()}
    for name, p, y in (("cover", d.p_cover_nopush.to_numpy(float), cover), ("over", d.p_over_nopush.to_numpy(float), over)):
        k = np.isfinite(y) & np.isfinite(p)
        out[f"brier_{name}"] = np.where(k, (p - np.nan_to_num(y)) ** 2, np.nan)
        out[f"calib_{name}"] = np.where(k, p - np.nan_to_num(y), np.nan)  # mean pred minus observed
    return out


m = {v: measures(per[v]) for v in VARIANTS}
bench = {}
for v in VARIANTS:
    row = {}
    for key, x in m[v].items():
        k = np.isfinite(x)
        row[key] = {"value": round(float(np.mean(x[k])), 4), "ci": ci(x[k], clusters[k])}
        if v != "current":
            if key.startswith(("bias", "calib")):  # better = mean closer to zero
                row[key]["closer_to_zero_vs_current"] = closeness_gain(m["current"][key][k], x[k], 0.0, clusters[k])
            else:
                d = m["current"][key][k] - x[k]  # > 0: fixed is better
                row[key]["gain_vs_current"] = {"value": round(float(d.mean()), 4), "ci": ci(d, clusters[k])}
    row["coverage"] = {f"{kind}_{l}": {"value": round(float(per[v][f"{kind}_in_{int(l * 100)}"].mean()), 4)}
                       for kind in ("margin", "total") for l in sb.LEVELS}
    if v != "current":
        for kind in ("margin", "total"):
            for l in sb.LEVELS:
                col = f"{kind}_in_{int(l * 100)}"
                row["coverage"][f"{kind}_{l}"]["closer_to_nominal_vs_current"] = closeness_gain(
                    base[col].to_numpy(), per[v][col].to_numpy(), l, clusters)
    row["tie_rate"] = round(float(per[v].p_tie.mean()), 4)
    row["p_abs3"], row["p_abs7"] = round(float(per[v].p_abs3.mean()), 4), round(float(per[v].p_abs7.mean()), 4)
    d = per[v][per[v].home_win != 0.5]
    row["win_log_loss"] = round(metrics.log_loss(d.p_win_half.to_numpy(), d.home_win.to_numpy()), 5)
    if v != "current":
        dc = base[base.home_win != 0.5]
        g = metrics.paired_gain(d.p_win_half.to_numpy(), dc.p_win_half.to_numpy(), d.home_win.to_numpy())
        row["win_log_loss_gain_vs_current"] = {"value": round(g["log_loss_gain"], 5), "ci": g["log_loss_gain_ci"]}
    bench[v] = row
bench["real"] = {"tie_rate": float((margin == 0).mean()), "abs3": float(np.mean(np.abs(margin) == 3)),
                 "abs7": float(np.mean(np.abs(margin) == 7)), "games": int(len(base))}

# --- mean check 2024, 2025, 2026 wk 1-5 -------------------------------------------------------------
present = {n: {"present": True, "observed_before_cutoff": True} for n in rc.INPUTS}
check = {}
for v in VARIANTS:
    for s in CHECK:
        model = engine._score_model(feat, s)
        games = feat[(feat["season"] == s) & (feat["game_type"] == "REG")]
        if s == 2026:
            games = games[games["week"] <= 5]
        res = []
        for _, r in games.iterrows():
            sim = engine._simulation(r, P[(s, v)], model, feat)
            if sim is None:
                continue
            e = rc.check_game(r["game_id"], sim, present, r["spread_line"])
            res.append({"week": int(r["week"]), "ok": e["ok"], "d_margin": e["margin"]["simulated"] - e["margin"]["inputs"],
                        "d_total": e["total"]["simulated"] - e["total"]["inputs"]})
        res = pd.DataFrame(res)
        wk = res.groupby("week").agg(ok=("ok", "all"), n=("ok", "size"))
        full = wk[wk.n >= 16]
        check[f"{s}/{v}"] = {
            "games": len(res), "game_pass": round(float(res.ok.mean()), 4),
            "weeks": len(wk), "week_pass": round(float(wk.ok.mean()), 4),
            "weeks_16": len(full), "week16_pass": round(float(full.ok.mean()), 4) if len(full) else None,
            "per_game_pow16": round(float(res.ok.mean()) ** 16, 4),
            "d_margin_mean": round(float(res.d_margin.mean()), 3), "d_total_mean": round(float(res.d_total.mean()), 3),
        }

json.dump({"pool_means": pool_means, "bench": bench, "mean_check": check}, open(sys.argv[2], "w"), indent=1)
for v in VARIANTS:
    b = bench[v]
    print(v, {k: (b[k]["value"], b[k].get("gain_vs_current", b[k].get("closer_to_zero_vs_current"))) for k in m[v]})
    print("   ", "cov", {k: (c["value"], c.get("closer_to_nominal_vs_current")) for k, c in b["coverage"].items()}, "tie", b["tie_rate"], "ll", b["win_log_loss"], b.get("win_log_loss_gain_vs_current"))
for k, c in check.items():
    print(k, c)
