"""Evaluation report (step 18f): the bench as one report, run records and a full prediction export.

    python -m nflpi.analytics.report <games.csv> <out_dir> [--sim-dir DIR] [--simulate]

Reads the stored simulator evidence, never reruns the simulator confirm. Spec: docs/model/EVALUATION.md.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from nflpi.analytics import backtest, metrics, score_backtest, sim_backtest
from nflpi.analytics.manifest import run_record
from nflpi.export import (
    CONFIDENCE_BANDS,
    closing_results,
    prediction_record,
    sim_wide,
    to_csv_text,
    to_json_text,
    to_native,
)
from nflpi.predictions.elo import EloParams
from nflpi.predictions.scores import add_score_features

D72_FIRST_PROTECTED = "2026-10-15"
D72_FIRST_SEASON = 2026
BENCH_SEASONS = list(range(2012, 2026))
WINDOW = 10
RELIABILITY_BINS = 20
RELIABILITY_MODELS = ("logistic", "blend", "market")
MATCH_TOLERANCE = 1e-9
CONFIRM_FILE = "confirm-result.json"
INPUT_SIM_FILES = ("tune-result.json", CONFIRM_FILE)
CUTOFF_RULE = "fitted on seasons S-10 to S-1 for test season S"
SIM_LABEL = "not shown to beat a coin flip against the closing line"
RETURNS_REASON = "no history of timestamped prices exists, so no returns or profit are reported (PLAN 3.5)"
NO_SIM_REASON = "stored simulator results not supplied; pass --sim-dir with confirm-result.json"
STORED_KEYS = ("seasons", "n_simulations", "default_distribution", "games", "sources_note", "variants")
CLOSING_LINE_MODELS = {"market", "blend"}
RECORD_COLUMNS = [
    "game_id", "season", "week", "kickoff_utc", "home_team", "away_team", "home_win", "home_score", "away_score",
    "spread_line", "total_line", "p_home", "p_elo", "p_logistic", "p_market", "p_blend",
]
NOTES = [
    "The closing line is a benchmark, not what was on offer at decision time; every closing-line number is labelled.",
    "The bench has been scored many times on the latest seasons, so this report is a read, not a new test.",
]


class ReportError(ValueError):
    """The inputs break a rule of the report (D72) or cannot be scored."""


# --- sample and the D72 gate ----------------------------------------------------------------------

def _kickoffs(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["kickoff_utc"], utc=True, errors="coerce")


def _protected_cut() -> pd.Timestamp:
    return pd.Timestamp(D72_FIRST_PROTECTED, tz="UTC")


def guard_scored(frame: pd.DataFrame, seasons: list[int]) -> None:
    if any(s >= D72_FIRST_SEASON for s in seasons):
        raise ReportError(f"D72: seasons from {D72_FIRST_SEASON} on are never scored")
    scored = frame[frame["season"].isin(seasons)]
    kickoffs = _kickoffs(scored)
    if kickoffs.isna().any():
        raise ReportError("D72: a scored game has no readable kickoff, so it cannot be checked against the cutoff")
    if (kickoffs >= _protected_cut()).any():
        raise ReportError(f"D72: a game with kickoff on or after {D72_FIRST_PROTECTED} would be scored")


def guard_finals(frame: pd.DataFrame) -> None:
    """A final score on or after the protected date means the file itself breaks D72."""
    finals = frame[frame["home_score"].notna() & frame["away_score"].notna()]
    kickoffs = _kickoffs(finals)
    if kickoffs.isna().any():
        raise ReportError("D72: the file holds a final game with no readable kickoff")
    if (kickoffs >= _protected_cut()).any():
        raise ReportError(f"D72: the file holds a final game with kickoff on or after {D72_FIRST_PROTECTED}")


def _sample(frame: pd.DataFrame, seasons: list[int], preds: pd.DataFrame, record: pd.DataFrame,
            score_preds: pd.DataFrame) -> dict:
    finals = frame[(frame["game_type"] == "REG") & (frame["status"] == "final") & frame["season"].isin(seasons)
                   & frame["home_score"].notna() & frame["away_score"].notna()]
    return {
        "finals": int(len(finals)),
        "ties_excluded": int((finals["home_score"] == finals["away_score"]).sum()),
        "no_moneyline_excluded": int(preds["p_market"].isna().sum()),
        "no_score_prediction_excluded": int(score_preds[score_backtest.PRED_COLS].isna().any(axis=1).sum()),
        "games": int(len(record)),
        "by_season": {int(s): int(n) for s, n in record.groupby("season").size().items()},
    }


def bench_frames(frame: pd.DataFrame, seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(win record, score predictions, sample) from the existing walk-forward bench code."""
    guard_scored(frame, seasons)
    elo = backtest._elo_frames(frame)
    preds = pd.concat([backtest.predict_season(elo, s, WINDOW) for s in seasons], ignore_index=True)
    record = preds.loc[preds["p_market"].notna(), RECORD_COLUMNS]
    record = record.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    ordered = frame.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    scored = add_score_features(ordered, EloParams())
    score_all = pd.concat([score_backtest.predict_season(scored, s, WINDOW) for s in seasons], ignore_index=True)
    score_preds = score_all.loc[score_all["game_id"].isin(record["game_id"]),
                                ["game_id", "season", *score_backtest.PRED_COLS]].reset_index(drop=True)
    return record, score_preds, _sample(frame, seasons, preds, record, score_preds)


