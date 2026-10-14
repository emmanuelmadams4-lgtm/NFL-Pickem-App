"""Evaluation report, run records and exports: frozen clauses R1 to R18 of docs/model/EVALUATION.md.

Every frame below is SYNTHETIC (hand-made, 8 games) so each number can be checked by hand.
Conventions assumed from the spec: spread_line is nflverse's (positive = home favoured), home covers when
(home - away) - spread_line > 0; "bias" is mean(predicted - actual); closing-outcome counts are counts.
"""

import csv
import hashlib
import io
import json
import math
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nflpi.analytics import backtest
from nflpi.analytics import report as rep
from nflpi.analytics.manifest import file_sha256, git_revision, run_record
from nflpi.export import PREDICTION_COLUMNS, prediction_record, to_csv_text, to_json_text

# --- synthetic fixtures --------------------------------------------------------------------------

HOME_SCORE = [27, 28, 20, 17, 13, 10, 24, 14]
AWAY_SCORE = [24, 24, 17, 24, 20, 16, 21, 31]
SPREAD = [3.0, 3.0, 3.5, -3.0, -1.5, 2.5, -2.5, 7.0]
TOTAL = [51.0, 47.0, 40.5, 41.0, 44.5, 44.5, 48.5, 40.0]
HOME_WIN = [1, 1, 1, 0, 0, 0, 1, 0]
P_MARKET = [0.8] * 4 + [0.4] * 4
P_BLEND = [0.8] * 4 + [0.35] * 4
MARGINS = [h - a for h, a in zip(HOME_SCORE, AWAY_SCORE, strict=True)]
TOTALS = [h + a for h, a in zip(HOME_SCORE, AWAY_SCORE, strict=True)]
SEASONS = [2024] * 4 + [2025] * 4
KICKOFFS = pd.to_datetime(
    ["2024-09-08T17:00:00Z", "2024-09-08T20:00:00Z", "2024-09-15T17:00:00Z", "2024-09-15T20:00:00Z",
     "2025-09-07T17:00:00Z", "2025-09-07T20:00:00Z", "2025-09-14T17:00:00Z", "2025-09-14T20:00:00Z"],
    utc=True,
)
GAME_IDS = [f"{s}_0{1 + (i % 4) // 2}_A{i}_H{i}" for i, s in enumerate(SEASONS)]
SAMPLE = {"finals": 10, "ties_excluded": 1, "no_moneyline_excluded": 1, "no_score_prediction_excluded": 0,
          "games": 8, "by_season": {2024: 4, 2025: 4}}


def make_record() -> pd.DataFrame:
    return pd.DataFrame({
        "game_id": GAME_IDS, "season": SEASONS, "week": [1, 1, 2, 2, 1, 1, 2, 2], "kickoff_utc": KICKOFFS,
        "home_team": [f"H{i}" for i in range(8)], "away_team": [f"A{i}" for i in range(8)],
        "home_win": HOME_WIN, "home_score": HOME_SCORE, "away_score": AWAY_SCORE,
        "spread_line": SPREAD, "total_line": TOTAL,
        "p_home": 0.55, "p_elo": 0.6, "p_logistic": 0.62, "p_market": P_MARKET, "p_blend": P_BLEND,
    })


def _preds(margin_err: list[float], total_err: list[float]) -> dict[str, list[float]]:
    margin = [m + e for m, e in zip(MARGINS, margin_err, strict=True)]
    total = [t + e for t, e in zip(TOTALS, total_err, strict=True)]
    pairs = list(zip(total, margin, strict=True))
    return {"home": [(t + m) / 2 for t, m in pairs], "away": [(t - m) / 2 for t, m in pairs]}


# per-method (margin error, total error) of the made-up predictions, predicted minus actual
IMPLIED_ERR = ([1, -1, 2, -2, 0, 0, 3, 1], [2, 2, -2, 2, -2, 2, -2, 2])
STATS_ERR = ([2] * 8, [0] * 8)
BLEND_ERR = ([0] * 8, [1] * 8)


def make_score_preds() -> pd.DataFrame:
    out = pd.DataFrame({"game_id": GAME_IDS, "season": SEASONS, "home_score": HOME_SCORE, "away_score": AWAY_SCORE})
    for method, (me, te) in {"implied": IMPLIED_ERR, "stats": STATS_ERR, "blend": BLEND_ERR}.items():
        p = _preds(me, te)
        out[f"pred_{method}_home"], out[f"pred_{method}_away"] = p["home"], p["away"]
    return out


