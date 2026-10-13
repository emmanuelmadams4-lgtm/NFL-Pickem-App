# Step 13a: data timing (B8) — when the line, the quarterbacks and the injury rows were first seen and last changed

Lane `timing`, branch `lane/timing`, base `173f26b`, coord task #25, tier T1. Coordinator Stanley (hive `worker-timing`), 2026-10-13. Server only: no screen, no route, no reply-shape change.
Plan row: `docs/gauntlet/PLAN.md` row 13, part B8, and the architect note "live data timing and leakage (B8)". The rest of step 13 (S7 layers, S14 query shape, S12 label) is not in this lane.

## 1. PLANNING

* **Direction check.** Builds: a quiet log of when our ingestion first saw, and last saw change, each game's betting line, each club's projected starting quarterback and each injury report row, plus a report that says how old the line was at the last look before kickoff. Replaces: nothing (today the app cannot say how stale a pick's inputs were). Is not: a screen, an API field, or a model change.
* **Why now.** Week 6 kicks off Thursday 2026-10-15. The log has to be collecting before then or the week 6 report has nothing to read. Two-way door (a new append-only table).
* **What the existing tables already answer** (read from `service.py`, `models.py`):
  * **Line:** `upsert_games` appends a `market_snapshots` row only when the line (home/away moneyline, spread, total) differs from the newest row, with `observed_at` = the run time. So the first row's `observed_at` is first seen and the newest row's is last changed. **No new table.** (The `kind` flip latest to closing edits a row without moving its time; that happens after the final whistle, so it never touches pregame.)
  * **Injuries:** `ingest_injuries` inserts a row only when a player's `(report_status, practice_status)` changed, with `observed_at` = the run time. So min and max `observed_at` per player per week are first seen and last changed. **No new table.**
  * **Quarterbacks:** `games.home_qb` / `away_qb` are OVERWRITTEN by every `upsert_games` run (and `updated_at` moves every run whether or not anything changed). The history is lost today. **One new append-only table, `qb_observations`** (game, side, name or blank, observed_at), a row only when the name changes. Written inside `upsert_games`.
* **Assumptions.** `validated`: the three behaviours above (code read, plus the tests below). `validated`: the live database holds 6,771 games with no QB history, so the first run after deploy writes one row per side per game with the deploy time; for any game already kicked off that time is after kickoff and, by the no-hindsight rule, never counts as pregame. `assumed`: nflverse future starting QBs are projections (CLAUDE.md), so "QB seen" means "our feed named one", not "he started". Known ceiling: a line unchanged for days reads as old even though it is still current, because we log changes, not looks; a "last looked at" time would need a write per run per game and is not asked for.
* **Skills.** `/jevgrep` not used (small, exact lookups by grep; recorded). `/graft` not used (not installed here). `harness-engineering`: the new table is append-only, written only by ingestion, read only by the report. No Design Gauntlet (no UI). Security review not required (no route, no user input, no outside call). Migration: read by a new `ecc:database-reviewer` before the critic.
* **Prior decisions read.** `CLAUDE.md` data integrity rules (missing stays missing; insert-only history; ingestion failure keeps old data), lanes.md section "Lane timing".

## 2. SPECIFICATION (frozen)

Gate: `cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations && uv run alembic check`, `npm run gen:api` shows no drift, run twice on the final commit, plus a mutation pass (each clause broken once). Tests: `backend/tests/test_timing.py` (made-up rows, every ingestion time passed in).

Definitions. **First seen / last changed**, line: min / max `observed_at` of the game's `market_snapshots`. Quarterback: first seen = earliest observation with a name (None if never named), last changed = latest observation, a change to blank included. Injury: min / max `observed_at` per `(team, player_id or player)` for the game's season, week and two clubs. **Line age** = kickoff minus the `observed_at` of the newest snapshot strictly before kickoff, in hours. **Pregame** = `observed_at` strictly before `kickoff_utc`.

| ID | Clause | Test |
|---|---|---|
| T1 | An unchanged line on a new run does NOT move last changed | `test_unchanged_line_on_a_new_run_does_not_move_last_changed` |
| T2 | A changed line moves last changed; first seen never moves | `test_changed_line_moves_last_changed_and_never_first_seen` |
| T3 | An unchanged quarterback does not move last changed | `test_unchanged_quarterback_does_not_move_last_changed` |
| T4 | A changed quarterback moves last changed for that club only; first seen never moves | `test_changed_quarterback_moves_last_changed_and_never_first_seen` |
| T5 | A blank quarterback stays blank (never first seen); a name dropped back to blank is a change | `test_blank_quarterback_stays_blank_and_is_not_first_seen` |
| T6 | Injury rows: first seen never moves; last changed moves only on a real status change | `test_injury_rows_keep_first_seen_and_move_last_changed_only_on_a_change` |
| T7 | Line age is kickoff minus the last pregame snapshot | `test_line_age_is_kickoff_minus_the_last_pregame_snapshot` |
| T8 | A line first seen after kickoff is not a pregame line (age None) | `test_a_line_first_seen_after_kickoff_is_not_a_pregame_line` |
| T9 | A line change after kickoff does not shorten the pregame age | `test_a_line_change_after_kickoff_does_not_shorten_the_pregame_age` |
| T10 | A quarterback seen only after kickoff counts as blank pregame | `test_a_quarterback_seen_only_after_kickoff_counts_as_blank_pregame` |
| T11 | A quarterback change after kickoff does not replace the pregame one | `test_a_quarterback_change_after_kickoff_does_not_replace_the_pregame_one` |
| T12 | Missing stays missing: a game with no line has age None; the median skips it (never zero) and is None when nothing is known | `test_median_skips_games_without_a_line_and_is_none_when_all_are_missing` |
| T13 | The week report counts games with a blank quarterback side, blank sides, games with a line, and the median | `test_week_report_counts_blank_quarterbacks_and_the_median` |
| T14 | The migration list and schema parity: upgrade, check, downgrade, upgrade; `alembic check` clean | `test_hardening.py` migration test (list line) + gate `alembic check` |

* **Operational layer:** the log fills on every schedule ingestion with no new job; the report is `cd backend && uv run python -m nflpi.analytics.timing <season> <week>`. **User-facing layer:** N/A (no screen in this lane).
* **Week 6 report: PENDING** until week 6 is played (after Monday 2026-10-19). It is not faked in this log.
* Red: commit `0b71014`, `step-13a-evidence/red-1.log`.

## 3. IMPLEMENTATION

* **Provider.** `codex exec` tried once with the default model: refused, exact error `{"type":"invalid_request_error","message":"The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account."}` (400). So `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit)`, `BUILD_RUNG: sonnet (try 1 of 2)`, `CLIMBS: none`. One bounded work order (models, migration 0007, `ingestion/timing.py`, `service.py` hook and `now` parameter, `analytics/timing.py`) built by a Sonnet subagent; the coordinator wrote the spec and the tests first, inspected the whole diff and reran the proof itself. Work orders Claude built: the one.
* **Commits.** `0b71014` tests (red), `57f0e2d` feature. First green: `tests/test_timing.py` 13 passed, `ruff` clean (the builder reported one E501 in the frozen test docstring; fixed by the coordinator, it is the lane's own file).
* **Where the log is written.** `upsert_games` calls `timing.record_qbs` once per run (same transaction); the line and injury logs are the existing append-only tables, untouched. `ingest_injuries` gained an optional `now` (time injection for tests, same style as `ingest_weather`).
* **Review.** `ecc:database-reviewer` on the migration, model and `record_qbs`: PASS, no blockers. Advisories (all carried, none mapped to a clause): (1) FK has no ON DELETE, same as every other table, games are never deleted; (2) `record_qbs` reads every newest row each run (~13.5k small rows, fine today; `DISTINCT ON` if it grows); (3) a duplicate `game_id` in one batch would insert twice (feed keys are unique); (4) blank or NaN names: `parse_games` maps blank to None, so not reachable. Security review: not required (no route, input or outside call).
* **Live-database safety.** The migration only creates a new table and one index; `games` is not altered, no existing row is rewritten, the foreign key onto an empty table validates nothing. First run after deploy writes about 2 rows per game (~13.5k) stamped with the deploy time; for games already kicked off that is after kickoff and never counts as pregame (clauses T8 to T11).

## 4. CLEANUP

* Scope-locked `/refactor` pass on the touched code. One simplification: dropped `obs.qb or None` in `week_report` (commit `a706007`), an unreachable guard that the mutation pass found no test could distinguish (`parse_games` already returns None for a blank name). Left alone with reason: the two-item `SIDES` tuple exists in both new modules (one line each, importing across the ingestion/analytics layers would add a dependency for no gain). Re-ran `tests/test_timing.py` and the full gate after the edit.

## 5. Evidence (all on `a706007` unless noted)

| Check | Result | Log |
|---|---|---|
| Mutation pass: each frozen rule broken once (12 breaks: T1, T2, T3, T4/T5, T5, T6, T7, T8/T9, T10/T11, T12, T13) | 11 caught; 1 survivor (`obs.qb or None`) was the unreachable guard, now deleted | `step-13a-evidence/mutation.log` |
| Gate run 1: `pytest -q` | 1203 passed in 315 s | `step-13a-evidence/gate-1.log` |
| Gate run 1: `ruff check nflpi tests migrations` | All checks passed | same |
| Gate run 1: alembic upgrade, `check`, downgrade to 0006, upgrade | exit 0, "No new upgrade operations detected" | same |
| Gate run 2 (same commit, separate hold of the slot) | 1203 passed in 199 s; ruff clean; alembic check clean | `step-13a-evidence/gate-2.log` |
| `npm run gen:api` | exit 0, `git status packages` empty: no API drift | `step-13a-evidence/gate-2.log` |

Test database: container `nflpi-lane-scores-db` on 127.0.0.1:15446 (never the default URL). Slot: `res:gate-c` per god's ruling of 14:19Z (`res:gate-b` was held by another lane from 09:50 to past 10:10 local).

## 6. VERIFICATION

* **Fresh critic** (`ecc:code-reviewer`, no build transcript, `1ff61c3` before the rebase): **PASS**. Every clause T1 to T13 has a test that exercises it (none vacuous); T14 is the migration list line plus `alembic check`; step log has all sections and the evidence files exist. Its own gate rerun on that HEAD: 1203 passed, ruff clean, alembic upgrade and check clean. Blockers: none. Advisories carried (not clauses): duplicate `game_id` inside one batch would insert twice (feed keys are unique); `record_qbs` reads every newest row per run (~13.5k, `DISTINCT ON` if it grows); first run after deploy stamps about 2 rows per game with the deploy time, so for games already played `first_seen` shows the deploy time (they never count as pregame).
* **Jev** (`passed`): 0.78, inside the grey zone (0.1 to 0.8), so the advisor decided: `ADVISOR: sonnet "did the review truly pass" -> PASS` (gate pair green, critic PASS, no clause lacks a test; it did not rerun anything).
* **Rebase.** Main moved from `173f26b` to `7c8a3d0` (lane web step 8a2 landed; its changes to `service.py` and `test_hardening.py` did not conflict). Rebased cleanly onto `7c8a3d0` under `res:git-integrate`; new HEAD `f03694d` (same five commits). Gate after the rebase: `gate-3.log` 1222 passed, ruff clean, alembic upgrade and check clean, `gen:api` no drift; `gate-4.log` is the second consecutive run on that commit.
* **Lane guard** (`lane-guard.py check lanes.md timing 173f26b`) lists exactly the three granted seam files and nothing else: `migrations/versions/0007_qb_observations.py` (the one migration), `nflpi/models.py` (append-only class at the end), `tests/test_hardening.py` (the one migration-list line). No file under `apps/web`, `api/`, `jobs.py`, `config.py`, `ai/` or `packages/shared` was touched.
* **Week 6 report: PENDING.** Run after week 6 is played (after Monday 2026-10-19): `cd backend && uv run python -m nflpi.analytics.timing 2026 6`. Not faked here. Until then, `week_report` on the real fixtures reports no pregame line and blank quarterbacks for any game ingested after its kickoff, by design (no hindsight).
* **Landing note for god.** Migration `0007` (down revision `0006`): renumber if another lane lands first. The first schedule ingestion after deploy writes about 13.5k `qb_observations` rows. The log only starts collecting on that deploy, so deploy before Thursday 2026-10-15 kickoff for week 6 to have pregame rows.