# --- win model ------------------------------------------------------------------------------------

def _win_blocks(record: pd.DataFrame) -> dict:
    y = record["home_win"].to_numpy(float)
    return {m: {"label": backtest.LABELS[m], "uses_closing_line": m in CLOSING_LINE_MODELS,
                **metrics.summarize(record[f"p_{m}"].to_numpy(float), y)} for m in backtest.MODELS}


def _reliability(record: pd.DataFrame) -> dict:
    y = record["home_win"].to_numpy(float)
    return {m: metrics.calibration(record[f"p_{m}"].to_numpy(float), y, RELIABILITY_BINS)
            for m in RELIABILITY_MODELS}


def _season_blocks(record: pd.DataFrame) -> dict:
    out = {}
    for season, g in record.groupby("season"):
        y = g["home_win"].to_numpy(float)
        row = {"n": int(len(g))}
        for m in backtest.MODELS:
            p = g[f"p_{m}"].to_numpy(float)
            row[m] = {"n": int(len(g)), "accuracy": metrics.accuracy(p, y), "log_loss": metrics.log_loss(p, y)}
        out[int(season)] = row
    return out


def _confidence_bands(record: pd.DataFrame) -> list[dict]:
    p = record["p_blend"].to_numpy(float)
    picked = np.maximum(p, 1 - p)
    correct = (p > 0.5) == (record["home_win"].to_numpy(float) == 1)
    rows = []
    for label, lo, hi in CONFIDENCE_BANDS:
        mask = (picked >= lo) & ((picked < hi) if hi < 1 else (picked <= hi))
        n = int(mask.sum())
        rows.append({"band": label, "n": n, "share": n / len(p) if len(p) else None,
                     "hit_rate": float(correct[mask].mean()) if n else None})
    return rows


def _pick_labels(record: pd.DataFrame) -> list[dict]:
    return [{**row, "n": row["games"]} for row in backtest.label_report(record)]


# --- points and closing outcomes ------------------------------------------------------------------

def _error_block(error: np.ndarray) -> dict:
    kept = error[np.isfinite(error)]
    if not len(kept):
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    return {"n": int(len(kept)), "mae": float(np.abs(kept).mean()), "rmse": float(np.sqrt((kept**2).mean())),
            "bias": float(kept.mean())}


def _method_errors(df: pd.DataFrame, method: str) -> dict:
    home, away = df[f"pred_{method}_home"].to_numpy(float), df[f"pred_{method}_away"].to_numpy(float)
    actual_home, actual_away = df["home_score"].to_numpy(float), df["away_score"].to_numpy(float)
    return {"margin": _error_block((home - away) - (actual_home - actual_away)),
            "total": _error_block((home + away) - (actual_home + actual_away))}


def _points(df: pd.DataFrame) -> dict:
    methods = score_backtest.METHODS
    out = {m: {"label": score_backtest.LABELS[m], **_method_errors(df, m)} for m in methods}
    out["by_season"] = {int(s): {m: _method_errors(g, m) for m in methods} for s, g in df.groupby("season")}
    return out


