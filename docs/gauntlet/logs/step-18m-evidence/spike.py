"""Spike, not production: does an exponentially tilted pool of real regulation score pairs fix 3/7? Tune seasons only."""
import csv, sys, json
import numpy as np
from nflpi.analytics import sim_backtest as sb
from nflpi.sim import simulate_game, TeamFeatures
from nflpi.sim.params import regulation_scores
from nflpi.sim.overtime import resolve_overtime

rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["gameday"] < "2026-10-15"]
frame = sb.load_games(rows)
table = sb.build_table(frame)
SEASONS = range(2012, 2022)
N = 4000
BW = []
ALPHAS = [1.0, 0.75, 0.5]
KMAX = 60  # 0 = no kernel

def tilt_weights(sa, sb_, ta, tb, base=None):
    lam = np.zeros(2); S = np.stack([sa, sb_], 1).astype(float); t = np.array([ta, tb])
    for _ in range(50):
        z = S @ lam + (0 if base is None else np.log(base)); w = np.exp(z - z.max()); w /= w.sum()
        m = w @ S; d = S - m; H = (d * w[:, None]).T @ d; g = m - t
        if np.abs(g).max() < 1e-6: break
        lam -= np.linalg.solve(H + 1e-9 * np.eye(2), g)
    return w

out = {}
for source in ("football_only", "market_informed"):
    p = sb.PREFIX[source]
    TAGS = ["cur"] + [f"h{h}" for h in BW] + [f"kw{a}" for a in ALPHAS]
    stats = {f"{t}{k}": [] for t in TAGS for k in ("3", "7", "_crps", "_cov", "_over", "80", "_mean_err", "50", "95", "_pit", "_sd")}
    stats |= {k: [] for k in ("real3", "real7", "y_cover", "y_over")}
    for season in SEASONS:
        params = sb.learn_for_season(table, season, source)
        win = table[table["season"].between(max(sb.MIN_TRAIN_SEASON, season - sb.WINDOW), season - 1)]
        ra, rb = regulation_scores(win["home_score"].to_numpy(), win["away_score"].to_numpy(), win["overtime"].to_numpy())
        half_ot = float(np.mean(ra - win["home_score"].to_numpy()) + np.mean(rb - win["away_score"].to_numpy())) / 2
        games = table[table["season"] == season]
        mwa, mwb = win[f"{p}home"].to_numpy(float), win[f"{p}away"].to_numpy(float)
        rng = np.random.default_rng(season)
        # key-number ratio learned on the training window only: real |margin| frequency over the current sampler's
        sim_hist = np.zeros(KMAX + 1); real_hist = np.zeros(KMAX + 1)
        for x in win.itertuples():
            r0 = simulate_game(TeamFeatures(getattr(x, f"{p}home")), TeamFeatures(getattr(x, f"{p}away")), 2000,
                               params=params, seed=int(rng.integers(1 << 31)))
            sim_hist += np.bincount(np.minimum(np.abs(r0.a_score - r0.b_score), KMAX), minlength=KMAX + 1) / 2000
            real_hist[min(abs(x.home_score - x.away_score), KMAX)] += 1
        ratio = np.where(sim_hist > 0, (real_hist + 0.5) / (sim_hist + 0.5), 1.0)
        for g in games.itertuples():
            mua, mub = getattr(g, f"{p}home"), getattr(g, f"{p}away")
            h, tot = -g.spread_line, g.total_line
            cur = simulate_game(TeamFeatures(mua), TeamFeatures(mub), N, params=params, seed=int(rng.integers(1 << 31)), spread=h, total=tot)
            sims = [("cur", cur.a_score, cur.b_score)]
            for bw in BW:
                base = None if bw == 0 else np.exp(-0.5 * (((mwa - mua) / bw) ** 2 + ((mwb - mub) / bw) ** 2)) + 1e-12
                w = tilt_weights(ra, rb, mua + half_ot, mub + half_ot, base)  # half_ot is negative (reg - final)
                idx = rng.choice(len(ra), N, p=w)
                a, b = resolve_overtime(ra[idx], rb[idx], rng, params, False)
                sims.append((f"h{bw}", a, b))
            real_m, real_t = g.home_score - g.away_score, g.home_score + g.away_score
            m0, t0 = cur.a_score - cur.b_score, cur.a_score + cur.b_score
            for al in ALPHAS:
                base = ratio[np.minimum(np.abs(m0), KMAX)] ** al
                w = tilt_weights(m0, t0, m0.mean(), t0.mean(), base)  # keep the mean margin and total
                idx = rng.choice(len(m0), N, p=w)
                sims.append((f"kw{al}", cur.a_score[idx], cur.b_score[idx]))
            for tag, A, B in sims:
                m, t = A - B, A + B
                stats[f"{tag}3"].append(np.mean(np.abs(m) == 3)); stats[f"{tag}7"].append(np.mean(np.abs(m) == 7))
                stats[f"{tag}_crps"].append(sb.crps(m, real_m) + sb.crps(t, real_t))
                e = m + h; dec = e != 0
                pc = np.mean(e > 0) / max(np.mean(dec), 1e-9)
                po = np.mean(t > tot) / max(np.mean(t != tot), 1e-9)
                stats[f"{tag}_cov"].append(pc); stats[f"{tag}_over"].append(po)
                lo, hi = np.quantile(m, 0.1, method="lower"), np.quantile(m, 0.9, method="higher")
                stats[f"{tag}80"].append(lo <= real_m <= hi)
                below, at = np.mean(m < real_m), np.mean(m == real_m)
                stats[f"{tag}_pit"].append(below + rng.random() * at)  # randomized PIT, fair for whole-number margins
                stats[f"{tag}_sd"].append(m.std())
                for lv, key in ((0.5, "50"), (0.95, "95")):
                    l2, h2 = np.quantile(m, (1 - lv) / 2, method="lower"), np.quantile(m, (1 + lv) / 2, method="higher")
                    stats[f"{tag}{key}"].append(l2 <= real_m <= h2)
                stats[f"{tag}_mean_err"].append(m.mean() - (mua - mub))
            stats["real3"].append(abs(real_m) == 3); stats["real7"].append(abs(real_m) == 7)
            stats["y_cover"].append(np.nan if real_m + h == 0 else float(real_m + h > 0))
            stats["y_over"].append(np.nan if real_t == tot else float(real_t > tot))
    s = {k: np.array(v, float) for k, v in stats.items()}
    def boot(pn, pc, y):
        ok = ~np.isnan(y); d = (pn[ok] - y[ok]) ** 2 - (pc[ok] - y[ok]) ** 2; r = np.random.default_rng(7)
        bs = [d[r.integers(0, len(d), len(d))].mean() for _ in range(2000)]
        return [float(d.mean()), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]
    def bootc(a, c):
        d = a - c; r = np.random.default_rng(7); bs = [d[r.integers(0, len(d), len(d))].mean() for _ in range(2000)]
        return [float(d.mean()), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]
    def brier(pp, y): ok = ~np.isnan(y); return float(np.mean((pp[ok] - y[ok]) ** 2))
    out[source] = {"games": len(s["real3"]), "real3": s["real3"].mean(), "real7": s["real7"].mean()}
    for t in TAGS:
        out[source][t] = {"k3": s[f"{t}3"].mean(), "k7": s[f"{t}7"].mean(), "crps": s[f"{t}_crps"].mean(),
            "cover_brier": brier(s[f"{t}_cov"], s["y_cover"]), "over_brier": brier(s[f"{t}_over"], s["y_over"]),
            "cov50/80/95": [s[f"{t}50"].mean(), s[f"{t}80"].mean(), s[f"{t}95"].mean()],
            "mean_err": s[f"{t}_mean_err"].mean(), "sd": s[f"{t}_sd"].mean(),
            "d_cover_ci": boot(s[f"{t}_cov"], s["cur_cov"], s["y_cover"]), "d_over_ci": boot(s[f"{t}_over"], s["cur_over"], s["y_over"]),
            "d_crps_ci": bootc(s[f"{t}_crps"], s["cur_crps"]),
            "pit_cov50/80/95": [float(np.mean(np.abs(s[f"{t}_pit"] - 0.5) <= lv / 2)) for lv in (0.5, 0.8, 0.95)]}
    print(source, json.dumps(out[source], indent=1, default=float), flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1, default=float)