def make_sim_stored() -> dict:
    def variant(source: str, distribution: str, ci: list[float], gain: float) -> dict:
        return {
            "games": 40, "source": source, "distribution": distribution,
            "is_default": distribution == "paired_residual",
            "margin_mae": 9.5, "margin_rmse": 12.25, "total_mae": 10.75, "total_rmse": 13.5,
            "coverage": {"margin": {"0.5": 0.45, "0.8": 0.7, "0.95": 0.9},
                         "total": {"0.5": 0.4, "0.8": 0.65, "0.95": 0.85}},
            "calibration": {
                "cover": {"table": [{"lo": 0.3, "hi": 0.5, "n": 10, "mean_pred": 0.4, "observed": 0.5},
                                    {"lo": 0.5, "hi": 0.7, "n": 30, "mean_pred": 0.6, "observed": 0.7}],
                          "brier": 0.2825, "brier_flat_half": 0.25},
                "over": {"table": [{"lo": 0.2, "hi": 0.4, "n": 20, "mean_pred": 0.3, "observed": 0.4},
                                   {"lo": 0.4, "hi": 0.6, "n": 20, "mean_pred": 0.5, "observed": 0.6}],
                         "brier": 0.2675, "brier_flat_half": 0.25},
            },
            "tie_rate": {"sim": 0.0125, "real": 0.0275},
            "key_numbers": {"3": {"sim": 0.1125, "real": 0.15}, "7": {"sim": 0.0625, "real": 0.0875}},
            "win_gap_vs_blend": {"mean_abs": 0.1125, "max_abs": 0.5225, "n_above_0.10": 21, "largest": []},
            "win_probability": {"games": 39, "excludes_ties": True, "log_loss": 0.6775, "accuracy": 0.6425,
                                "blend_log_loss": 0.6125, "market_log_loss": 0.6075, "accuracy_blend": 0.6775,
                                "log_loss_gain_vs_blend": gain, "log_loss_gain_ci": ci,
                                "accuracy_diff_vs_blend": -0.035},
        }

    return {"seasons": [2024, 2025], "n_simulations": 100, "default_distribution": "paired_residual",
            "sources_note": "market_informed variants are priced at the closing line, so football_only is the "
                            "fair test", "games": 40,
            "variants": [variant("football_only", "paired_residual", [-0.0875, -0.0425], -0.0675),
                         variant("market_informed", "poisson", [-0.0125, 0.0225], 0.005)]}


def build(sim=None, record=None, score_preds=None) -> dict:
    return rep.build_report(make_record() if record is None else record,
                            make_score_preds() if score_preds is None else score_preds, dict(SAMPLE), sim)


def numbers_in(obj) -> list[float]:
    """Every int/float anywhere in a nested structure."""
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in numbers_in(v)]
    if isinstance(obj, (list, tuple)):
        return [x for v in obj for x in numbers_in(v)]
    return []


def season_entry(block, season: int):
    """The entry for a season whether by_season is a dict keyed by int/str or a list of rows."""
    if isinstance(block, dict):
        return block[str(season)] if str(season) in block else block[season]
    return next(row for row in block if int(row["season"]) == season)


def model_entry(entry, model: str) -> dict:
    return entry[model] if model in entry else entry["models"][model]


def nflverse_row(game_id: str, season: int, day: str, home_score: int, away_score: int) -> dict[str, str]:
    return {
        "game_id": game_id, "season": str(season), "week": "1", "game_type": "REG", "gameday": day,
        "gametime": "13:00", "weekday": "Sunday", "away_team": "T01", "home_team": "T02",
        "away_score": str(away_score), "home_score": str(home_score), "location": "Home", "div_game": "0",
        "roof": "outdoors", "surface": "grass", "stadium": "S", "stadium_id": "S1", "away_rest": "7",
        "home_rest": "7", "away_qb_name": "", "home_qb_name": "", "away_coach": "", "home_coach": "",
        "temp": "", "wind": "", "home_moneyline": "-150", "away_moneyline": "130", "spread_line": "3.0",
        "total_line": "44.5", "overtime": "0",
    }


def write_games_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


# --- R1 / R3 sample and the D72 gate -------------------------------------------------------------

def test_r1_report_reuses_the_existing_bench_code_and_duplicates_no_model():
    # Arrange
    source = Path(rep.__file__).read_text()

    # Act / Assert
    assert "predict_season" in source
    assert "LogisticRegression" not in source and "sklearn" not in source
    assert not hasattr(rep, "fit_logistic")


def test_r3_a_kickoff_on_or_after_the_d72_date_raises_and_nothing_is_written(tmp_path):
    # Arrange
    assert rep.D72_FIRST_PROTECTED == "2026-10-15"
    games = write_games_csv(tmp_path / "games.csv", [nflverse_row("2026_06_T01_T02", 2026, "2026-10-18", 20, 17)])
    out = tmp_path / "out"

    # Act / Assert
    assert issubclass(rep.ReportError, ValueError)
    with pytest.raises(rep.ReportError):
        rep.main([str(games), str(out)])
    assert not out.exists() or list(out.iterdir()) == []


def test_r3_bench_frames_refuses_a_frame_holding_a_protected_game(tmp_path):
    # Arrange
    from nflpi.analytics import sim_backtest
    frame = sim_backtest.load_games([nflverse_row("2026_06_T01_T02", 2026, "2026-10-18", 20, 17)])

    # Act / Assert
    with pytest.raises(rep.ReportError):
        rep.bench_frames(frame, [2026])


def test_r2_report_states_the_sample_and_every_exclusion():
    # Arrange / Act
    sample = build()["sample"]

    # Assert
    assert (sample["finals"], sample["ties_excluded"], sample["no_moneyline_excluded"]) == (10, 1, 1)
    assert sample["no_score_prediction_excluded"] == 0 and sample["games"] == 8
    assert {str(k): v for k, v in sample["by_season"].items()} == {"2024": 4, "2025": 4}