def _outcome_counts(cover: pd.Series, over: pd.Series) -> dict:
    return {
        "spread": {"n": int(cover.notna().sum()), "home_cover": int((cover == "home_cover").sum()),
                   "away_cover": int((cover == "away_cover").sum()), "push": int((cover == "push").sum())},
        "total": {"n": int(over.notna().sum()), "over": int((over == "over").sum()),
                  "under": int((over == "under").sum()), "push": int((over == "push").sum())},
    }


def _closing_outcomes(df: pd.DataFrame) -> dict:
    cover, over = closing_results(df)
    by_season = {int(s): _outcome_counts(cover[g.index], over[g.index]) for s, g in df.groupby("season")}
    return {"line_kind": "closing, benchmark only", "overall": _outcome_counts(cover, over), "by_season": by_season,
            "returns": {"value": None, "reason": RETURNS_REASON}}


# --- simulator (stored confirm file) --------------------------------------------------------------

def _weighted_mean(table: list[dict], key: str) -> tuple[int, float | None]:
    n = sum(row["n"] for row in table)
    return n, (sum(row["n"] * row[key] for row in table) / n if n else None)


def _rates(v: dict) -> tuple[dict, dict]:
    rates, briers = {}, {}
    for kind in ("cover", "over"):
        table = v["calibration"][kind]["table"]
        n, simulated = _weighted_mean(table, "mean_pred")
        rates[kind] = {"n": n, "simulated": simulated, "real": _weighted_mean(table, "observed")[1],
                       "pushes": v["games"] - n}
        briers[kind] = {"n": n, "brier": v["calibration"][kind]["brier"],
                        "brier_flat_half": v["calibration"][kind]["brier_flat_half"]}
    return rates, briers


def _sim_variant(v: dict) -> dict:
    rates, briers = _rates(v)
    interval = v["win_probability"].get("log_loss_gain_ci")
    includes_zero = None if interval is None else interval[0] <= 0 <= interval[1]
    verdict = ("interval missing" if includes_zero is None
               else "interval includes zero" if includes_zero else "interval excludes zero")
    return {
        "source": v["source"], "distribution": v["distribution"], "is_default": v["is_default"], "n": v["games"],
        "margin": {"n": v["games"], "mae": v["margin_mae"], "rmse": v["margin_rmse"]},
        "total": {"n": v["games"], "mae": v["total_mae"], "rmse": v["total_rmse"]},
        "coverage": {kind: [{"nominal": float(level), "n": v["games"], "observed": value}
                            for level, value in levels.items()] for kind, levels in v["coverage"].items()},
        "rates": rates, "brier": briers, "tie_rate": {"n": v["games"], **v["tie_rate"]},
        "key_numbers": v["key_numbers"], "win_probability": v["win_probability"],
        "win_gap_vs_blend": v["win_gap_vs_blend"],
        "verdict": {"gain_interval_includes_zero": includes_zero,
                    "text": f"stored log loss gain over the blend: {verdict}"},
    }


def _simulator(stored: dict | None, reason: str | None) -> dict:
    if stored is None:
        return {"label": SIM_LABEL, "variants": [], "reason": reason or NO_SIM_REASON}
    return {
        "label": SIM_LABEL, "seasons": stored["seasons"], "n_simulations": stored["n_simulations"],
        "default_distribution": stored["default_distribution"], "games": stored["games"],
        "sources_note": stored["sources_note"], "variants": [_sim_variant(v) for v in stored["variants"]],
    }


def build_report(record: pd.DataFrame, score_preds: pd.DataFrame, sample: dict, sim: dict | None,
                 sim_reason: str | None = None) -> dict:
    df = record.merge(score_preds[["game_id", *score_backtest.PRED_COLS]], on="game_id", how="left")
    return to_native({
        "sample": sample,
        "win": _win_blocks(record),
        "reliability": _reliability(record),
        "by_season": _season_blocks(record),
        "confidence_bands": _confidence_bands(record),
        "pick_labels": _pick_labels(record),
        "points": _points(df),
        "closing_outcomes": _closing_outcomes(df),
        "simulator": _simulator(sim, sim_reason),
        "notes": NOTES,
    })


# --- re-simulation (--simulate) -------------------------------------------------------------------

def _same(fresh: dict, stored: dict) -> bool:
    pairs = [(fresh["coverage"][k][lv], stored["coverage"][k][lv]) for k in ("margin", "total")
             for lv in stored["coverage"][k]]
    pairs += [(fresh["calibration"][k]["brier"], stored["calibration"][k]["brier"]) for k in ("cover", "over")]
    return all(abs(a - b) <= MATCH_TOLERANCE for a, b in pairs)


