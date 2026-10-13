# Step 18a: audit of the current model, the six-repository check, and the plan for the rest of step 18

Lane `audit`, branch `lane/audit`, base main `c55827f`, coord task #30, tier **T1** (documents and one test file; no model change). Coordinator Oscar (hive `worker-audit`, Opus), 2026-10-13, one Gauntlet Loop ONE_SHOT session. Owner brief: `docs/model/OWNER_BRIEF_2026-10-13.md` sections 1 and 2; owner decision D68.

**Result in three lines.** The model is not broken and is well calibrated, but it is the market's closing number in all but 2% of games, so it ties the market and cannot beat it as built (`docs/model/AUDIT.md`). Of the six repositories one is a possible later dependency, two give ideas, three are rejected; none shows a technique that beats the current model (`docs/model/REPOS.md`). The rest of step 18 is cut into seven lane-sized steps, 18d to 18j, with the rules for judging spread and totals forecasts written before any test (`docs/model/PLAN.md`).

Words: see the glossary at the top of `docs/model/AUDIT.md`.

## 1. PLANNING

* **Direction check.** Builds: three documents (audit, repository table, plan) and one test file that proves the audit's main claims. Replaces: nothing. Is not: a model change, a new screen, a new route, a migration or a dependency.
* **Step, base, scope.** Step 18a of step 18 (wave 1: 18a audit, 18b odds, 18c sim). Files owned: `docs/model/AUDIT.md`, `REPOS.md`, `PLAN.md`, `backend/tests/test_model_audit.py`, this log and `step-18a-evidence/**` (lane map, section "Lane audit"). Everything else is read only; the model and bench files belong to lane modelc (step 14c).
* **Prior decisions read.** D18 (ship rule), D60, D67, D68 (`docs/gauntlet/OWNER_DECISIONS_2026-10-12.md`); `CLAUDE.md` data-integrity and model-validation rules; step logs 14, 14b, 8b, 9, 13a, 4; hive memories of god, worker-modelc.
* **Assumptions (T1).**