# --- R4 to R6 win model --------------------------------------------------------------------------

def test_r4_market_accuracy_log_loss_and_brier_match_hand_computation():
    # Arrange: market is right on 3 of 4 home picks and 3 of 4 away picks
    expected_ll = (3 * -math.log(0.8) - math.log(0.2) + 3 * -math.log(0.6) - math.log(0.4)) / 8

    # Act
    market = build()["win"]["market"]

    # Assert
    assert market["n"] == 8
    assert market["accuracy"] == pytest.approx(0.75)
    assert market["log_loss"] == pytest.approx(expected_ll)
    assert market["brier"] == pytest.approx((0.76 + 0.84) / 8)
    lo, hi = market["accuracy_ci"]
    assert 0.0 <= lo <= 0.75 <= hi <= 1.0


def test_r4_every_model_is_present_with_its_label_and_closing_line_flag():
    # Arrange / Act
    win = build()["win"]

    # Assert
    assert set(win) == {"home", "elo", "logistic", "market", "blend"}
    for model, entry in win.items():
        assert entry["label"] == backtest.LABELS[model]
        assert entry["uses_closing_line"] is (model in {"market", "blend"})


def test_r5_reliability_has_ten_bins_models_and_an_n_on_every_bin():
    # Arrange / Act
    reliability = build()["reliability"]

    # Assert
    assert set(reliability) == {"logistic", "blend", "market"}
    for bins in reliability.values():
        assert all("n" in b for b in bins) and sum(b["n"] for b in bins) == 8
    assert sorted(b["n"] for b in reliability["market"] if b["n"]) == [4, 4]
    assert len(reliability["market"]) in {10, 2}  # ten bins, or only the occupied ones if empties are omitted


def test_r6_by_season_and_confidence_bands_count_and_hit_rates_by_hand():
    # Arrange / Act
    report = build()

    # Assert by season: market 3 of 4 each season
    m24 = model_entry(season_entry(report["by_season"], 2024), "market")
    m25 = model_entry(season_entry(report["by_season"], 2025), "market")
    assert (m24["n"], m24["accuracy"]) == (4, pytest.approx(0.75))
    assert m24["log_loss"] == pytest.approx((3 * -math.log(0.8) - math.log(0.2)) / 4)
    assert (m25["n"], m25["accuracy"]) == (4, pytest.approx(0.75))
    # Assert bands: blend 0.8 pick is 70+ (4 games, 3 hits); away pick at 0.65 is 60-70 (4 games, 3 hits)
    bands = report["confidence_bands"]
    filled = [b for b in bands if b["n"]]
    assert sorted(b["n"] for b in filled) == [4, 4]
    assert all(b["hit_rate"] == pytest.approx(0.75) and b["share"] == pytest.approx(0.5) for b in filled)
    empty = [b for b in bands if not b["n"]]
    assert empty and all(b["hit_rate"] is None for b in empty)


# --- R7 / R8 points and closing outcomes ---------------------------------------------------------

def test_r7_score_errors_per_method_match_hand_computation():
    # Arrange / Act
    points = build()["points"]

    # Assert: implied margin errors [1,-1,2,-2,0,0,3,1], total errors [2,2,-2,2,-2,2,-2,2]
    implied = points["implied"]
    assert implied["margin"]["n"] == 8
    assert implied["margin"]["mae"] == pytest.approx(10 / 8)
    assert implied["margin"]["rmse"] == pytest.approx(math.sqrt(20 / 8))
    assert implied["margin"]["bias"] == pytest.approx(4 / 8)
    assert (implied["total"]["mae"], implied["total"]["rmse"]) == (pytest.approx(2.0), pytest.approx(2.0))
    assert implied["total"]["bias"] == pytest.approx(0.5)
    assert points["stats"]["margin"]["bias"] == pytest.approx(2.0) and points["stats"]["total"]["mae"] == 0
    assert points["blend"]["margin"]["rmse"] == 0 and points["blend"]["total"]["bias"] == pytest.approx(1.0)
    assert points["by_season"]  # per season detail exists


def test_r7_games_with_a_missing_prediction_are_excluded_from_that_method_only():
    # Arrange
    preds = make_score_preds()
    preds.loc[0, "pred_stats_home"] = np.nan

    # Act
    points = build(score_preds=preds)["points"]

    # Assert
    assert points["stats"]["margin"]["n"] == 7 and points["stats"]["total"]["n"] == 7
    assert points["implied"]["margin"]["n"] == 8 and points["blend"]["total"]["n"] == 8


def test_r8_closing_outcomes_count_pushes_and_use_the_nflverse_spread_sign():
    # Arrange / Act: spread +3 home favoured, home wins by 3 -> push; by 4 -> home covers
    outcomes = build()["closing_outcomes"]

    # Assert overall
    spread, total = outcomes["overall"]["spread"], outcomes["overall"]["total"]
    assert (spread["n"], spread["home_cover"], spread["away_cover"], spread["push"]) == (8, 2, 5, 1)
    assert (total["n"], total["over"], total["under"], total["push"]) == (8, 2, 4, 2)
    # Assert by season
    s24 = season_entry(outcomes["by_season"], 2024)
    assert (s24["spread"]["home_cover"], s24["spread"]["away_cover"], s24["spread"]["push"]) == (1, 2, 1)
    assert (s24["total"]["over"], s24["total"]["under"], s24["total"]["push"]) == (1, 1, 2)
    # Assert returns are missing with a reason
    assert "reason" in outcomes and not outcomes.get("returns") or "reason" in json.dumps(outcomes["returns"])