def simulate_confirm(frame: pd.DataFrame, record: pd.DataFrame, stored: dict) -> tuple[pd.DataFrame, bool]:
    """Per-game simulator columns for the stored seasons, and whether they reproduce the stored confirm file."""
    guard_scored(frame, [int(s) for s in stored["seasons"]])
    table = sim_backtest.build_table(frame)
    default = stored["default_distribution"]
    rows = sim_backtest.simulate_table(table, stored["seasons"], distributions=(default,),
                                       n_simulations=stored["n_simulations"], base_seed=sim_backtest.BASE_SEED)
    cols = ["game_id", "home_score", "away_score", "spread_line", "total_line", "home_win"]
    joined = rows.merge(table[cols], on="game_id").merge(record[["game_id", "p_blend", "p_market"]],
                                                        on="game_id", how="left")
    fresh = {(s, d): sim_backtest._variant(g, s, d, default)
             for (s, d), g in joined.groupby(["source", "distribution"], sort=False)}
    kept = {(v["source"], v["distribution"]): v for v in stored["variants"]}
    matches = all(key in fresh and _same(fresh[key], kept[key]) for key in kept if key[1] == default)
    return sim_wide(rows), matches


# --- text -----------------------------------------------------------------------------------------

def _fmt(value) -> str:
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _is_scalar(value) -> bool:
    return not isinstance(value, (dict, list))


def _render_dict(node: dict, depth: int, lines: list[str]) -> None:
    pad = "  " * depth
    for key, value in node.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            _render_dict(value, depth + 1, lines)
        elif isinstance(value, list) and not all(_is_scalar(v) for v in value):
            lines.append(f"{pad}{key}:")
            for item in value:
                _render_item(item, depth + 1, lines)
        elif isinstance(value, list):
            lines.append(f"{pad}{key}: " + (", ".join(_fmt(v) for v in value) if value else "missing"))
        else:
            lines.append(f"{pad}{key}: {_fmt(value)}")


def _render_item(item, depth: int, lines: list[str]) -> None:
    pad = "  " * depth
    if isinstance(item, dict) and all(_is_scalar(v) for v in item.values()):
        lines.append(f"{pad}- " + ", ".join(f"{k}={_fmt(v)}" for k, v in item.items()))
    elif isinstance(item, dict):
        lines.append(f"{pad}-")
        _render_dict(item, depth + 1, lines)
    else:
        lines.append(f"{pad}- {_fmt(item)}")


def render_text(report: dict) -> str:
    """The report as indented text: every number comes from the report, a missing value reads 'missing'."""
    lines = ["Evaluation report"]
    _render_dict(report, 0, lines)
    return "\n".join(lines) + "\n"


# --- run records ----------------------------------------------------------------------------------

SIM_CUTOFF_RULE = "learned on seasons S-10 to S-1 before test season S"
SIM_SEED_NOTE = (f"the code constant sim_backtest.BASE_SEED, because {CONFIRM_FILE} stores no seed; "
                 "--simulate recomputing the stored confirm result is the evidence")


def _iso(latest) -> str | None:
    return pd.Timestamp(latest).strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(latest) else None


def _sim_cutoff_rule(seasons: list[int], latest: str | None) -> str:
    rule = (f"{SIM_CUTOFF_RULE}; confirm seasons {min(seasons)} to {max(seasons)}, "
            f"read from the stored {CONFIRM_FILE}")
    return rule if latest else f"{rule}; latest kickoff unavailable: no bench game in those seasons"


def _record_kwargs(record: pd.DataFrame) -> list[dict]:
    seasons = sorted(int(s) for s in record["season"].unique())
    shared = {"cutoff_rule": CUTOFF_RULE, "latest_kickoff": _iso(record["kickoff_utc"].max()),
              "n_games": len(record), "seasons": seasons, "seed": None,
              "seed_note": "deterministic, no random draws"}
    specs = [{"model": m, "label": backtest.LABELS[m], "uses_closing_line": m in CLOSING_LINE_MODELS, **shared}
             for m in backtest.MODELS]
    return specs + [{"model": f"score_{m}", "label": score_backtest.LABELS[m], "uses_closing_line": m != "stats",
                     **shared} for m in score_backtest.METHODS]


