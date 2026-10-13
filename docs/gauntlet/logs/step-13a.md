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