def test_r8_spread_sign_conversion_is_the_one_existing_helper():
    # Arrange / Act
    from nflpi.data.asof import home_spread_from_nflverse

    # Assert: nflverse +3 (home favoured) is h = -3
    assert home_spread_from_nflverse(3.0) == -3.0 and home_spread_from_nflverse(-2.5) == 2.5


def test_r8_a_home_underdog_spread_flips_the_sign():
    # Arrange: one game, nflverse spread -3 (home is a 3 point underdog), home loses by 7 -> away covers;
    # home wins 24-23 -> home covers
    record = make_record().iloc[[3, 6]].copy()
    record["home_score"], record["away_score"] = [17, 24], [24, 23]
    record["home_win"] = [0, 1]
    record["spread_line"] = [-3.0, -3.0]
    preds = make_score_preds().iloc[[3, 6]].copy()

    # Act
    spread = build(record=record, score_preds=preds)["closing_outcomes"]["overall"]["spread"]

    # Assert
    assert (spread["home_cover"], spread["away_cover"], spread["push"]) == (1, 1, 0)


# --- R9 to R11 simulator -------------------------------------------------------------------------

def test_r9_simulator_variants_carry_n_errors_coverage_and_weighted_rates():
    # Arrange / Act
    simulator = build(sim=make_sim_stored())["simulator"]

    # Assert
    assert [(v["source"], v["distribution"]) for v in simulator["variants"]] == [
        ("football_only", "paired_residual"), ("market_informed", "poisson")]
    nums = numbers_in(simulator["variants"][0])
    for expected in (40, 9.5, 12.25, 10.75, 13.5, 0.45, 0.7, 0.9, 0.4, 0.65, 0.85, 0.0125, 0.0275, 0.25, 0.2825):
        assert any(x == pytest.approx(expected) for x in nums), expected
    # sample-weighted: cover (10*0.4 + 30*0.6)/40 = 0.55 vs real (10*0.5 + 30*0.7)/40 = 0.65
    for expected in (0.55, 0.65):  # over: (20*0.3 + 20*0.5)/40 = 0.4 vs (20*0.4 + 20*0.6)/40 = 0.5
        assert any(x == pytest.approx(expected) for x in nums), expected
    assert "not shown to beat a coin flip against the closing line" in json.dumps(simulator).lower()


def test_r10_simulator_win_probability_is_reported_as_stored_with_its_note():
    # Arrange / Act
    simulator = build(sim=make_sim_stored())["simulator"]
    wins = [numbers_in(v["win_probability"]) for v in simulator["variants"]]

    # Assert: stored values and intervals are carried over unchanged
    for expected in (0.6775, 0.6425, -0.0675, -0.0875, -0.0425, 0.6125, 0.6075):
        assert any(x == pytest.approx(expected) for x in wins[0]), expected
    assert any(x == pytest.approx(0.005) for x in wins[1])
    assert any(x == pytest.approx(0.0225) for x in wins[1])
    assert "market_informed" in json.dumps(simulator)  # the stored football-only / market-informed note


def test_r11_without_stored_results_the_simulator_is_missing_with_a_reason_and_the_rest_is_unchanged():
    # Arrange / Act
    without = build(sim=None)
    with_sim = build(sim=make_sim_stored())

    # Assert
    assert without["simulator"].get("variants") in (None, [])
    assert without["simulator"].get("reason")
    rest = lambda r: {k: v for k, v in r.items() if k not in {"simulator", "notes"}}  # noqa: E731
    assert rest(without) == rest(with_sim)


def test_r11_main_with_an_empty_sim_dir_writes_the_report_with_a_missing_simulator(tmp_path, monkeypatch):
    # Arrange
    games = write_games_csv(tmp_path / "games.csv", [nflverse_row("2025_01_T01_T02", 2025, "2025-09-07", 20, 17)])
    monkeypatch.setattr(rep, "bench_frames", lambda frame, seasons: (make_record(), make_score_preds(), dict(SAMPLE)))
    (tmp_path / "sim").mkdir()
    out = tmp_path / "out"

    # Act
    rep.main([str(games), str(out), "--sim-dir", str(tmp_path / "sim")])

    # Assert
    report = json.loads((out / "report.json").read_text())
    assert report["simulator"].get("variants") in (None, []) and report["simulator"]["reason"]


# --- R12 simulator columns in the export ---------------------------------------------------------

def test_r12_simulator_export_columns_are_missing_without_sim_rows_and_filled_with_them():
    # Arrange
    base = prediction_record(make_record(), make_score_preds())
    sim_cols = [c for c in PREDICTION_COLUMNS if base[c].isna().all()]
    sim_rows = pd.DataFrame({"game_id": GAME_IDS, **{c: 0.5 for c in sim_cols}})

    # Act
    filled = prediction_record(make_record(), make_score_preds(), sim_rows)

    # Assert
    assert sim_cols  # there are simulator columns, all missing by default
    assert list(filled.columns) == PREDICTION_COLUMNS
    assert all(filled[c].notna().all() for c in sim_cols)