| Assumption | State |
|---|---|
| The bench and the live path share `add_features` and `LogitModel` | validated (code read, then the parity test) |
| The step 14 numbers (3,649 games, market 0.6094, blend 0.6107) can be reproduced from today's nflverse file | validated (`audit-numbers.json`) |
| Past lines in the nflverse file are closing lines | assumed (the code and step logs say so; nflverse's own source and time were not checked: AUDIT A6) |
| For finished games nflverse's quarterback name is the man who started | unknown, and written as a HYPOTHESIS (AUDIT A8); it does not change this step's design |
| The live database may not be opened by this lane | validated (dispatch) |

* **Minimum change.** Three documents and one test file. Evidence scripts live in the evidence folder, not in the package.
* **Done by outcome.** Functional: the six audit tests pass twice and each planted defect makes one fail. User-facing: the owner can read in `AUDIT.md` why the model ties the market, and in `PLAN.md` what happens next. Operational: N/A (nothing runs in production from this step); the gate proves nothing existing moved.
* **Skills and tools.**

| Skill or tool | Use |
|---|---|
| `gauntlet-loop` | loaded first; ONE_SHOT, six checkpoints |
| `/jevgrep` | `jg 0.8.0` present. Not used: the dispatch named the two files to audit (`analytics/backtest.py`, `predictions/engine.py`) and the rest were reached by import; all seven model files were read whole. Recorded as not used, not as unavailable |
| `/graft` | not installed here (as step 13a found); `grep` for exact lookups |
| `/tdd` | no project `tdd` skill; the coordinator wrote the tests first (section 2) |
| `/ponytail` | in the work order: smallest code, no new dependency, no file outside the evidence folder |
| `harness-engineering` | N/A: no runner, evaluator or approval boundary is created |
| Design Gauntlet | N/A: no user interface |
| Headroom | `headroom doctor`: 1 failure, 5 warnings: not routed (expected in this app); no effect |
| Codex | refused once, default model: "The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account" (`~/.claude/plans/nfl-pickem-lanes/logs/step-18a-codex-probe.log`). Builder = one Claude Sonnet subagent |
| Model picks | fixed by the dispatch (readers Haiku or Sonnet, builder Sonnet, critic `ecc:mle-reviewer`); no Jev call was needed for them |

* **EFFORT.** PLANNING and SPECIFICATION high (the audit's claims are the product); IMPLEMENTATION low for the coordinator (builder and readers did the work); VERIFICATION high.

## 2. SPECIFICATION (frozen before the first run)

Public seam (from the dispatch): `analytics.backtest.predict_season` (bench) and `predictions.engine.refresh_predictions` / `backfill_season` / `train` (live).

| ID | Clause | Test in `backend/tests/test_model_audit.py` | Planted defect that must break it |
|---|---|---|---|
| S1 | Changing a game's own final score, and every later game's, changes neither its pregame features nor its probability, on the bench and on the live path | `test_bench_features_and_probability_ignore_the_games_own_and_later_scores`, `test_live_features_and_probability_ignore_the_games_own_and_later_scores` | M7 (bench), M1 (live) |
| S2 | For the same game and inputs the bench and the live path give the same features and the same probability | `test_bench_and_live_path_agree_on_features_and_probability` | M2, M6 |
| S3 | The walk-forward fit for season S uses no game from season S or later; the live model is fitted only on seasons before the one it predicts | `test_walk_forward_fit_for_a_season_uses_no_game_from_that_season_or_later`, `test_live_model_is_fitted_only_on_seasons_before_the_one_it_predicts` | M3, M4 (bench), M5 (live) |
| S4 | A live pick uses a line stored before kickoff; a rebuilt pick uses the closing line; the live weights are fitted on closing lines | `test_live_pick_uses_the_line_seen_before_kickoff_and_a_rebuilt_pick_the_closing_line` | M8 |

* **Document rules (from the dispatch, checked by the critic).** Every finding in `AUDIT.md` is VERIFIED (file and line, plus a test or a command with output) or HYPOTHESIS (names the test that would settle it). Every repository row carries the commit and the license as read from the clone. No 2026 game, line, injury or result is made up.
* **Red.** These tests assert properties the code is expected to have, so "red first" is not possible without a defect. Red was produced the honest way: eight planted defects (`step-18a-evidence/mutate.py`), each of which must make at least one test fail. Had a test failed on the unchanged code, it would have been kept as a strict `xfail` and reported to the integrator as `AUDIT CRITICAL` (none did).
* **S4 was added after the first run** (commit `cdbd66f`), when the line-timing finding (AUDIT A6) needed its own proof. It adds a clause; it changes none.
* **Gate.** `docs/gauntlet/logs/step-18a-evidence/gate.sh <label>`: full `pytest` on the lane's own database (`nflpi-lane-model-db`, port 15442; a skipped test fails the gate), `ruff` on `nflpi tests migrations` and the evidence scripts, `alembic upgrade head` then `alembic check` on a fresh scratch database, `npm run gen:api` with no drift. One full run on the final commit, the audit test file twice in a row, and the planted-defect sweep.
* **Baseline.** `tests/test_model.py` on `c55827f`: 34 passed (`~/.claude/plans/nfl-pickem-lanes/logs/step-18a-c55827f-baseline-test_model.log`).

## 3. IMPLEMENTATION

| Piece | Who | Result |
|---|---|---|
| Six repositories cloned shallow into the session scratch folder, outside the repository; never run | coordinator | six commits and licenses read from the clones (table in `REPOS.md`) |
| One reader per repository | 4 Sonnet + 2 Haiku subagents, read only, in parallel | reports in `step-18a-evidence/repos/`. The coordinator re-checked every commit and license and spot-checked the claims marked ✔ in `REPOS.md`. One reader claim was wrong (nfl-predictions does report log loss) and is corrected in the report and the table |
| `backend/tests/test_model_audit.py` (the spec) | coordinator | 5 tests green on the first run (`d407ad5`), 6 after S4 (`cdbd66f`) |
| Work order 1 (`step-18a-evidence/wo-1.md`): `audit_numbers.py`, `mutate.py` | Claude Sonnet builder (Codex refused), try 1 of 2 | delivered ruff-clean. The builder found that pytest's colour codes hid the `FAILED` lines and added `--color=no`. The coordinator read both files, then added three planted defects to the list (M7, M8 and nothing else: the list is spec data) |
| `blend_vs_market.py` (30 lines, one lookup) | coordinator | written directly: smaller than a work order, recorded here as the exception the roster allows |
| Bench numbers | coordinator, under `res:gate-c` | `audit-numbers.json`: 3,649 games, market 66.57% / 0.6094, blend 66.46% / 0.6107, equal to step 14's stored numbers |
| `AUDIT.md`, `REPOS.md`, `PLAN.md` | coordinator | commits `cdbd66f`, `1f26f39` |

**BUILD:** `IMPLEMENTATION_PROVIDER: CLAUDE (Codex refused the default model)`, `BUILD_RUNG: sonnet (try 1 of 2)`, `CLIMBS: none`.

**Review fan-out (T1, trivial tier: `ecc:code-reviewer` on the four new code files, read only).** REVIEW_VERDICT_PLACEHOLDER

## 4. CLEANUP

CLEANUP_PLACEHOLDER

## 5. VERIFICATION

VERIFICATION_PLACEHOLDER

## 6. LANDING

Not done by this lane, by rule: no push, no pull request, no merge. The integrator (god) lands it and is the final reviewer. LANDING_PLACEHOLDER

## Seams needed

None for this step. `docs/model/PLAN.md` section 2 lists the seams that steps 18f, 18h and 18i will ask for.

## For the owner, through the integrator

One open decision, `docs/model/PLAN.md` section 3.6: name the 2026 games from 2026-10-15 on as the untouched final period (my pick), or keep reusing 2022 to 2025. Two-way door. Until answered, D18 stands unchanged.
