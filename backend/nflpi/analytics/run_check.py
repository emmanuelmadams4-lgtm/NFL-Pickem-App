"""The check report for one simulation run: maths only, written by Python (docs/model/PLAN.md section 5, D74).

Claude reads this report and the run record and answers PASS or FAIL. It never edits a number, and a reply that is
not exactly PASS or FAIL counts as no verdict.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from nflpi.analytics.sim_backtest import N_SIMULATIONS
from nflpi.picks import home_spread_from_nflverse  # re-export of the one place that flips the sign (A13)

INPUTS = ("elo_diff", "home_field", "home_qb_change", "away_qb_change", "market_logit")  # FEATURES.md Table 1
REQUIRED_INPUTS = ("elo_diff",)  # the others have a stated fallback, so missing is marked, not failed
PROB_TOL = 1e-3  # the stored chances are rounded to 4 places
SE_Z = 5.0  # a mean this many standard errors off its inputs is not sampling noise
Z_80 = 1.2816  # normal quantile of an 80% interval, to get the spread back from the stored interval
# Overtime adds points on top of the expected points of the two teams, so the simulated mean total sits a little
# above home + away. Measured +0.30 to +0.38 on the six fixture games (synthetic overtime rate 13%, real is lower).
OVERTIME_TOTAL_ALLOWANCE = 0.5
REASON_MAX = 500
CUTOFF_RULE = "a value may be used only if observed_at <= the moment the prediction is made (the as-of rule)"


@dataclass(frozen=True)
class Verdict:
    status: str | None  # "PASS", "FAIL" or None (no verdict)
    reasons: tuple[str, ...] = ()
    cause: str | None = None  # why there is no verdict: cap, provider, unparsed or error
    games: tuple[str, ...] = ()  # the games a FAIL names


def _finite(v: object) -> bool:
    return v is not None and not isinstance(v, str) and math.isfinite(v)


def _sum(sim: Mapping, keys: tuple[str, ...]) -> float | None:
    values = [sim.get(k) for k in keys]
    return None if any(v is None for v in values) else round(sum(values), 6)


def _mean_check(name: str, simulated: float, from_inputs: float, interval: list[float], n: int,
                allowance_above: float = 0.0) -> tuple[dict, list]:
    se = (interval[1] - interval[0]) / (2 * Z_80) / math.sqrt(n)
    slack = SE_Z * se + PROB_TOL
    within = -slack <= simulated - from_inputs <= slack + allowance_above
    entry = {"inputs": round(from_inputs, 4), "simulated": simulated, "sampling_error": round(se, 4), "within": within}
    if not within:
        return entry, [f"mean {name} {simulated} is not within sampling error of the inputs {entry['inputs']}"]
    return entry, []


def check_game(game_id: str, sim: Mapping | None, inputs: Mapping[str, Mapping], spread_line: float | None) -> dict:
    """One game's maths. `inputs` maps each FEATURES.md name to {"present": bool, "observed_before_cutoff": ...}."""
    marked = {
        name: {
            "status": "present" if inputs[name]["present"] else "missing",
            "observed_before_cutoff": inputs[name]["observed_before_cutoff"],
        }
        for name in INPUTS
    }
    entry: dict = {"game_id": game_id, "has_simulation": sim is not None, "inputs": marked}
    if sim is None:
        return entry | {"ok": True, "problems": []}
    problems = [f"input {n} missing" for n in REQUIRED_INPUTS if marked[n]["status"] == "missing"]
    problems += [f"input {n} was not observed before the cutoff" for n, m in marked.items()
                 if m["status"] == "present" and m["observed_before_cutoff"] is False]
    n = sim["n_simulations"]
    if n != N_SIMULATIONS:
        problems.append(f"n_simulations is {n}, must be {N_SIMULATIONS}")
    sums = {
        "win_tie_loss": _sum(sim, ("home_win", "away_win", "tie")),
        "cover_push": _sum(sim, ("home_cover", "away_cover", "spread_push")),
        "over_push": _sum(sim, ("over", "under", "total_push")),
    }
    names = {"win_tie_loss": "win+tie+loss", "cover_push": "cover+push+no cover", "over_push": "over+push+under"}
    for key, total in sums.items():
        if total is None and key != "win_tie_loss":
            continue
        if total is None or abs(total - 1) > PROB_TOL:
            problems.append(f"{names[key]} sums to {total}, must be 1")
    for line, fields, label in (("home_spread", ("home_cover", "away_cover", "spread_push"), "cover chances"),
                                ("total", ("over", "under", "total_push"), "over chances")):
        if (sim.get(line) is None) != all(sim.get(f) is None for f in fields):
            problems.append(f"{label} and the {line} line disagree about being missing")
    expected_h = float(home_spread_from_nflverse(spread_line)) if _finite(spread_line) else None
    stored_h = sim.get("home_spread")
    sign_ok = (expected_h is None and stored_h is None) or (
        expected_h is not None and stored_h is not None and abs(stored_h - expected_h) <= PROB_TOL)
    if not sign_ok:
        problems.append(f"spread sign: stored home_spread {stored_h} is not the one converted from {spread_line}")
    margin, found = _mean_check("margin", sim["expected_margin"], sim["home_points"] - sim["away_points"],
                                sim["margin_80"], n)
    total, more = _mean_check("total", sim["expected_total"], sim["home_points"] + sim["away_points"],
                              sim["total_80"], n,
                              OVERTIME_TOTAL_ALLOWANCE)
    problems += found + more
    return entry | {
        "n_simulations": n, "sums": sums, "margin": margin, "total": total,
        "spread_sign": {"nflverse_spread_line": spread_line, "expected_home_spread": expected_h,
                        "stored_home_spread": stored_h, "ok": sign_ok},
        "ok": not problems, "problems": problems,
    }


