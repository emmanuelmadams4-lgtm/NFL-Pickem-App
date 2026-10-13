# Step 15f (server side): grade the in-game win probabilities of finished games (no screen)

Session: owner's Mac, 2026-10-13, lane `livegrade` (worktree `.claude/worktrees/lane-livegrade`, branch `lane/livegrade`, base `main@173f26b`). Coordinator: Claude Sonnet 5.5 (hive temp "Oscar", `worker-livegrade`). Tier T2. Coord task #24, claim `claims/livegrade`, state file `~/.claude/plans/nfl-pickem-lanes/lane-livegrade.md`.
Evidence: `docs/gauntlet/logs/step-15f-evidence/` (design.md, gate.sh, mutate.py, run-locked.sh, `final1-*`, `final2-*`, `mutation.log`, reviews).
Row covered: `odds-live-plan.md` row 15f ("Grade the model in-game ... Display and grading only | hand count on two finished games"). NOT in this step: any screen, the market-consensus candidate (15e), any change to the live worker or fetch code, any migration.

KNOWN LIMIT (read first): no real game has been played with the live worker on (first one is Thursday 2026-10-15, SEA @ DEN). All series in the tests and the hand count are made up. **Real-game hand count: PENDING, after 2026-10-15.** No network call was made in this step.

## 1. PLANNING
* **In the owner's words (D55):** "can we also add realtime scores please for each game until the game ends if the game is going on"; plan row 15f asks that the in-game path be graded for the Results page. Display and grading only: nothing here can change a pick or a prediction (the plan's "Locked picks" line).
* **Builds / replaces / is not:** builds one pure grading module and one read route. Replaces nothing. Not visible to the owner yet (no screen).
* **Pre-flight:** Problem: after a game ends nobody can tell whether our model, ESPN or Kalshi called it better while it was on. Why now: the series (`live_states`, `market_quotes` kind live) is already stored. Scope: grading maths + one route; cut: screen, 15e, any model use. Success signal: after 2026-10-15 the route returns scores for SEA @ DEN that match a hand count. Reversibility: two-way (no migration; remove one route).
* **Assumptions:** validated: table shapes (read models.py), the Results page's pregame rule (views.py: last prediction before kickoff, or backfill); assumed: real series density (see KNOWN LIMIT).
* **Skills:** `/jevgrep`, `/graft`: not run (files named in the dispatch, read directly). `/tdd`: tests committed red first. `/ponytail`: stated in the work order. Design Gauntlet: N/A (no UI).
* **EFFORT:** PLANNING/SPECIFICATION high; IMPLEMENTATION low; VERIFICATION high.

