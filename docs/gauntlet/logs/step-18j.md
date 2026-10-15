# Step 18j: screens for the step 18 outputs — step log (lane web, card HAG-71)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web`, base origin/main `60833f4` (2026-10-14). Coord task #35.

## 1. PLANNING

**In the owner's words.** This step puts the new score simulator on the game page: the margin and total it expects,
how often the home or away side covers the spread, and how often the game goes over or under the total. It also shows
on the week board which pick mode the app is using. It replaces nothing. It is **not** a pick: the pick stays the win
model's, and every simulator number is labelled as shown only, not shown to beat the betting market.

**Goal (dispatch god 5f9ef8, plan `docs/model/PLAN.md` §2 row 18j).** Show on the existing screens, per game, the
simulator's margin, total, cover, push and over/under chances (`PredictionOut.simulation`, labelled as shown only,
never a pick), the pick mode (`WeekOut.pick_mode`), and the 18i spread/total/value outputs where the API already
serves them. 18k's run-check state (`PredictionOut.simulation_check`) comes later, when god says 18k has landed.

**What the API serves (read in `backend/nflpi/api/schemas.py` on `60833f4`).** `SimulationOut`: `home_points`,
`away_points`, `expected_margin`, `expected_total`, `margin_80`, `total_80`, `home_spread` (owner-brief sign: a
favourite is negative, `data/asof.py:48`), `total`, `home_cover`, `away_cover`, `spread_push`, `over`, `under`,
`total_push`, `n_simulations`, `label` ("Score simulator, football-only inputs: not shown to beat the betting market or
the win model", `predictions/engine.py:37`). It is `null` when there is no fitted simulator or no input
(`engine.py` `_safe_simulation`). `PickModeOut`: `mode`, `assumed`, `label`. `MarketOut` already has `spread_line` and
`total_line` (shown today in the Market section). **Not served:** 18i's value ratings (`nflpi/value/rate.py`: stars,
`UNRATED`, `NO_BET`) are in no schema or route. Told god (2026-10-14, `18j-plan-note`); 18j does not show them and
does not touch backend files. PLAN §3.5: every rating would be `UNRATED` today anyway.

**Done when.** The spec below holds in `apps/web/e2e/sim18j.spec.ts`; the FULL browser suite is green on a fresh build
(god's lesson from PR #39) and typecheck is 0; Dwight has no CRITICAL on the diff; a fresh critic PASS; lane-guard clean.

**Tier T2** (new user-facing behaviour, no API or data change). Prior decisions read: D74 (`PLAN.md` §5: maths picks,
nothing else chooses a pick), PLAN §3.2-3.5 (the cover and totals chances are not shown to beat a coin flip; no value
claim), `CLAUDE.md` (never "lock" or "guaranteed"; win probability and uncertainty shown apart; no prediction logic in
the client).

**Pre-flight.** (1) Problem: the simulator runs on every game since 18h but the owner cannot see it. (2) Why now: 18h
and 18i landed; 18j is the last step of the 18 plan. (3) Scope: one game-page section and one week-board line; cut: the
game card (the board stays as dense as today), value ratings (not served), any chart of the simulated distribution.
(4) Success signal: the owner can read the cover and over/under chances for a game without mistaking them for a pick
(qualitative; read on the iPhone after deploy). (5) Reversibility: two-way (UI only).

**Assumptions.** validated: field names and nullability (schemas on `60833f4`); the label text comes from the server;
the e2e seed never fits simulator settings (`tests/e2e_seed.py` calls no `save_sim_params`), so every e2e game has
`simulation: null`. assumed: whole-percent chances and one-decision points read well at 393 px (design critic checks).
unknown: none that changes the design.

**Instrumentation.** None new: UI only, no metric moves in production. N/A with that reason.

**Skills.** `/graft`/grep: the seams were pinned by exact-symbol reads (`SimulationOut`, `PickModeOut`, `SIM_LABEL`,
`SECTIONS` in `game-view.tsx`, `PageHead` in `week-board.tsx`). `/jevgrep`: N/A, no behavioural question was open after
those reads. TDD: Playwright browser tests are the public seam (as steps 6, 7, 10, 15). `/ponytail` in every work order.
Design Gauntlet: applies (game page, week board). `harness-engineering`: N/A (no runner or evaluator).

**Test data.** The tests read the real game and week replies and add a `simulation` typed against the generated wire
type (`components["schemas"]["SimulationOut"]`), the way the passkey tests rewrote `/api/health`; service workers are
blocked for those tests. Values are made up. No member names anywhere.

## 2. SPECIFICATION (frozen before production code)

Game page (`components/game/**`), a "Score simulator" section, `id="simulator"`, tab "Simulator" in the Sections row
after "Market":
- S1 With a simulation: the section shows the server's `label` word for word and the sentence "Shown only: not a pick,
  and it does not change the pick above." It shows the average score (`away_points`, `home_points`, one decimal, with
  the team abbreviations), the home margin (`expected_margin`, signed, one decimal) with "80% of runs between A and B"
  (`margin_80`, signed, one decimal), the total (`expected_total`, one decimal) with its 80% range (`total_80`), and
  "Based on N simulated games." (`n_simulations` with a thousands separator).