def build_report(entries: Mapping[str, dict]) -> dict:
    games = list(entries.values())
    simulated = [g for g in games if g["has_simulation"]]
    return {
        "required_simulations": N_SIMULATIONS, "cutoff_rule": CUTOFF_RULE, "n_games": len(games),
        "n_simulated": len(simulated), "all_ok": all(g["ok"] for g in games), "games": games,
    }


def _before(observed: object, cutoff: datetime) -> bool | None:
    if observed is None or observed is pd.NaT:
        return None
    ts = pd.Timestamp(observed)
    ts = ts.tz_localize(UTC) if ts.tzinfo is None else ts
    return bool(ts <= cutoff)


def game_inputs(row: Mapping, cutoff: datetime, results_ok: bool | None) -> dict[str, dict]:
    """Which FEATURES.md inputs this game has, and whether each was observed before `cutoff`.

    Results (Elo) are checked as a whole by `results_ok`; the schedule and quarterback names carry no timestamp of
    their own (None = not recorded); the market line carries our own download time.
    """
    named = lambda *cols: all(isinstance(row.get(c), str) and row.get(c) for c in cols)  # noqa: E731
    market_seen = _before(row.get("market_observed_at"), cutoff)
    return {
        "elo_diff": {"present": _finite(row.get("elo_diff")), "observed_before_cutoff": results_ok},
        "home_field": {"present": _finite(row.get("home_field")), "observed_before_cutoff": None},
        "home_qb_change": {"present": named("home_qb", "home_prev_qb"), "observed_before_cutoff": None},
        "away_qb_change": {"present": named("away_qb", "away_prev_qb"), "observed_before_cutoff": None},
        "market_logit": {"present": _finite(row.get("market_logit")), "observed_before_cutoff": market_seen},
    }


def content_hash(record: Mapping, report: Mapping, simulations: Mapping) -> str:
    """Same record, report and simulations give the same hash: Claude is asked only when this changes."""
    record = {k: v for k, v in record.items() if k != "git_dirty"}  # a dirty tree must not cost a call
    payload = json.dumps({"record": record, "report": report, "simulations": simulations}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_verdict(text: str) -> Verdict:
    """The first line must be exactly PASS or FAIL; everything after it is reasons. Anything else is no verdict."""
    lines = (text or "").strip().splitlines()
    if not lines or lines[0].strip() not in ("PASS", "FAIL"):
        return Verdict(None, cause="unparsed")
    status, rest = lines[0].strip(), [ln.strip() for ln in lines[1:] if ln.strip()]
    if status == "PASS" and rest:
        return Verdict(None, cause="unparsed")  # a PASS must be the only line: anything after it is no verdict
    reasons = " ".join(rest)[:REASON_MAX]
    return Verdict(status, (reasons,) if reasons else ())
