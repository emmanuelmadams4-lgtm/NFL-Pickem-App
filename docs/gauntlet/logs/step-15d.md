# Step 15d (server side): the live worker and GET /api/live (no screen)

Session: owner's Mac, 2026-10-13 (US Eastern night), lane `livewire` (worktree `.claude/worktrees/lane-livewire`, branch `lane/livewire`, base `main@e51ac48`, which had not moved at the last check). Coordinator: Claude Sonnet 5.5 (hive temp "Darryl", `worker-livewire`). Tier T2. Coord task #19, claim `claims/livewire`, state file `~/.claude/plans/nfl-pickem-lanes/lane-livewire.md`.
Evidence: `docs/gauntlet/logs/step-15d-evidence/` (design.md, gate.sh, `final1-*`, `final2-*` gate logs, lane-guard.txt, reviews/).
Rows covered: `odds-live-plan.md` rows 15d (server half) and 15g wiring; step-15a carried items S4, I8, L3 (worker half), and "staleness = `last_confirmed`". NOT in this step: any screen, the market-consensus feature (15e), in-game grading (15f), merging the two fetch guards.

KNOWN LIMIT (read first): no NFL game is in progress until Thursday 2026-10-15 (SEA @ DEN, 8:15 PM ET). The in-progress path is proved with the 15a recorded replies edited to look live, plus a fake clock. **"Checked against a real live game": PENDING, 2026-10-15** (then Sunday 2026-10-18). Not seen live: whether ESPN's win probability can lag or vanish, whether Kalshi stays priced in play, how long a real summary fetch takes.