- S2 Against the spread, when `home_spread` is not null: the line as "<home abbr> <signed spread>" ("Pick'em" at 0),
  then the home cover, away cover and push chances as whole percents labelled with the team abbreviations and "Push".
  Over/under, when `total` is not null: "Over/under <total>", then over, under and push as whole percents. When
  `home_spread` or `total` is null, that block says "No spread yet." or "No total yet." and shows no chances.
- S3 With `simulation: null`: the section says "No simulation for this game yet." and nothing else.
- S4 The section never uses the words "lock", "guaranteed" or "bet"; the pick panel is unchanged by it.
Week board (`components/week/**`):
- S5 The board shows the API's `pick_mode.label` word for word under the week heading.
Quality:
- S6 No serious or critical axe finding on the game page with a simulation; no sideways scroll at 393 px and 320 px.

Gate: `apps/web/e2e/sim18j.spec.ts` (new), then the FULL browser suite on a fresh build (`e2e/`), typecheck. Under
D71 the pull request's CI is the full gate again on the final head.

**Spec amendment after design critic 1 (before WO2; `reviews/design-1.md`).** S1: the margin fact is labelled
"<home abbr> margin"; ranges read "80% of runs: A to B". S2: the spread heading reads "<home abbr> <signed spread>, the
line the simulator used" and the total heading "Over/under <total>, the line the simulator used" (the simulator keeps
the line from its prediction run; Market shows the latest line, so the two can differ). Tests updated in the same
commit as this amendment.

## 3. IMPLEMENTATION

Provider: Codex (Ryan `ryan-mv5mjwq1`), rung unchanged, no climbs. Red first: `1bf2cc2` (run `s18j-red-1`, 6/6 fail:
no `#simulator` section, no pick-mode line).
- WO1 (`evidence/wo-1.md`, try 1): `3b0ffc9`, new `components/game/simulation.tsx`, tab and section in `game-view.tsx`,
  pick-mode line in `week-board.tsx`. Diff inspected (allowed files only); typecheck 0; `s18j-green-1` 6/6 on a fresh build.
