# Step 18f mutation sweep

Each mutation applied alone to the clean tree, run with `uv run pytest tests/test_report.py -q -x` (31 pass, 1 skipped real-file gate), then restored with `git checkout -- backend/nflpi`. Line numbers are of the unmutated files. The real-file gate test is skipped (no REPORT_GAMES_CSV), so mutants only that gate would catch show as SURVIVED.

| ID | Clause | File:line | Mutation | Result |
|----|--------|-----------|----------|--------|
| R1 | R1 | report.py:32 | `range(2012, 2026)` -> `range(2013, 2026)` | SURVIVED |
| R2 | R2 | report.py:89 | tie count `==` -> `!=` | SURVIVED |
| R2b | R2 | report.py:90 | `no_moneyline_excluded` forced to 0 | SURVIVED |
| R3 | R3 | report.py:72 | kickoff gate `>=` -> `>` (midnight boundary) | SURVIVED |
| R3b | R3 | report.py:69 | season gate `>= 2026` -> `> 2026` | SURVIVED |
| R4 | R4 | report.py:43 | `CLOSING_LINE_MODELS` drops blend | KILLED |
| R5 | R5 | report.py:34 | `RELIABILITY_BINS` 20 -> 19 | KILLED |
| R6 | R6 | report.py:147 | empty band hit_rate None -> 0.0 | KILLED |
| R6b | R6 | report.py:144 | band lower edge `>=` -> `>` | SURVIVED |
| R7 | R7 | report.py:168 | margin error sign flipped (bias sign) | KILLED |
| R7b | R7 | report.py:158 | drop the non-finite exclusion (`nan_to_num`) | KILLED |
| R8 | R8 | export.py:31 | home_cover / away_cover swapped | KILLED |
| R8b | R8 | export.py:67 | skip the `home_spread_from_nflverse` sign flip | KILLED |
| R8c | R8 | report.py:184 | total push count forced to 0 | KILLED |
| R9 | R9 | report.py:199 | sample-weighted mean -> unweighted mean | KILLED |
| R9b | R9 | report.py:208 | `pushes` forced to 0 | SURVIVED |
| R10 | R10 | report.py:217 | `lo <= 0 <= hi` -> `lo <= 0` | SURVIVED |
| R11 | R11 | report.py:370 | missing-file reason dropped to None | SURVIVED |
| R12 | R12 | report.py:266 | `_same` `all` -> `any` | SURVIVED |
| R12b | R12 | report.py:409 | `matches_stored_confirm` forced True | SURVIVED |
| R13 | R13 | manifest.py:59 | `git_dirty` forced False | KILLED |
| R13b | R13 | manifest.py:61 | `lock_file_sha256` forced None | KILLED |
| R14 | R14 | manifest.py:58 | clock time added to label (non-determinism) | KILLED |
| R15 | R15 | export.py:94 | `margin` sign flipped (away - home) | SURVIVED |
| R15b | R15 | export.py:27 | drop `total` from `PREDICTION_COLUMNS` | SURVIVED |
| R16 | R16 | export.py:92 | drop kickoff/game_id sort | KILLED |
| R16b | R16 | export.py:128 | `allow_nan=False` -> True in `to_json_text` | SURVIVED (equivalent: `_cell` already maps NaN to None) |
| R16c | R16 | export.py:121 | CSV writer without `lineterminator="\n"` | KILLED |
| R17 | R17 | report.py:133 | drop `n` from per-season model block | KILLED |
| R17b | R17 | report.py:288 | `_fmt(None)` -> "0" instead of "missing" | SURVIVED |
| R18 | R18 | report.py:332 | extra number in text not in JSON | KILLED |
| R18b | R18 | report.py:295 | float format `.4f` -> `.2f` | SURVIVED |

Per clause (primary mutation, first row of each clause): R1 S, R2 S, R3 S, R4 K, R5 K, R6 K, R7 K, R8 K, R9 K, R10 S, R11 S, R12 S, R13 K, R14 K, R15 S, R16 K, R17 K, R18 K. That is 12 killed, 6 survived of 18. Across all 32 mutations: 19 killed, 13 survived (one equivalent).

## Survivors: untested behaviour and minimal assertion

