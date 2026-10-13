# Review 1: ecc:code-reviewer on 1f26f39 (read only, nothing run)

**Verdict: WARN.** No test was found that passes with its clause broken. The guard in `mutate.py` can still run the suite against the wrong database, and a few numbers in `audit_numbers.py` are slightly off.

I did not run anything. Every claim below comes from reading the code.

**1. Tests that could pass while broken, and mutations**

I found no vacuous test.

- **S1 (bench and live):** both tests have real controls. The bench test asserts that the target's `home_win` flipped and that later `elo_diff` moved. The live test asserts that an earlier result moves `elo_diff`.
- **S3 and S2:** the spies, the `tuned == [sorted(allowed)]` check, and the black-box rewrite are sound. The 6e-5 tolerance only covers 4-decimal rounding. M1 shifts a feature by about 0.02, far above it.
- **M1:** this mutation is overwritten on the bench path, because `_elo_frames` recomputes `elo_diff` at `backtest.py:58`. Only the live test can kill it, and M7 covers the bench.
- **M4:** it is killed only because flipping every test-season score moves the home rate away from 0.5. That holds for the 15-game odd fixture.

LOW `test_model_audit.py:158-161` — The S4 weights clause checks that the stored `market_kind` of the training-season frame is all "closing". It does not check that `engine.train` fits on that frame. It also never checks that the `latest` line's `market_observed_at` is before kickoff. Only the label and `Prediction.created_at` are checked. Fix: assert `market_observed_at < kickoff` on live rows.

LOW `mutate.py:14` — No mutation targets the live fit window in `engine.train` (`through_season + 1`) or the closing-line source for weights. Add M9 on `engine.py:103`.

**2. `audit_numbers.py` statistics**

Decile reliability, ECE, Wilson interval use, `PAIRS` and the `season_2026` counts are correct as written.

MEDIUM `audit_numbers.py:93-96` — `no_moneyline_excluded` counts games where `home_ml` is NaN. `market_prob` is NaN when either moneyline is missing (`features.py:~126`). A game with only one moneyline is dropped from `preds` but not counted here, so `preds_games = regular_season_finals − ties − no_moneyline` can be wrong. Fix: use `home_ml.isna() | away_ml.isna()` and assert the identity.

MEDIUM `audit_numbers.py:98` — `share_with_both_qbs` uses `.notna()`, but `parse_games` sets `home_qb` to `r["home_qb_name"] or None` (`nflverse.py:168`). A literal "NA" string would count as present and overstate the share. I did not check whether `fetch_csv` turns "NA" into empty. Fix: test with `isin(["", "NA"])` as `season_2026` does.

LOW `audit_numbers.py:43` — The calibration slope comes from `LogitModel.fit`, which is L2-regularized (`C=1.0`). The slope is shrunk slightly, under about 1% at these sample sizes. Fix: say so in the doc, or fit unpenalized.

LOW `audit_numbers.py:106` — `paired_gain` is called without `clusters`. The intervals and `ships` treat games as independent, though `paired_gain` supports week or season clusters. Don't cite `ships` as the project's bar without noting that.

`blend_vs_market.py` is consistent with `engine.train`: window 10 and seasons 2016–2025 match `through_season − window + 1 … through_season`. No finding.

**3. `mutate.py` safety**

MEDIUM `mutate.py:79-81` — The database guard rejects only the substring ":5432". A URL with no port (which defaults to 5432), or a non-test database on another port, passes. The suite runs `drop_all` and `truncate` on whatever `DATABASE_URL` points at. Fix: parse it with `make_url` and require `database.endswith("_test")`.

MEDIUM `mutate.py:64-74` — Restoring from a pre-mutation byte snapshot overwrites any edit another process makes to the same file in that window. That is exactly the situation you described for `backend/nflpi`. The `finally` also does not survive SIGKILL. Fix: refuse to run if `git diff --quiet -- nflpi` is non-zero at start, or copy the tree to a scratch directory and mutate the copy.

LOW `mutate.py:91` — `files_left_changed` flags any pre-existing dirty state as a failure. It also misses untracked files. Fix: compare `git diff -- nflpi` before and after the run.

LOW `mutate.py:60,75` — Only lines starting with `FAILED` are counted. A mutation that causes a collection `ERROR` is reported SURVIVED even though pytest exits non-zero. That errs in the safe direction, but it is misleading.

Relative paths assume the current directory is `backend/`. A wrong directory raises `FileNotFoundError` before any write, so nothing is left changed.

**4. Plain bugs:** none found.

Files reviewed (read via `git show 1f26f39:<path>` from `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-audit`):
- `backend/tests/test_model_audit.py`
- `docs/gauntlet/logs/step-18a-evidence/audit_numbers.py`
- `docs/gauntlet/logs/step-18a-evidence/mutate.py`
- `docs/gauntlet/logs/step-18a-evidence/blend_vs_market.py`

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 |
| LOW | 6 |