## 1. PLANNING
* **In the owner's words (D55):** "can we also add realtime scores please for each game until the game ends if the game is going on". D59: yes to ESPN, Kalshi and the Odds API (Kalshi's agreement read: "Kalshi is fine"; Odds key supplied).
* **Builds / replaces / is not:** builds the server half that makes 15a's live data reach the app: a worker thread that polls while a game is on, and one read route the web will poll. Replaces nothing. Not visible to the owner yet (no screen).
* **Pre-flight:** Problem: the app stores live state but nothing fetches it or serves it. Why now: week 6 starts Thursday. Scope: worker thread + one route; cut: screen, model use, grading. Success signal: on Thursday 2026-10-15 `/api/live` shows SEA @ DEN's score and ESPN probability within about 40 s of ESPN's page, and `stale` is false while it is on. Reversibility: two-way (no migration; remove two lines in `main.py` and `jobs.py`).
* **Assumptions:** validated: the 15a adapters, back-off and reservation logic (read and reviewed); assumed: real in-play behaviour (see KNOWN LIMIT); validated: Odds API costs 1 credit per call (header 500 -> 499 in 15a).
* **Skills:** `/jevgrep`: not used (`JEVGREP: not-checked`; the files were named in the dispatch and read directly). `/graft`: N/A, same reason. `/tdd`: tests written first (red: `ImportError: cannot import name 'live_worker'` and `'live'`). `/ponytail`: stated in every work order. `harness-engineering`: the worker is a long-lived runner: locked = adapters and their reservations (15a), editable = `live_worker.py`, `api/live.py`, durable log = `ingestion_runs` + `source_status`, recovery = sweep of stale `running` rows, human-controlled = none (owner's yes recorded as D59). Design Gauntlet: N/A (no UI).
* **EFFORT:** PLANNING/SPECIFICATION high; IMPLEMENTATION low (builders); CLEANUP low; VERIFICATION high.

## 2. SPECIFICATION
Frozen in `step-15d-evidence/design.md` (clauses W1-W9 worker, A1-A8 route, amended by Dwight's review). Public seam: `nflpi.live_worker` (`live_step`, `in_window`, `with_deadline`, `sweep_stale_runs`, `run_forever`, `start`, `Schedule`, constants), `nflpi.api.live.router` (`GET /api/live`). Frozen numbers: wake 5 s; ESPN every wake while a game is in play (adapter spaces real fetches 30 s); Kalshi inside a 2 h lead window every 120 s; Odds inside a 24 h lead window every 6 h; run deadline 45 s; stale `running` rows after 10 min; a game is in play for 8 h after kickoff unless final.
Tests (68): `backend/tests/test_live_worker.py` (33) and `backend/tests/test_live_api.py` (35), committed red first (`1b6244d`). Red reason: the two modules did not exist.
* **Odds budget proof (W5):** a 31-day simulation with a game every day (steps of 30 min): 100 to 124 Odds calls, fake credit header never below 376; a header of 49 stops all calls for 35 days (2 calls in 40 days); a restarted worker (new `Schedule`) makes no second call inside 6 h (Dwight H1).
* **Killed run (I8, W7), decided by test:** the `ingestion_runs` row stays `running` (evidence), the source stays reserved (a restart does not refetch), no `live_states` row exists; the next start sweeps `running` rows of the three live (source, dataset) pairs older than 10 min to `failed`/`interrupted`, and nothing else.
* **Dwight design review (before code): PASS to build, H1-H5** (all folded in, listed at the bottom of design.md); H6 (owner's yes) is D59.
* JEV: `model:livewire:wo1 -> sol (0.88), effort unsure (0.63)`; `wo2 -> sol (0.56), effort medium (0.79)` (route `advisor`; the pick was the only workable one: luna 0.07/0.29, astra needs the owner). Coordinator took high for WO-1 (budget and logs) and medium for WO-2.

## 3. IMPLEMENTATION
| Work order | Builder | Commit | Proof |
|---|---|---|---|
| WO-2 `api/live.py` + 2 lines in `main.py` | Codex gpt-6-sol medium, try 1 | `cbab559` | 29 of 31 green; the 2 reds were my tests (an `app.routes` path check that does not fit FastAPI's include, a test missing the `session` fixture) |
| WO-1 `live_worker.py` + 2 lines in `jobs.py` | **Codex ran out of workspace credits** ("Your workspace is out of credits") right after WO-2; built by an **Opus** subagent from the same work order (rung sol -> opus). The integrator's later message asked for Sonnet, not Opus, for builds: noted, that work order was already done | `4755227` | 31 of 32 green; the red was my test (a game window closed exactly at the time the test asserted) |
| Review round 1 fixes (below) | coordinator (Sonnet rung; three one-line edits, red tests first) | `a912883`, `e0da90e` | 33 + 35 green |
* **Built by Claude and why:** WO-1 (Codex credits exhausted, first seen after WO-2); the review-fix edits (three one-line changes each preceded by a red test) and the cleanup split were written by the coordinator on the Sonnet rung. CLIMBS: `gpt-6-sol -> opus: Codex limit hit (rule 5)`. STRIKES: none.
* **Defect Codex introduced:** the route's candidate floor used `max(...)` where the work order said `min(...)`: games past midnight Eastern and early finals vanished. Found by two reviewers and Dwight, not by my tests (a gap: no test used a time past midnight). Fixed with two new red tests.
* Review fan-out (standard tier) on `5e70a10`: `ecc:code-reviewer` (5 findings) and `ecc:silent-failure-hunter` (7), reports in `step-15d-evidence/reviews/`. Dwight (security, with his two ecc agents): PASS on security, K1 breaks A3.

| Finding | Result |
|---|---|
| K1 / code-review #1,#2 / hunter #1: candidate floor `max` (route drops in-play games past midnight ET and early finals) | FIXED (`a912883`), 2 tests |
| code-review #5, Dwight K4: worker window 5 h, route shows `in` for 8 h | FIXED: worker window 8 h |
| hunter #3, Dwight K2 (partly): a `post` row with no final probability is never retried | FIXED: stays in the window until the summary is stored, test |
| Dwight K3: `stale` raises a false alarm all evening after the last game | FIXED (`e0da90e`): stale only when a returned game is `in` or `lost`; 3 tests |
| hunter #2 (HIGH): a deadline-cut or failed summary stores `home_win_prob` null and the next poll fixes it | CARRIED by decision (Dwight H2 accepted): missing stays missing; null means "no probability right now"; the web may hold its last value for a short time |
| hunter #4, Dwight K6: worker logs by class name every 5 s on a repeating fault; skipped/failed results not logged | CARRIED (log rate limit) |
| hunter #5: `rollback` inside the failure handler can itself raise; #6 no thread supervision (Dwight LOW) | CARRIED: the next wake recovers; `stale` is the signal; "live worker started" is logged |
| code-review #3: sources run one after another; a slow quote source delays the next ESPN poll (worst case about 85 s + 30 s) | CARRIED: needs hung quote sources; `stale` shows it |
| code-review #4: step time is the step's start | CARRIED (the adapters' reservations keep the floors) |
| hunter #7, Dwight K5: a flat Kalshi price older than 15 min is null | CARRIED by Dwight's own H5 condition; stated in the route contract |

## 4. CLEANUP
`/refactor` pass scope-locked to files this lane wrote: `api/live.py`'s `live()` (62 lines) split into `_visible` and `_kalshi_prices` (no behaviour change, 33 tests rerun green, OpenAPI unchanged); `ruff format` run on the four own files only (lesson from 15a). **No change needed, with reasons:** `live_worker.py` (162 lines, one job; `in_window` is public only for tests and the sweep decision); test helpers `Net`/`Clock` kept (used by many tests).

## 5. VERIFICATION
* **Gate x2 (coordinator, under `res:gate`), HEAD code `e0da90e`, on main `e51ac48`:** `final1-*`: pytest **1014 passed** (2:08), ruff All checks passed, alembic up/check "No new upgrade operations detected", genapi "no drift", keyscan "key text found in no file". `final2-*`: pytest **1014 passed** (1:57), same four PASS. (Baseline: I did not run the suite on `main@e51ac48` separately; the 15a log recorded 931 passed on `e6c9611`, and this lane adds 68 tests.)
* **Lane guard** (`lane-guard.txt`): the granted seam files (`api/main.py` 2 lines, `jobs.py` 2 lines, the regenerated `openapi.json` and `api-types.ts`) and **`backend/tests/test_live_worker.py`, which `lanes.md` does not list under OWNS** (the dispatch named one test file; the worker tests needed their own). Raised to god as `SEAM: lanes.md OWNS backend/tests/test_live_worker.py` in the done message.
* Fresh critic, Dwight's re-review and Jev's Job 4: see section 5b (appended below when they return).

## 6. LANDING
Not mine: god lands it. Nothing pushed, no PR, no deploy, no real paid AI call, no Odds API call (zero), no real ESPN or Kalshi call in this step (all tests use recorded fixtures; the hand check is PENDING 2026-10-15, see KNOWN LIMIT). Live app, the PC, ports 8000/5432 and its containers were never touched.

**Honest list of what was NOT done or NOT proved:** nothing ran against a game in progress; the web contract (null probability handling, stale rule, 15-min Kalshi rule) is untested by a screen; Codex's workspace was out of credits so one work order was built by Opus; the sandbox here blocks the local test database, docker and the uv cache, so gate, pytest and codex ran with the sandbox off (only those commands).
