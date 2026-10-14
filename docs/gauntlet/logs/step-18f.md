# Step 18f — evaluation report, run records, exports (lane report)

Base `da6505b` (PR #32 merged). Spec `docs/model/EVALUATION.md` (R1-R18). One-shot, six checkpoints.

| CP | What | Evidence |
|---|---|---|
| 1 Plan | design: pure transforms over rebuilt bench + stored sim confirm; no DB, no route | `lane-report.md` state file |
| 2 Spec | R1-R18 | `ed3092d`, `1521a3b`, `ecc2671` |
| 3 Red tests | 32 tests, red at collection | `9a5c97c` |
| 4 Build | report.py, manifest.py, export.py (Sonnet implementer; Codex unavailable in sandbox) | `6300fa0`; real-file gate: 3,663 finals, 13 ties, 1 no moneyline, 3,649 games, market log loss 0.6094, blend 0.6107; two CLI runs byte-identical; `--simulate` matches the stored confirm |
| 5 Mutation sweep | 32 mutations over R1-R18; 19 killed, 13 survived (12 real + R16b equivalent); tests added, all real survivors then killed | `docs/gauntlet/logs/step-18f-evidence/mutations.md` |
| 6 Critic, lane-guard | round 1 FAIL on a454f10 (HIGH: simulator run records carried bench provenance), fixed in 1318117; round 2 fresh critic PASS on 1318117 (no CRITICAL/HIGH; advisories: n==0 bins in stored reliability, R12 default-distribution-only, private-helper reuse). Lane-guard OK vs origin/main. 62 passed, 1 skipped (real-file gate, passes with REPORT_GAMES_CSV) | |

Notes: reliability is ten 5-point bins of the picked side's chance (metrics.calibration). The bench frame reuses private `backtest._elo_frames`, `sim_backtest._variant`, `sim_backtest._read` (no duplication). Seam: none outstanding; `jobs.py` untouched. Live `predictions` export needs DB and a route (step 18h).
