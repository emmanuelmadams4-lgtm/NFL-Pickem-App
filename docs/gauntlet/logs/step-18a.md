# Step 18a: audit of the current model, the six-repository check, and the plan for the rest of step 18

Lane `audit`, branch `lane/audit`, started from main `c55827f`, moved onto main three times as other lanes landed (`11cc401`, `589aa3b`, then `b4d42d0`); commit names below are as of the branch on `b4d42d0`, except `d2a6f7b` and `639f430`, which name the commits the critics and the gate actually ran on, coord task #30, tier **T1** (documents and one test file; no model change). Coordinator Oscar (hive `worker-audit`, Opus), 2026-10-13, one Gauntlet Loop ONE_SHOT session. Owner brief: `docs/model/OWNER_BRIEF_2026-10-13.md` sections 1 and 2; owner decision D68.

**Result in three lines.** The model is not broken and is well calibrated, but it is the market's closing number in all but 2% of games, and it ties the market: nothing measured shows it beating the market (`docs/model/AUDIT.md`). Of the six repositories one is a possible later dependency, two give ideas, three are rejected; none shows a technique that beats the current model (`docs/model/REPOS.md`). The rest of step 18 is cut into seven lane-sized steps, 18d to 18j, with the rules for judging spread and totals forecasts written before any test (`docs/model/PLAN.md`).

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
| S1 | Changing a game's own final score, and every later game's, changes neither its pregame features nor its probability, on the bench and on the live path | `test_bench_features_and_probability_ignore_the_games_own_and_later_scores`, `test_live_features_and_probability_ignore_the_games_own_and_later_scores` | M7 (bench), M1 (live), M10 (total points, both) |
| S2 | For the same game and inputs the bench and the live path give the same features and the same probability | `test_bench_and_live_path_agree_on_features_and_probability` | M2, M6 |
| S3 | The walk-forward fit for season S uses no game from season S or later; the live model is fitted only on seasons before the one it predicts | `test_walk_forward_fit_for_a_season_uses_no_game_from_that_season_or_later`, `test_live_model_is_fitted_only_on_seasons_before_the_one_it_predicts` | M3, M4 (bench), M5 (live) |
| S4 | A live pick uses a line stored before kickoff; a rebuilt pick uses the closing line; the live weights are fitted on closing lines | `test_live_pick_uses_the_line_seen_before_kickoff_and_a_rebuilt_pick_the_closing_line` | M8 |

* **Document rules (from the dispatch, checked by the critic).** Every finding in `AUDIT.md` is VERIFIED (file and line, plus a test or a command with output) or HYPOTHESIS (names the test that would settle it). Every repository row carries the commit and the license as read from the clone. No 2026 game, line, injury or result is made up.
* **Red.** These tests assert properties the code is expected to have, so "red first" is not possible without a defect. Red was produced the honest way: planted defects (ten by the end: M1 to M10) (`step-18a-evidence/mutate.py`), each of which must make at least one test fail. Had a test failed on the unchanged code, it would have been kept as a strict `xfail` and reported to the integrator as `AUDIT CRITICAL` (none did).
* **S4 was added after the first run** (commit `3ddcff3`), when the line-timing finding (AUDIT A6) needed its own proof. It adds a clause; it changes none.
* **Gate.** `docs/gauntlet/logs/step-18a-evidence/gate.sh <label>`: full `pytest` on the lane's own database (`nflpi-lane-model-db`, port 15442; a skipped test fails the gate), `ruff` on `nflpi tests migrations` and the evidence scripts, `alembic upgrade head` then `alembic check` on a fresh scratch database, `npm run gen:api` with no drift. One full run on the final commit, the audit test file twice in a row, and the planted-defect sweep.
* **Baseline.** `tests/test_model.py` on `c55827f`: 34 passed (`~/.claude/plans/nfl-pickem-lanes/logs/step-18a-c55827f-baseline-test_model.log`).

## 3. IMPLEMENTATION