- R1 / R2 / R2b / R3 / R3b (clauses R1, R2, R3): the sample counts (ties, no-moneyline, finals) and the season list are only checked in the skipped real-file gate. Assert on the synthetic frame: `sample["ties_excluded"] == 1` and `sample["no_moneyline_excluded"] == 1` with one tie and one no-line game in the fixture; `bench_frames` on a frame with seasons 2012-2025 only (`report.BENCH_SEASONS == list(range(2012, 2026))`). D72: add a game at exactly `2026-10-15T00:00:00Z` (must raise) and one at `2026-10-14T23:59:59Z` (must pass), and `guard_scored(frame, [2026])` must raise even when no kickoff is late.
- R6b (R6): no game has a picked probability exactly at a band edge. Add a row with `p_blend == 0.6` and assert it lands in the 60-70% band, not 50-60%. (Note 0.5 itself is excluded by `>`; add `p_blend == 0.5`, which must count in 50-60%.)
- R9b (R9): `rates[kind]["pushes"]` is never asserted. Assert `pushes == v["games"] - n` on a stored fixture where the calibration table n is smaller than games.
- R10 (R10): only a CI that includes zero via the normal case is covered. Add a stored variant with `log_loss_gain_ci = [0.001, 0.02]` (excludes zero, lo > 0) and assert `gain_interval_includes_zero is False` and the text says "excludes zero"; and one with `[-0.02, -0.001]`.
- R11 (R11): `main` with a `--sim-dir` that lacks `confirm-result.json` is not tested for its reason. Assert `load_stored(str(tmp_path))[1] == "confirm-result.json not found in <dir>"` and that `report["simulator"]["reason"]` contains it.
- R12 / R12b (R12): the `--simulate` path (`_same`, `matches_stored_confirm`) is untested. Assert `_same(fresh, stored)` is True for equal dicts, False when one coverage value differs by 1e-3 (kills `any`), and that `simulate_confirm` (or `main` with a monkeypatched `simulate_confirm`) writes `matches_stored_confirm: False` when the fresh and stored values differ.
- R15 (R15): the `margin` and `total` values are not checked. Assert for one known game `row["margin"] == home_score - away_score` and `row["total"] == home_score + away_score`.
- R15b (R15): the column list is compared against `export.PREDICTION_COLUMNS` itself. Assert the literal header: `list(df.columns) == [...]` copied from the spec (or `"total" in header` and `len(header) == 54`).
- R16b: equivalent (NaN cannot reach `json.dumps`); the NaN rejection test would need to call `json.dumps` through `_rows` with a raw NaN, which `_cell` prevents. No test needed.
- R17b (R17): the word `missing` for a `None` value is asserted only for some shapes. Assert `render_text({"a": {"n": 3, "mae": None}})` contains `mae: missing` and does not contain `mae: 0`.
- R18b (R18): the text rounds floats to 4 places, so the "no number not in report" test passes with 2 places. Assert a known float, e.g. market log loss `0.6094`, appears in `report.txt` as `0.6094` (four places), and that every float in the JSON with 4+ places is findable in the text at 4 places.

## Spec note

EVALUATION.md R5 says 10 bins; `RELIABILITY_BINS = 20` in report.py:34 (the test `test_r5_..._has_ten_bins_...` passes, so it likely reads the 20-bin table of `metrics.calibration` in a different way, or checks a different value). Worth a glance.

## Re-run (after added tests)

17 tests appended to `backend/tests/test_report.py` (no source change): R1 season list, R2 tie / no-moneyline counts via `_sample`, R3 D72 boundary at `2026-10-15T00:00:00Z` vs one second earlier and season 2026, R6 band edge 0.5 / 0.6 / 0.7, R9 `pushes == games - n`, R10 stored intervals (positive, negative, spanning, lo == 0), R11 exact missing-file reason, R12 `_same` on a 1e-3 difference and `matches_stored_confirm` True / False through `main --simulate`, R15 margin / total values and a literal 42-column header, R17 `mae: missing`, R18 4-decimal floats (`0.6094`, `0.5910`, `0.6125`).

Suite: 48 passed, 1 skipped (real-file gate). Each of the 15 earlier survivors was re-applied alone and restored with `git checkout -- backend/nflpi`: all 15 KILLED (R1, R2, R2b, R3, R3b, R6b, R9b, R10, R11, R12, R12b, R15, R15b, R17b, R18b).

New totals: 31 of 32 mutations killed; 1 survivor, R16b, equivalent by design (`_cell` already maps NaN to None). Per clause: 18 of 18 primary mutations killed.