- Design Gauntlet: before/after screenshots at 393 and 1280 px in `~/.claude/plans/nfl-pickem-lanes-logs/step-18j/`;
  fresh read-only design critic, report and triage in `evidence/reviews/design-1.md` (1 MUST: the simulator's spread
  could differ from Market's line with no word saying so; accepted with 2, 4-9; not taken: 3, 10, reasons there).
  Defect to test first: spec amendment and amended tests `258d62f`, red for the right reason (`s18j-red-2`: S1 fails on
  "LV margin", 5 pass).
- WO2 (`evidence/wo-2.md`, try 1): Ryan went quiet at 18:04 UTC (god nudged), reported done 19:05 UTC; no ladder
  climb. Diff inspected (simulation.tsx, week-board.tsx only); typecheck 0; `s18j-green-2` 6/6 on a fresh build;
  committed `fd99c20`. Re-shot `after2-*` (393, 1280): all eight design items visible; the phone header keeps
  "Yahoo sheet" on its row; the pick-mode line sits under the header. design.md: no durable change.

## 4. CLEANUP

Scope-locked `/refactor` read of the touched code (`simulation.tsx`, the `week-board.tsx` line, `game-view.tsx` two
lines) on `fd99c20`. Result: **no change needed**. Reasons: the spread and total blocks look alike but differ in
labels, null field and values; a shared helper would add props for two callers (ponytail). `Fact`, `signed` and
`spreadText` are local, small and used only here (moving `Fact` to `ui.tsx` was design finding 10, not taken). The
`<span>` in each line heading is the single text node the spec test counts; harmless. No dead code, no unused
imports (typecheck 0). No proof rerun needed (no edit).

**Spec amendment 2 (after full run `s18j-full-1` on `b4ba105`).** S5: the pick-mode label (word for word) sits at the
foot of the week board, after "Select a game for the full matchup. Picks lock at kickoff.", not under the heading. Why:
under the heading it wraps to two lines at 393 px and pushes the first game's pick buttons below the first screen
(`phone-layout.spec.ts` L1: 803 > 778). The red test is L1 itself; S5 already checks the label is shown.

**WO3 (after amendment 2).** `evidence/wo-3.md`, try 1. Ryan edited at 20:15 UTC and reported at 22:25 UTC. The
diff matched the order (one line moved in `week-board.tsx`); typecheck 0. Committed `907f6fa`.

## 5. VERIFICATION

Runs (logs in `~/.claude/plans/nfl-pickem-lanes/logs/step-15-web/<name>.log`):
- `s18j-full-1` on `b4ba105`, the FULL suite on a fresh build: 246 passed, 6 failed, 2 skipped, 20.4 min. One real
  failure, phone-layout L1 (803 > 778, caused by 18j), which led to amendment 2 and WO3. Five timeouts: live L9 (axe
  `page.evaluate`), passkey K3, phone-layout L8 (cards never loaded), pwa P12 and P13.
- `s18j-green-3` on `10b9978` plus the WO3 diff, a fresh build of five spec files: L1 passes; 9 failed, every one a
  timeout of minutes (passkey K1, K3, K11; phone-layout L6; pwa P3, P4, P9, P12, P13), 53 min. The failing set changed
  from run to run. The machine was under heavy CPU load from other sessions.
- god (2026-10-14 22:20 UTC, under D71): PR CI is the full gate. Locally, show green on the specs 18j touches.
- `s18j-green-4` on `907f6fa`, a fresh build of sim18j, phone-layout, step2 and restyle: 56 passed, 2 failed. sim18j
  6/6, and phone-layout in full (L1 and L6 included). The two failures are restyle R1 and step2 E3, both waiting for
  `game-card`. E3's page said "Loading week"; R1's page snapshot shows the cards arrived after the limit. These are
  slow loads; the full suite runs on PR CI.
- typecheck 0 on `907f6fa`. Security: Dwight PASS on `b4ba105` (`evidence/reviews/security-1.md`). The only later
  code change is WO3's one-line move.
- god's check (23:14 UTC): does the board now wait on a new query? **No.** `git diff origin/main...HEAD` on
  `week-board.tsx` is one `<p>` after the card list, reading `data.pick_mode.label` from the week reply the board
  already loads. `simulation.tsx` has no hooks and no fetch; it reads the `game` prop. `game-view.tsx` adds only a tab
  and the section. No new request runs before the cards render. R1 and E3 are left to PR CI (D71).

**Fresh critic 1 on `5a91a18`: PASS + 1 MEDIUM** (`evidence/reviews/critic-1.md`). **Amendment 3:** S1 lists the
home team first (design finding 6, WO2). S5b (new): a week reply without `pick_mode` (an old reply from the offline
cache) still shows the board's cards. Red: `s18j-red-3` (no game card in 15 s). Fix: WO4.

**WO4.** `evidence/wo-4.md`, try 1. Ryan reported at 23:31 UTC. The diff matched (one guarded line in
`week-board.tsx`); typecheck 0. `s18j-green-5` (a fresh build: sim18j and phone-layout): 18 passed, 2 failed.
S5b now passes (it was red in `s18j-red-3`); L1 passes. The 2 failures: sim18j S3 timed out "while setting up page"
(the browser fixture, before any app code ran; S3 passed in green-1, green-2, green-4 and critic-1), and phone-layout
L2 waited for `game-card` (it passed in green-4). Same slow-load pattern; PR CI decides (D71).
- **Fresh critic 2 on `75c20a7`: PASS** (`evidence/reviews/critic-2.md`): sim18j 7/7 on a fresh build (`s18j-critic-2`);
  typecheck 0; no CRITICAL, HIGH or MEDIUM. Critic 1's MEDIUM is fixed; the only other new field read (`simulation`) is
  safe when absent; every red test comes before its fix.
- Jev Job 4 (`decide.sh nfl-pickem-lanes web review-18j`): "advisor, jev unavailable", so the call goes to god.
- lane-guard vs origin/main: every production file is in lane web. Unowned new files need a `lanes.md` entry (god):
  `apps/web/e2e/sim18j.spec.ts`, `docs/gauntlet/logs/step-18j.md`, `docs/gauntlet/logs/step-18j-evidence/**`.

## 6. LANDING

Not done here: no push, PR or merge without the owner's yes, and god lands. Handed to god: the lane/web head below.
PR CI is the full browser gate (D71). Carried: 18i value ratings are served by no API (told god on 2026-10-14);
18k's run-check state (`simulation_check`) is added after 18k lands (the owner's yes on HAG-75), then gen:api
(Dwight A1).

## LANDING (integrator, 2026-10-15)

Pull request #40 from `lane/web` at `e41a965`. CI: the push run was green on every job. The pull-request run's e2e had 252 passed and 1 failed: `pwa.spec.ts` P6 (B11 build ID), the known flaky test. A rerun of that job was green (attempt 2). lane-guard was clean after the integrator added `e2e/sim18j.spec.ts`, this log and its evidence to lane web. Merged as `bd9a9ff` at 00:57 UTC.

**Deployed:** deploy 13 to the owner's PC at `bd9a9ff`, 01:46 UTC (D73). The PC dropped off SSH from about 01:00 to 01:45 UTC (Tailscale ping still answered), so the deploy ran only after three SSH checks in a row passed, and it ran detached on the PC. Backup first, no migration (alembic `0010`), row counts kept (two new predictions from the worker), `/api/health` 200, and no errors in the app or worker logs. **PENDING:** the `simulation_check` display, after 18k lands (HAG-75).