| Piece | Who | Result |
|---|---|---|
| Six repositories cloned shallow into the session scratch folder, outside the repository; never run | coordinator | six commits and licenses read from the clones (table in `REPOS.md`) |
| One reader per repository | 4 Sonnet + 2 Haiku subagents, read only, in parallel | reports in `step-18a-evidence/repos/`. The coordinator re-checked every commit and license and spot-checked the claims marked ✔ in `REPOS.md`. One reader claim was wrong (nfl-predictions does report log loss) and is corrected in the report and the table |
| `backend/tests/test_model_audit.py` (the spec) | coordinator | 5 tests green on the first run (`a3d57f1`), 6 after S4 (`3ddcff3`) |
| Work order 1 (`step-18a-evidence/wo-1.md`): `audit_numbers.py`, `mutate.py` | Claude Sonnet builder (Codex refused), try 1 of 2 | delivered ruff-clean. The builder found that pytest's colour codes hid the `FAILED` lines and added `--color=no`. The coordinator read both files, then added three planted defects to the list himself (M7, M8, M9: the list is spec data, not code) |
| `blend_vs_market.py` (30 lines, one lookup) | coordinator | written directly: smaller than a work order, recorded here as the exception the roster allows |
| Bench numbers | coordinator, under `res:gate-c` | `audit-numbers.json`: 3,649 games, market 66.57% / 0.6094, blend 66.46% / 0.6107, equal to step 14's stored numbers |
| `AUDIT.md`, `REPOS.md`, `PLAN.md` | coordinator | commits `3ddcff3`, `97bc97f` |

**BUILD:** `IMPLEMENTATION_PROVIDER: CLAUDE (Codex refused the default model)`, `BUILD_RUNG: sonnet (try 1 of 2)`, `CLIMBS: none`.

**Review fan-out (T1, trivial tier: `ecc:code-reviewer` on the four new code files, read only).** Verdict **WARN** on `97bc97f`: no test found that passes with its clause broken; 0 critical, 0 high, 4 medium, 6 low (`step-18a-evidence/reviews/code-reviewer-1.md`). Each finding and what was done:

| Finding | Done |
|---|---|
| MEDIUM `audit_numbers.py`: the "no moneyline" count looked at the home price only | fixed in work order 1b (either price missing), and the script now stops unless games = finals - ties - no line. The numbers did not change (3,649 = 3,663 - 13 - 1) |
| MEDIUM `audit_numbers.py`: a quarterback name of "NA" would count as present | fixed in 1b. Checked the file too: in 6,499 games of 2002 to 2025 no name is blank or "NA", and a missing 2026 name is blank, never "NA" (`feeds-extra.txt`), so the app does not read a missing name as a quarterback |
| MEDIUM `mutate.py`: the database guard only refused the text ":5432" | fixed in 1b: the database name must end in `_test` and the port must be set and not 5432 |
| MEDIUM `mutate.py`: a restore could overwrite someone else's edit | fixed in 1b: it refuses to start when `git diff -- nflpi` is not clean |
| LOW S4 checked the label, not the line's own time | fixed by the coordinator (the test is the spec): a live row's line must have been seen before kickoff |
| LOW no planted defect for the live fit window | M9 added; caught |
| LOW paired intervals treat games as independent | 1b adds the week-clustered intervals; `AUDIT.md` A9 quotes both |
| LOW calibration slope uses a regularized fit | noted in `AUDIT.md` A4 (effect under 0.01) |
| LOW `mutate.py` counted only `FAILED` lines; end check flagged an already dirty tree | fixed in 1b (`ERROR` lines count; refuses a dirty tree at start) |

Work order 1b (`wo-1b.md`): Claude Sonnet builder, try 2 of 2 on the rung, six changes in the two scripts, commit `178b389`. The coordinator read the diff and reran every proof (section 5). One lapse, stated plainly: both builders' own proof runs of `mutate.py` (about 90 seconds each) ran without a machine lock, because the work orders allowed one run and did not name the lock; every coordinator run held one.

## 4. CLEANUP

Scope: the four code files this step added (`backend/tests/test_model_audit.py` and the three scripts in the evidence folder). An explicit `/refactor` read after the review fixes, on `178b389`:

* **No change needed.** `test_model_audit.py` repeats two five-line helpers that also exist in `tests/test_model.py` (`frame`, `_flip_scores`). Kept on purpose: that file belongs to lane modelc and may change under this one; importing from it would tie the audit's proof to another lane's test file.
* **No change needed.** `audit_numbers.py` and `blend_vs_market.py` both build the bench frame the way `jobs.backtest` does (seven lines each). Kept: each script must run alone as evidence, and a shared helper would be a third file for seven lines.
* **No change needed.** `mutate.py`: one dictionary of defects and one loop.
* Remaining review items: none open; all ten are answered in section 3.

No file changed in this pass, so no proof was rerun for it.

## 5. VERIFICATION

All on the lane's own database (`nflpi-lane-model-db`, port 15442). Raw logs are outside the repository in `~/.claude/plans/nfl-pickem-lanes/logs/` (file names below).

