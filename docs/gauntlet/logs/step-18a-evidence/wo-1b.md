# Work order 1b (step 18a): narrow correction after the code review

Builder: Claude Sonnet subagent, try 2 of 2 on this rung (narrow correction). Source: `ecc:code-reviewer` on `1f26f39`, verdict WARN, 4 MEDIUM, 6 LOW (full report: `reviews/code-reviewer-1.md`). Only the two files below change. Do not touch the `MUTATIONS` entries or any test.

## `docs/gauntlet/logs/step-18a-evidence/audit_numbers.py`
1. `no_moneyline_excluded`: count non-tied finished regular-season games where EITHER moneyline is missing (`home_ml` or `away_ml`). Then check the identity and stop with a clear `SystemExit` message if it fails: `preds_games == regular_season_finals - ties_excluded - no_moneyline_excluded`.
2. `share_with_both_qbs`: a name counts as present only if it is not null, not `""` and not `"NA"`.
3. `paired`: also pass week clusters, so each entry gains the cluster keys `paired_gain` already supports: `clusters = rows.groupby(["season", "week"], sort=True).ngroup().to_numpy()`.

## `docs/gauntlet/logs/step-18a-evidence/mutate.py`
4. Database guard: parse `DATABASE_URL` with `sqlalchemy.engine.make_url`; refuse (exit 2, clear message) unless the database name ends with `_test` AND the port is set and is not 5432.
5. Refuse to start (exit 2, clear message) if `git diff --quiet -- nflpi` is already non-zero, so a restore can never overwrite someone else's edit and the end check means what it says.
6. Count a test line starting with `FAILED` or with `ERROR` as failed, so a mutation that breaks collection is not reported as `SURVIVED`.

CONSTRAINTS: smallest diff; no new dependency (sqlalchemy is already one); ruff clean at 120; no other file changed; do not commit; never run the full suite; you may run `mutate.py` once to prove it (DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15442/nflpi_test, sandbox off for uv) but NOT `audit_numbers.py` in full (the coordinator runs it under a machine lock).

PROOF (the coordinator reruns): ruff clean; `mutate.py` exits 0 with nine KILLED; with `DATABASE_URL=postgresql+psycopg://x:y@localhost/nflpi_test` (no port) and with `...@127.0.0.1:15442/nflpi` (not a test database) it exits 2 before running anything.

RETURN: the diff summary, the proof you ran with results, any blocker.
