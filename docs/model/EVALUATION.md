# Evaluation report, run records, exports (step 18f)

Brief reference: `docs/model/OWNER_BRIEF_2026-10-13.md` section 10 and 11; decision D68. Plan row: `docs/model/PLAN.md` section 2, 18f. Code: `backend/nflpi/analytics/report.py`, `backend/nflpi/analytics/manifest.py`, `backend/nflpi/export.py`. Tests: `backend/tests/test_report.py`. Log: `docs/gauntlet/logs/step-18f.md`.

## What it is

One command turns the bench into one evaluation report, one run record per model, and the full prediction record as CSV and JSON.

```
python -m nflpi.analytics.report <games.csv> <out_dir> [--sim-dir DIR] [--simulate]
```

Writes to `<out_dir>`: `report.json`, `report.txt`, `run-records.json`, `predictions.csv`, `predictions.json`. Nothing else, no clock time in any file. Not wired into the app, no route, no migration, no database, no new dependency, `jobs.py` untouched.

* `games.csv` is the nflverse schedules file (same input as `python -m nflpi.analytics.sim_backtest`).
* `--sim-dir` points at a folder holding the stored simulator evidence `tune-result.json` and `confirm-result.json` (`docs/gauntlet/logs/step-18c-evidence`). The report **reads** them. It never reruns the simulator confirm (it can be run once).
* `--simulate` re-simulates the confirm seasons with the stored default distribution and the stored seed, only to add per-game simulator columns to the export and to check the result against the stored confirm file (clause R12). Slow (minutes). Without it those columns are missing.

## Clauses (each has one test and one mutation)

**Sample**
* R1 Bench seasons 2012 to 2025, regular season, walk-forward by season, rebuilt with the existing bench code (`backtest.predict_season`, `score_backtest.predict_season`); nothing is refitted differently and no model code is duplicated.
* R2 The report states the sample and every exclusion: regular-season finals in the file, ties left out, games without a moneyline left out, games with no score prediction, and the games left in. Gate numbers on the real file: 3,663 finals, 13 ties, 1 without moneyline, **3,649** games. Per season counts too.
* R3 D72: a game with kickoff on or after `2026-10-15` is never scored. A frame or season list that would score one raises `ReportError`; nothing is written.

**Win model**
* R4 For each of `home`, `elo`, `logistic`, `market`, `blend` (labels as in `backtest.LABELS`): n, accuracy with its interval, log loss, Brier, via `metrics.summarize`. Equal to the stored bench: market log loss 0.6094, blend 0.6107, n 3,649. Closing-line models are labelled as using the closing line.
* R5 Reliability in ten bins of the picked side's chance, 50 to 100 percent in 5-point steps (`metrics.calibration`, which buckets by the picked side, so these are ten bins, not deciles of 0 to 1) for `logistic`, `blend`, `market`; every bin has its n.
* R6 By season (n, accuracy, log loss per model) and by confidence band of the blend pick (`backtest.label_report`, plus bands 50-60, 60-70, 70+ percent of the picked side): n, share, hit rate. An empty band prints as missing, never as 0.

**Points**
* R7 Margin and total error for the three score methods (`implied`, `stats`, `blend`): n, MAE, RMSE, mean error (bias), margin and total, overall and by season. Games with a missing prediction are excluded and counted.
* R8 Closing-line outcomes against the quoted lines: home covers, away covers, pushes, overs, unders, pushes, each with n, overall and by season, settled with `nflpi.betting.settle` and the home spread `h = -spread_line` through `nflpi.data.asof.home_spread_from_nflverse` (the one place the sign is flipped; audit A13). No returns or profit are reported: there is no history of timestamped prices (PLAN 3.5). Printed as missing with that reason.

**Simulator (seasons 2022 to 2025 only, from the stored confirm file)**
* R9 For each stored variant (source x distribution): n, margin and total MAE and RMSE, interval coverage at 50, 80, 95 percent for margin and total with the nominal level beside it, simulated cover and over rates (sample-weighted mean of the stored reliability table) beside the real rates with pushes excluded and counted, tie rate, Brier against a flat 0.5. Label kept: "not shown to beat a coin flip against the closing line".
* R10 Simulator against classifier: the stored win-probability block (log loss, accuracy, gain over the blend with its interval) and gap block for each variant, labelled with the football-only / market-informed note. Verdict text is only the stored fact (interval includes zero or not); the report adds no new claim.
* R11 Without `--sim-dir`, or with a missing file, the whole simulator section is missing with the reason, and the rest of the report is unchanged.
* R12 With `--simulate`, the per-game simulator columns are added and `matches_stored_confirm` states whether the recomputed interval coverage and Brier values equal the stored ones; if not, the report says so and still writes.

**Run records**
* R13 One record per model (`home`, `elo`, `logistic`, `market`, `blend`, `score_implied`, `score_stats`, `score_blend`, and each simulator source): model name and label, `code_revision` (git HEAD, plus `git_dirty`), `lock_file_sha256` (`backend/uv.lock`), `data_sha256` (every input file, by file name), `seed` (the simulator's seed, the code constant `BASE_SEED`, noted as such in `seed_note` because `confirm-result.json` stores no seed; `--simulate` recomputing the stored confirm result is the evidence; `null` with `seed_note` "deterministic, no random draws" for the others), `cutoff` (rule: fitted on seasons S-10 to S-1 for test season S; and the latest kickoff in the record; simulator records use their own rule, "learned on seasons S-10 to S-1 before test season S; confirm seasons 2022 to 2025, read from the stored confirm-result.json", with the stored confirm file's games and seasons and the latest kickoff of those seasons, `null` with the reason in the rule if unavailable), `n_games`, `seasons`, `uses_closing_line`. A value that cannot be read (no git, no lock file) is `null` with a reason, never guessed.
* R14 Same inputs give a byte-identical `run-records.json`.

**Export**
* R15 `predictions.csv` and `predictions.json` hold one row per scored game with fixed columns: ids and teams, season, week, kickoff, result (`home_win`, margin, total), lines (`spread_line` as nflverse gives it, `home_spread` as the brief's h, `total_line`), the five win probabilities, the blend pick and its confidence band, the three score predictions (home, away), `cover_result`, `over_result`, `line_kind` ("closing, benchmark only"), and the simulator columns (missing unless `--simulate`). A missing value is an empty CSV cell and JSON `null`; NaN never appears.
* R16 Same inputs give byte-identical files (sorted by kickoff then game id; stable key order; `\n` line ends). JSON written with `allow_nan=False`.

**Report form**
* R17 Every block in `report.json` that carries a metric also carries its `n`. A missing number is `null` in JSON and the word `missing` in `report.txt`.
* R18 `report.txt` is a rendering of `report.json` and holds no number that is not in it.

## Limits

* It reports the bench, not the live app. The live `predictions` table (kinds `live` and `backfill`, market snapshots, push chance, edge, warnings) is not exported here: that needs the database and a route, which are step 18h seams.
* The closing line is a benchmark, not what was on offer at decision time (AUDIT A6); every closing-line number is labelled so.
* A blend probability of exactly 0.5 counts as an away pick in the confidence bands and in `blend_pick` (a home pick needs more than 0.5).
* The bench has been scored many times on 2022 to 2025 (AUDIT A11). This report is a read, not a new test; it ships nothing and tunes nothing.