# --- R13 / R14 run records -----------------------------------------------------------------------

def make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "backend").mkdir(parents=True)
    (repo / "backend" / "uv.lock").write_text("lock-contents-v1\n")
    data = tmp_path / "games.csv"
    data.write_text("game_id\nx\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "synthetic")
    return repo, data


def record_for(repo: Path, data: Path, model: str = "market", seed=None) -> dict:
    return run_record(
        model, label="Betting market (closing line)", seed=seed,
        seed_note=None if seed else "deterministic, no random draws",
        cutoff_rule="fitted on seasons S-10 to S-1 for test season S", latest_kickoff="2025-09-14T20:00:00Z",
        n_games=8, seasons=[2024, 2025], uses_closing_line=True, data_files={"games.csv": data}, repo_root=repo,
    )


def test_r13_run_record_reads_revision_lock_hash_and_data_hash(tmp_path):
    # Arrange
    repo, data = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")

    # Act
    rec = record_for(repo, data, seed=None)

    # Assert
    assert rec["code_revision"] == head and rec["git_dirty"] is False
    assert rec["lock_file_sha256"] == hashlib.sha256(b"lock-contents-v1\n").hexdigest()
    assert rec["data_sha256"] == {"games.csv": hashlib.sha256(data.read_bytes()).hexdigest()}
    assert file_sha256(data) == rec["data_sha256"]["games.csv"]
    assert rec["seed"] is None and rec["seed_note"] == "deterministic, no random draws"
    assert "S-10 to S-1" in json.dumps(rec["cutoff"]) and "2025-09-14T20:00:00Z" in json.dumps(rec["cutoff"])
    assert (rec["n_games"], rec["seasons"], rec["uses_closing_line"]) == (8, [2024, 2025], True)
    assert git_revision(repo) == (head, False)


def test_r13_a_stored_simulator_seed_is_kept_and_a_dirty_tree_is_flagged(tmp_path):
    # Arrange
    repo, data = make_repo(tmp_path)
    (repo / "backend" / "uv.lock").write_text("changed\n")

    # Act
    rec = record_for(repo, data, model="sim_football_only", seed=20261013)

    # Assert
    assert rec["seed"] == 20261013 and rec["git_dirty"] is True


def test_r13_unreadable_things_are_null_with_a_reason_never_guessed(tmp_path):
    # Arrange: no git repository, no lock file
    bare = tmp_path / "bare"
    bare.mkdir()
    data = tmp_path / "games.csv"
    data.write_text("x\n")

    # Act
    rec = record_for(bare, data)

    # Assert
    assert rec["code_revision"] is None and rec["git_dirty"] is None
    assert rec["lock_file_sha256"] is None
    reasons = {k: v for k, v in rec.items() if "reason" in k and v}
    assert any("git" in k or "revision" in k for k in reasons) and any("lock" in k for k in reasons)
    assert git_revision(bare)[0] is None


def test_r14_same_inputs_give_a_byte_identical_run_record(tmp_path):
    # Arrange
    repo, data = make_repo(tmp_path)

    # Act
    first = json.dumps(record_for(repo, data), sort_keys=False, allow_nan=False)
    second = json.dumps(record_for(repo, data), sort_keys=False, allow_nan=False)

    # Assert
    assert first == second


def test_r14_main_writes_identical_run_records_twice(tmp_path, monkeypatch):
    # Arrange
    games = write_games_csv(tmp_path / "games.csv", [nflverse_row("2025_01_T01_T02", 2025, "2025-09-07", 20, 17)])
    monkeypatch.setattr(rep, "bench_frames", lambda frame, seasons: (make_record(), make_score_preds(), dict(SAMPLE)))

    # Act
    rep.main([str(games), str(tmp_path / "a")])
    rep.main([str(games), str(tmp_path / "b")])

    # Assert: exactly the five documented files, same bytes
    names = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert names == ["predictions.csv", "predictions.json", "report.json", "report.txt", "run-records.json"]
    for name in names:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


# --- R15 / R16 export ----------------------------------------------------------------------------

def test_r15_export_has_fixed_columns_one_row_per_game_and_settled_results():
    # Arrange / Act
    df = prediction_record(make_record(), make_score_preds())

    # Assert
    assert list(df.columns) == PREDICTION_COLUMNS and len(df) == 8
    for name in ("game_id", "season", "week", "home_team", "away_team", "home_win", "spread_line", "home_spread",
                 "total_line", "cover_result", "over_result", "line_kind"):
        assert name in PREDICTION_COLUMNS, name
    by_id = df.set_index("game_id")
    first = by_id.loc[GAME_IDS[0]]
    assert first["home_spread"] == -3.0 and first["spread_line"] == 3.0
    assert first["cover_result"] == "push" and first["over_result"] == "push"
    assert by_id.loc[GAME_IDS[1], "cover_result"] != "push"
    assert set(df["line_kind"]) == {"closing, benchmark only"}


def test_r15_a_missing_value_is_an_empty_csv_cell_and_json_null_never_nan():
    # Arrange
    record = make_record()
    record.loc[2, "p_market"] = np.nan
    df = prediction_record(record, make_score_preds())

    # Act
    csv_text, json_text = to_csv_text(df), to_json_text(df)

    # Assert
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert next(r for r in rows if r["game_id"] == GAME_IDS[2])["p_market"] == ""
    assert not re.search(r"\bnan\b", csv_text, re.I) and not re.search(r"\bnan\b", json_text, re.I)
    data = json.loads(json_text)  # json.loads accepts NaN, so also check the text itself
    assert next(r for r in data if r["game_id"] == GAME_IDS[2])["p_market"] is None


def test_r16_export_is_sorted_by_kickoff_then_game_id_stable_and_byte_identical():
    # Arrange: shuffled input, with two games sharing a kickoff
    record = make_record()
    record.loc[1, "kickoff_utc"] = record.loc[0, "kickoff_utc"]
    record.loc[0, "game_id"], record.loc[1, "game_id"] = "2024_01_Z", "2024_01_A"
    scores = make_score_preds()
    scores.loc[0, "game_id"], scores.loc[1, "game_id"] = "2024_01_Z", "2024_01_A"
    shuffled = record.sample(frac=1, random_state=3).reset_index(drop=True)

    # Act
    one = prediction_record(shuffled, scores)
    two = prediction_record(record, scores)

    # Assert
    assert list(one["game_id"][:2]) == ["2024_01_A", "2024_01_Z"]
    assert to_csv_text(one) == to_csv_text(two) and to_json_text(one) == to_json_text(two)
    assert "\r" not in to_csv_text(one) and "\r" not in to_json_text(one)
    first_row = json.loads(to_json_text(one), object_pairs_hook=lambda pairs: pairs)[0]
    assert [k for k, _ in first_row] == PREDICTION_COLUMNS
    assert list(csv.reader(io.StringIO(to_csv_text(one))))[0] == PREDICTION_COLUMNS


def test_r16_json_text_rejects_nan_values_instead_of_writing_them():
    # Arrange
    df = prediction_record(make_record(), make_score_preds())

    # Act
    text = to_json_text(df.assign(p_blend=np.nan))

    # Assert: NaN becomes null, never the bare token
    assert "NaN" not in text and all(r["p_blend"] is None for r in json.loads(text))


# --- R17 / R18 report form -----------------------------------------------------------------------

METRIC_KEYS = {"accuracy", "log_loss", "brier", "mae", "rmse", "home_cover"}


def missing_n(node, path="report") -> list[str]:
    bad = []
    if isinstance(node, dict):
        if METRIC_KEYS & set(node) and "n" not in node and "games" not in node:
            bad.append(path)
        for k, v in node.items():
            bad += missing_n(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            bad += missing_n(v, f"{path}[{i}]")
    return bad


def nan_report() -> dict:
    preds = make_score_preds()
    for col in [c for c in preds.columns if c.startswith("pred_stats")]:
        preds[col] = np.nan
    return build(sim=make_sim_stored(), score_preds=preds)


def test_r17_every_metric_block_carries_its_n():
    # Arrange / Act
    report = build(sim=make_sim_stored())

    # Assert
    assert missing_n(report) == []
    assert missing_n(nan_report()) == []


def test_r17_a_missing_number_is_null_in_json_and_the_word_missing_in_text():
    # Arrange: no stats prediction at all
    report = nan_report()

    # Act
    dumped = json.dumps(report, allow_nan=False)
    text = rep.render_text(report)

    # Assert
    assert report["points"]["stats"]["margin"]["mae"] is None and report["points"]["stats"]["margin"]["n"] == 0
    assert "NaN" not in dumped and json.loads(dumped) == report
    assert "missing" in text
    assert not re.search(r"\b(nan|none|null)\b", text, re.I)


def test_r18_report_text_holds_no_number_that_is_not_in_the_report():
    # Arrange
    report = build(sim=make_sim_stored())
    text = re.sub(r"(?<=\d),(?=\d{3})", "", rep.render_text(report))
    token = re.compile(r"\d+(?:\.\d+)?")
    allowed = [abs(x) for x in numbers_in(report)]
    allowed += [x * 100 for x in allowed]
    allowed += [float(t) for t in token.findall(json.dumps([v for v in _strings(report)]))]

    # Act
    tokens = token.findall(text)
    stray = [t for t in tokens
             if not any(abs(a - float(t)) <= 0.5 * 10 ** -len(t.partition(".")[2]) + 1e-9 for a in allowed)]

    # Assert
    assert len(tokens) >= 20
    assert stray == []


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def test_r14_r16_the_report_and_its_text_are_deterministic():
    # Arrange / Act
    a, b = build(sim=make_sim_stored()), build(sim=make_sim_stored())

    # Assert
    assert json.dumps(a, allow_nan=False) == json.dumps(b, allow_nan=False)
    assert rep.render_text(a) == rep.render_text(b)


# --- the real file gate --------------------------------------------------------------------------

def _real_csv() -> str | None:
    path = os.environ.get("REPORT_GAMES_CSV")
    return path if path and Path(path).is_file() else None


@pytest.mark.skipif(_real_csv() is None, reason="set REPORT_GAMES_CSV to the nflverse games.csv to run the gate")
def test_real_file_gate_reproduces_the_stored_bench(tmp_path):
    # Arrange / Act
    rep.main([_real_csv(), str(tmp_path)])
    report = json.loads((tmp_path / "report.json").read_text())

    # Assert
    sample = report["sample"]
    assert (sample["finals"], sample["ties_excluded"], sample["no_moneyline_excluded"]) == (3663, 13, 1)
    assert sample["games"] == 3649
    assert report["win"]["market"]["n"] == 3649
    assert round(report["win"]["market"]["log_loss"], 4) == 0.6094
    assert round(report["win"]["blend"]["log_loss"], 4) == 0.6107
    seasons = sorted(int(s) for s in sample["by_season"])
    assert (seasons[0], seasons[-1]) == (2012, 2025)
    csv_rows = list(csv.DictReader(io.StringIO((tmp_path / "predictions.csv").read_text())))
    assert len(csv_rows) == 3649 and len(json.loads((tmp_path / "predictions.json").read_text())) == 3649


# --- mutation re-run additions (step 18f) --------------------------------------------------------

LITERAL_HEADER = [
    "game_id", "season", "week", "kickoff_utc", "home_team", "away_team", "home_win", "home_score", "away_score",
    "margin", "total", "spread_line", "home_spread", "total_line", "p_home", "p_elo", "p_logistic", "p_market",
    "p_blend", "blend_pick", "blend_confidence_band",
    "pred_implied_home", "pred_implied_away", "pred_stats_home", "pred_stats_away", "pred_blend_home",
    "pred_blend_away", "cover_result", "over_result", "line_kind",
    *[f"sim_{s}_{m}" for s in ("football_only", "market_informed")
      for m in ("mean_margin", "mean_total", "p_win_half", "p_tie", "p_cover_nopush", "p_over_nopush")],
]


def _frame_at(kickoff: str, season: int = 2025) -> pd.DataFrame:
    return pd.DataFrame({"season": [season], "kickoff_utc": [kickoff], "home_score": [20.0], "away_score": [17.0]})


def test_r1_bench_seasons_are_exactly_2012_to_2025():
    assert rep.BENCH_SEASONS == list(range(2012, 2026))
    assert (rep.BENCH_SEASONS[0], rep.BENCH_SEASONS[-1], len(rep.BENCH_SEASONS)) == (2012, 2025, 14)


def test_r2_sample_counts_one_tie_and_one_game_without_a_moneyline():
    # Arrange: 3 regular-season finals (one tie), one non-final, one playoff; one game lacks p_market
    frame = pd.DataFrame({
        "game_type": ["REG", "REG", "REG", "REG", "POST"], "status": ["final", "final", "final", "scheduled", "final"],
        "season": [2024] * 5, "home_score": [20, 17, 10, None, 30], "away_score": [10, 17, 13, None, 3],
    })
    preds = pd.DataFrame({"p_market": [0.6, 0.5, np.nan]})
    record = pd.DataFrame({"season": [2024, 2024], "game_id": ["a", "b"]})
    score_preds = pd.DataFrame({c: [1.0, 2.0] for c in rep.score_backtest.PRED_COLS})

    # Act
    sample = rep._sample(frame, [2024], preds, record, score_preds)

    # Assert
    assert sample["finals"] == 3
    assert sample["ties_excluded"] == 1
    assert sample["no_moneyline_excluded"] == 1
    assert sample["games"] == 2 and sample["by_season"] == {2024: 2}


def test_r3_d72_boundary_midnight_utc_raises_and_one_second_earlier_passes():
    # Arrange / Act / Assert
    with pytest.raises(rep.ReportError):
        rep.guard_scored(_frame_at("2026-10-15T00:00:00Z"), [2025])
    rep.guard_scored(_frame_at("2026-10-14T23:59:59Z"), [2025])
    with pytest.raises(rep.ReportError):
        rep.guard_finals(_frame_at("2026-10-15T00:00:00Z"))
    rep.guard_finals(_frame_at("2026-10-14T23:59:59Z"))


def test_r3_season_2026_is_refused_even_when_no_kickoff_is_late():
    with pytest.raises(rep.ReportError):
        rep.guard_scored(_frame_at("2026-09-10T00:00:00Z", season=2026), [2026])


def test_r6_a_picked_probability_exactly_on_a_band_edge_lands_in_the_upper_band():
    # Arrange: picked probabilities 0.5, 0.6 and 0.7 (home lost only at 0.7)
    record = pd.DataFrame({"p_blend": [0.5, 0.6, 0.7], "home_win": [1, 1, 0]})

    # Act
    bands = {b["band"]: b for b in rep._confidence_bands(record)}

    # Assert
    assert (bands["50-60%"]["n"], bands["60-70%"]["n"], bands["70%+"]["n"]) == (1, 1, 1)
    assert bands["60-70%"]["hit_rate"] == 1.0
    assert bands["50-60%"]["hit_rate"] == 0.0 and bands["70%+"]["hit_rate"] == 0.0


def test_r9_pushes_are_games_minus_the_calibration_n():
    # Arrange: 45 games, calibration tables hold 40 each
    variant = {**make_sim_stored()["variants"][0], "games": 45}

    # Act
    rates, _ = rep._rates(variant)

    # Assert
    assert rates["cover"]["n"] == 40 and rates["cover"]["pushes"] == 5
    assert rates["over"]["n"] == 40 and rates["over"]["pushes"] == 5


@pytest.mark.parametrize(("ci", "includes"), [([0.001, 0.02], False), ([-0.02, -0.001], False),
                                              ([-0.01, 0.02], True), ([0.0, 0.02], True)])
def test_r10_stored_interval_is_reported_as_stored(ci, includes):
    # Arrange
    variant = make_sim_stored()["variants"][0]
    variant["win_probability"]["log_loss_gain_ci"] = ci

    # Act
    out = rep._sim_variant(variant)

    # Assert
    assert out["verdict"]["gain_interval_includes_zero"] is includes
    assert out["verdict"]["text"].endswith("includes zero" if includes else "excludes zero")
    assert out["win_probability"]["log_loss_gain_ci"] == ci


def test_r11_missing_confirm_file_gives_the_exact_reason(tmp_path, monkeypatch):
    # Arrange
    expected = f"confirm-result.json not found in {tmp_path}"
    games = write_games_csv(tmp_path / "games.csv", [nflverse_row("2025_01_T01_T02", 2025, "2025-09-07", 20, 17)])
    monkeypatch.setattr(rep, "bench_frames", lambda frame, seasons: (make_record(), make_score_preds(), dict(SAMPLE)))
    out = tmp_path / "out"

    # Act
    stored, reason = rep.load_stored(str(tmp_path))
    rep.main([str(games), str(out), "--sim-dir", str(tmp_path)])

    # Assert
    assert stored is None and reason == expected
    assert json.loads((out / "report.json").read_text())["simulator"]["reason"] == expected
    assert rep.load_stored(None) == (None, rep.NO_SIM_REASON)


def _confirm_like(coverage_margin: float = 0.45, brier_cover: float = 0.2825) -> dict:
    return {"coverage": {"margin": {"0.5": coverage_margin, "0.8": 0.7}, "total": {"0.5": 0.4, "0.8": 0.65}},
            "calibration": {"cover": {"brier": brier_cover}, "over": {"brier": 0.2675}}}


def test_r12_same_is_true_for_equal_results_and_false_on_a_1e3_difference():
    # Arrange / Act / Assert
    assert rep._same(_confirm_like(), _confirm_like()) is True
    assert rep._same(_confirm_like(coverage_margin=0.451), _confirm_like()) is False
    assert rep._same(_confirm_like(brier_cover=0.2835), _confirm_like()) is False


@pytest.mark.parametrize("matches", [False, True])
def test_r12_main_simulate_writes_the_match_result_as_computed(tmp_path, monkeypatch, matches):
    # Arrange
    games = write_games_csv(tmp_path / "games.csv", [nflverse_row("2025_01_T01_T02", 2025, "2025-09-07", 20, 17)])
    sim = tmp_path / "sim"
    sim.mkdir()
    (sim / "confirm-result.json").write_text(json.dumps(make_sim_stored()))
    monkeypatch.setattr(rep, "bench_frames", lambda frame, seasons: (make_record(), make_score_preds(), dict(SAMPLE)))
    monkeypatch.setattr(rep, "simulate_confirm", lambda frame, record, stored: (None, matches))
    out = tmp_path / "out"

    # Act
    rep.main([str(games), str(out), "--sim-dir", str(sim), "--simulate"])

    # Assert
    assert json.loads((out / "report.json").read_text())["simulator"]["matches_stored_confirm"] is matches


def test_r15_margin_and_total_are_home_minus_away_and_home_plus_away_with_a_literal_header():
    # Arrange / Act
    df = prediction_record(make_record(), make_score_preds())

    # Assert: first game is 27-24, the last is 14-31
    assert list(df.columns) == LITERAL_HEADER and len(LITERAL_HEADER) == 42
    assert (df.loc[0, "margin"], df.loc[0, "total"]) == (3, 51)
    assert (df.loc[7, "margin"], df.loc[7, "total"]) == (-17, 45)
    assert df["margin"].tolist() == MARGINS and df["total"].tolist() == TOTALS
    assert to_csv_text(df).splitlines()[0] == ",".join(LITERAL_HEADER)
    assert list(json.loads(to_json_text(df))[0]) == LITERAL_HEADER


def test_r17_a_none_value_renders_as_the_word_missing_not_zero():
    # Arrange / Act
    text = rep.render_text({"a": {"n": 3, "mae": None}})

    # Assert
    assert "mae: missing" in text and "mae: 0" not in text
    assert "n: 3" in text


def test_r18_floats_render_at_four_decimals_and_ints_have_no_decimals():
    # Arrange
    report = build(sim=make_sim_stored())
    expected_ll = (3 * -math.log(0.8) - math.log(0.2) + 3 * -math.log(0.6) - math.log(0.4)) / 8

    # Act
    text = rep.render_text(report)

    # Assert
    assert "x: 0.6094" in rep.render_text({"x": 0.6094})
    assert f"log_loss: {expected_ll:.4f}" in text and f"{expected_ll:.4f}" == "0.5910"
    assert "blend_log_loss: 0.6125" in text and "market_log_loss: 0.6075" in text
    assert "mean_abs: 0.1125" in text