## 2. SPECIFICATION
Frozen in `step-15f-evidence/design.md` (clauses G1-G12), each with tests in `backend/tests/test_live_grade.py` (committed red in `ced4fb7`; red reason: `nflpi.analytics.live_grade` did not exist). Choices the dispatch asked to state plainly:
* **Weighting (G1): by time, not per stored point.** Each stored value holds until the next stored row for that game and counts for the seconds it held. Reason: ESPN stores a row only on change and Kalshi on each poll, so busy stretches make many rows and halftime few; per-point voting would grade how dense the data is. The flat pregame baseline gets the same weights (whole window).
* **Missing (G4, G5):** a value that is null, not finite, or outside 0..1 is missing: no weight, ends the previous hold, never filled, guessed or clamped. A forecaster with fewer than 3 held segments or under 50% of the window covered is `not_enough_data` with null scores (points and coverage shown). Pregame needs one point (the prediction itself).
* **Ties (G6):** final score equal -> status `tie`, no scores, in no average. **No live row (G7):** final game with rows but none `in` -> `no_live_data`; a final game with no rows at all is left out of the list. **Overtime (G8):** no special case; the window runs to the game's last row, period 5 rows are ordinary points. **Clamp (G9):** log loss reuses `metrics.game_log_loss` (clip at `metrics.EPS`); Brier is not clamped. **In progress (G10):** a game not `final` in `games`, or whose last row is still `in`, is `in_progress` and never scored or averaged.
* **Window (G2):** starts at the first `in` row; ends at the game's last row, which must be `post` or `lost`.
* **Averages (G11):** per forecaster, mean over games where it was scored, equal weight per game; week and season (every week).
* **Route (G12)** `GET /api/live/grades?season=&week=` (token, read only). Contract in the done message.
* **Hand count on two made-up games** (the plan's gate; the tests assert these numbers). Game A (home won), window 60 min. ESPN: .6 for 20 min, .8 for 20 min, null for 10 min (gap, no weight), .9 for 10 min. Brier = (20x(.4)^2 + 20x(.2)^2 + 10x(.1)^2)/50 = (3.2+0.8+0.1)/50 = **0.082** (the per-point mean would be 0.07); log loss = (20x0.5108 + 20x0.2231 + 10x0.1054)/50 = **0.3147**; coverage 50/60. Kalshi: .5 carried in from before the start for 30 min, .9 for 15, .95 for 15: Brier = (7.5+0.15+0.0375)/60 = **0.1281**, log loss **0.3857**. Pregame .7 flat: Brier **0.09**, log loss **0.3567**. Game B (away won), window 30 min. ESPN .5/.3/.1 for 10 min each: Brier (.25+.09+.01)/3 = **0.1167**, log loss **0.3851**; Kalshi has only 2 quotes -> `not_enough_data`; pregame .55: Brier **0.3025**, log loss **0.7985**. Averages over A and B: ESPN Brier **0.0993**, pregame **0.19625**, Kalshi (A only, 1 game) **0.1281**.
* **Real-game hand count: PENDING (after 2026-10-15).**

## 3. IMPLEMENTATION
| Work order | Builder | Commit | Proof |
|---|---|---|---|
| WO-1 `analytics/live_grade.py` + WO-2 route in `api/live.py` (one subagent) | **Claude (Sonnet subagent)**; Codex refused: `codex exec` with the default model returned "The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account." (13:50 UTC; same as lane newswire) | `54ad438` | 41 of 43 green on first run; the 2 reds and one spec slip were mine (see below) |

* **Built by Claude and why:** Codex unavailable (exact error above). The builder is never the critic. I inspected the diff and reran the proof myself.
* **My mistakes found at the first run, fixed in the tests (not the code):** G5 said ESPN needs 3 points, but two of my tests gave ESPN 1 or 2 points; I applied 3 points to both ESPN and Kalshi (spec stays uniform) and gave those tests 3 points. The `week=0` echo test failed because the fixed 422 text contains "0"; the test now allows digits that are part of the message. `test_live_api.py` asserted `/api/live` is the only live route; updated to allow `/api/live/grades`.
* Gen:api: `packages/shared/openapi.json` and `api-types.ts` regenerated (436 added lines, no removals), committed `1c12f85`.

## 4. CLEANUP
Scope-locked to own files. `ruff format` on the three own files. No other change: module is 160 lines, one job, functions under 50 lines.

## 5. VERIFICATION
* **Gate x2 on the rebased code** (base `main@43dfc46`; `main` is now `f0f5308`, one docs-only commit that touches only `docs/gauntlet/STATE.md`, so the code is the same): `step-15f-evidence/r1-summary.txt`, `r2-summary.txt`. Each: pytest **1268 passed** (r1 260 s, r2 164 s), `ruff check nflpi tests migrations` clean, `npm run gen:api` exit 0 and `git status packages/shared` empty (no drift). Earlier pair before the rebase: **1236 passed** twice (`final1-*`, `final2-*`).
* **`alembic check`:** r1 and r2 printed "Target database is not up to date" because the shared test database is built by `create_all`, not by migrations. Rerun on a fresh scratch database (`nflpi_alembic` on `nflpi-lane-live-db`, dropped after): `alembic upgrade head` reached `0007 (head)`; `alembic check` printed **"No new upgrade operations detected."** (`alembic-final.log`).
* **Targeted:** 81 tests (`test_live_grade.py`, `test_live_api.py`); every clause G1-G12 has a test that fails when it is broken.
* **Mutation sweep** (`mutate.py`, `mutation.log`): 24 of 26 caught; the 2 survivors are equivalent mutants (documented); one real survivor (a mid-game lost row counts as a point) was fixed in `c3bcbfd`/`2b37b66`.
* **Security (Dwight):** PASS. D1 (window end) and D3 (pregame fallback labelling) fixed in `8dd7bed`. S1 carried: the route reads a whole season per call; the Results page must open it once, not poll it.
* **Critic (new, no build transcript):** see the done message.
* **Real-game hand count: PENDING (after 2026-10-15).** All numbers above are from made-up series.

## 6. LANDING
Not mine: god lands it. Nothing pushed, no PR, no deploy, no paid AI call, no network call. Live app, the PC, ports 8000/5432 and its containers were never touched. The sandbox blocks the local test database, uv cache and docker, so pytest/ruff/uvx/codex ran with the sandbox off (only those commands).