def _sim_kwargs(record: pd.DataFrame, stored: dict) -> list[dict]:
    seasons = sorted(int(s) for s in stored["seasons"])
    latest = _iso(record.loc[record["season"].isin(seasons), "kickoff_utc"].max())
    return [{"model": f"sim_{s}", "label": f"Simulator, {s}", "uses_closing_line": s == "market_informed",
             "cutoff_rule": _sim_cutoff_rule(seasons, latest), "latest_kickoff": latest,
             "n_games": int(stored["games"]), "seasons": seasons, "seed": sim_backtest.BASE_SEED,
             "seed_note": SIM_SEED_NOTE} for s in sim_backtest.SOURCES]


def build_records(record: pd.DataFrame, stored: dict | None, data_files: dict[str, Path]) -> list[dict]:
    repo_root = Path(__file__).resolve().parents[3]
    specs = _record_kwargs(record) + ([] if stored is None else _sim_kwargs(record, stored))
    return [run_record(data_files=data_files, repo_root=repo_root, **spec) for spec in specs]


# --- command line ---------------------------------------------------------------------------------

def load_stored(sim_dir: str | None) -> tuple[dict | None, str | None]:
    if sim_dir is None:
        return None, NO_SIM_REASON
    path = Path(sim_dir) / CONFIRM_FILE
    if not path.is_file():
        return None, f"{CONFIRM_FILE} not found in {sim_dir}"
    return _read_stored(path), None


def _read_stored(path: Path) -> dict:
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        raise ReportError(f"{CONFIRM_FILE} cannot be read as JSON: {err}") from err
    missing = [k for k in STORED_KEYS if not isinstance(stored, dict) or k not in stored]
    seasons = stored.get("seasons") if isinstance(stored, dict) else None
    if missing or not isinstance(seasons, list) or not seasons or not all(isinstance(x, int) for x in seasons):
        raise ReportError(f"{CONFIRM_FILE} is not a valid confirm result (missing or invalid: "
                          f"{', '.join(missing) or 'seasons'})")
    return stored


def _input_files(games_csv: str, sim_dir: str | None) -> dict[str, Path]:
    files = {Path(games_csv).name: Path(games_csv)}
    for name in INPUT_SIM_FILES:
        if sim_dir is not None and (Path(sim_dir) / name).is_file():
            files[name] = Path(sim_dir) / name
    return files


def _write(out_dir: Path, name: str, text: str) -> None:
    with open(out_dir / name, "w", newline="") as f:
        f.write(text)


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m nflpi.analytics.report")
    parser.add_argument("games_csv")
    parser.add_argument("out_dir")
    parser.add_argument("--sim-dir")
    parser.add_argument("--simulate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse(argv)
    frame = sim_backtest.load_games(sim_backtest._read(args.games_csv))
    guard_finals(frame)
    record, score_preds, sample = bench_frames(frame, BENCH_SEASONS)
    if not sample["games"]:
        raise ReportError("no regular-season games with a moneyline in the bench seasons")
    stored, reason = load_stored(args.sim_dir)
    if args.simulate and stored is None:
        raise ReportError(f"--simulate needs the stored confirm file: {reason}")
    if stored is not None:
        guard_scored(frame, [int(s) for s in stored["seasons"]])
    sim_rows, matches = simulate_confirm(frame, record, stored) if args.simulate else (None, None)
    report = build_report(record, score_preds, sample, stored, reason)
    if args.simulate:
        report["simulator"]["matches_stored_confirm"] = matches
    records = build_records(record, stored, _input_files(args.games_csv, args.sim_dir))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    export = prediction_record(record, score_preds, sim_rows)
    _write(out, "report.json", json.dumps(report, indent=1, allow_nan=False) + "\n")
    _write(out, "report.txt", render_text(report))
    _write(out, "run-records.json", json.dumps(to_native(records), indent=1, allow_nan=False) + "\n")
    _write(out, "predictions.csv", to_csv_text(export))
    _write(out, "predictions.json", to_json_text(export))


def cli(argv: list[str]) -> int:
    """main() with a clear one-line message instead of a traceback; nothing is written on a ReportError."""
    try:
        main(argv)
    except ReportError as err:
        print(f"report: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
