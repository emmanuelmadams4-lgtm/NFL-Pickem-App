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