| Check | Result | Log |
|---|---|---|
| Audit test file, twice in a row, on the final test code | 6 passed, 6 passed | `step-18a-final-audit-run1.log`, `-run2.log` |
| Planted-defect sweep, coordinator's run under `res:gate-b` | **10 of 10 KILLED**, no file left changed | `step-18a-evidence/mutation.log` |
| **Full gate, one run on `639f430` (named `dc5bd7b` since the last branch move)** under `res:gate-b` | **PASS**: `pytest` 1,462 passed in 614 s, 0 failed, 0 skipped; `ruff` all checks passed; `alembic upgrade head` then `check` on a fresh scratch database: no new upgrade operations; `npm run gen:api`: no drift | `step-18a-final2.out`, `step-18a-final2-*.log` |
| Bench numbers reproduce the stored ones | 3,649 games, market 0.6094, blend 0.6107 (equal to step 14) | `step-18a-evidence/audit-numbers.json` |
| **Full gate again after the last branch move** (main went from `589aa3b` to `b4d42d0`: the Group screen landed) | Not finished by the lane: the Mac ran out of memory while four full gate runs ran at once and the worker was torn down; the integrator stopped the run. The gate on the current main is the CI of pull request #27 (backend, web, e2e, docker: all pass, twice) and the CI on main after the merge (`1078dbb`: success) | `step-18a-final3.out`, `step-18a-final3-*.log` |
| Lane guard | `OK` | `python3 ~/.claude/bin/lane-guard.py check …/lanes.md audit main` |

An earlier full-gate run on the previous candidate was stopped by the coordinator after 15 minutes without a result, because the test file was about to change and the run was holding a machine lock others were waiting for; it proves nothing and is not counted.

**Critics (each new, no build transcript, `ecc:mle-reviewer`).**

| Round | Commit | Verdict | What it did |
|---|---|---|---|
| 1 | `d2a6f7b` (same content as `1f94f1b`) | **FAIL on one rule** | Re-derived six VERIFIED findings (A9, A10, A4, A6, A8, A2/A3, plus A13/A14 arithmetic): all confirmed. All six repository rows match the clones (commit, date, license). Test file: 6 passed. Every clause S1 to S4 has a test and a killed defect. The failure: two HYPOTHESIS claims (A6, A8) were worded as fact in the summary's point 4 and in the "Realistic cutoffs" paragraph, and A8's "little" was an inference. Report: `step-18a-evidence/reviews/critic-1.md` |
| fix, once | `b79f81c` | | The three places reworded; every document searched for the same fault. Its advisory was also taken: the score rewrite in the S1 tests now changes the total as well as the winner, and planted defect M10 (total points in a feature) proves it on both paths |
| 2 (delta brief) | `639f430` | **PASS** | Read all of `AUDIT.md` again for the failed rule, checked A9 and A10's numbers in the evidence files, the test change, all ten killed defects, the citations after the branch move, and one repository claim the first critic could not confirm. Test file: 6 passed. Report: `step-18a-evidence/reviews/critic-2.md` |

**After critic 2, documents only.** Its three advisory notes were taken by softening three sentences in `AUDIT.md` (A4: the size of the regularization effect is no longer claimed; the 2022 to 2025 gap is no longer called chance; A10: "should change"). No code or test changed after the gate: `git diff --stat 639f430 HEAD` lists only `docs/`.

**Jev (did the review truly pass?).** `JEV: passed -> 0.82`. With a green gate and the critic's PASS, that meets the bar (0.8).

**Counts.** Critic rounds: 2 (one FAIL, fixed once, one PASS). Builder tries: 2 on the Sonnet rung (work orders 1 and 1b). Strikes: none. Continuations: 0.

## 6. LANDING

Not done by this lane, by rule: no push, no pull request, no merge. The integrator (god) lands it and is the final reviewer. State handed to the integrator: branch `lane/audit` on main `589aa3b`, gate green on `639f430`, critic PASS on `639f430`, later commits documents only. Not pushed, no pull request, nothing deployed, live app untouched.

What is done: the audit, the repository table, the plan, six tests, ten planted defects all caught. What is blocked or left: nothing in this step. Two findings can only be settled by the 2026 live log (AUDIT A6, A8), and one decision is the owner's (below).

## Seams needed

None for this step. `docs/model/PLAN.md` section 2 lists the seams that steps 18f, 18h and 18i will ask for.

## For the owner, through the integrator

One open decision, `docs/model/PLAN.md` section 3.6: name the 2026 games from 2026-10-15 on as the untouched final period (my pick), or keep reusing 2022 to 2025. Two-way door. Until answered, D18 stands unchanged.
