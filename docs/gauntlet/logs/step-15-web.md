# Step 15 web: live scores on screen (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · tier T2 · Design Gauntlet applies
Dispatch: hive message `2026-10-13T14-20-36-272Z-38b52c`, coord task #27. Worktree `.claude/worktrees/lane-web`, branch `lane/web`, restarted from main `d8276a2`. Coordinator Jim; builder Ryan (Codex, default model once, then Claude Sonnet subagents); security reviewer Dwight; one fresh critic per round.
Evidence: `docs/gauntlet/logs/step-15-web-evidence/` (work orders, reviews, `gate.sh`, `gate-summary.txt`, failing excerpts). Raw logs stay outside the repo by the integrator's rule (nothing over 200 KB committed): `~/.claude/plans/nfl-pickem-lanes/logs/step-15-web/`. Screenshots: `~/.claude/plans/nfl-pickem-lanes-logs/step-15-web/`.

## 1. PLANNING

**In the owner's words (D55):** "can we also add realtime scores please for each game until the game ends if the game is going on". Plan row 15d (`hive/research/odds-live-plan.md`): "Live win probability on screen … client only renders it. 'Stale' shows when `updated_at` is over 2 minutes old."

**Builds / replaces / is not.** Builds the screen half of step 15: while a game is in progress the game card and the game screen show the score, the period and clock, ESPN's live win probability, Kalshi's price, and a marker when the numbers are stale or unconfirmed. Replaces the bare "In progress" state (today a started game shows its kickoff time until the final score arrives). It is not a new model: nothing here changes a pick, a prediction, the sheet or the points; the server route `GET /api/live` (step 15d, on main) is not changed.

**Pre-flight (T2).**
1. Problem: during a game the owner cannot see the score or how the game is going in the app; the data is on the server since 15d and nothing shows it.
2. Why now: the first game in progress is Thursday 2026-10-15 (SEA at DEN).
3. Scope: one shared fetch function, one hook that polls only while a game is in progress, the card's score area plus one line, the game screen's header plus one line. Cut: play-by-play, a chart of the live probability, alerts, in-game grading (15f), any use of live numbers by the model.
4. Success signal: on Thursday the card shows the score within about a minute of ESPN, and when the feed stops it says so instead of showing an old score as current.
5. Reversibility: two-way (web only, no migration, no API change).

**Assumptions.** validated: the route contract (`docs/gauntlet/logs/step-15d.md`, types `LiveOut`, `LiveGameOut` in `@nflpi/shared`); validated: the week and game replies mark a started, unfinished game `in_progress` (`views.py:58`); assumed: ESPN's `clock` string is display-ready ("4:12"); unknown, not blocking: how the numbers behave in a real game (15d's own pending check, 2026-10-15). Carried from 15d and binding here: a null probability means "none right now" (never invented); `post` is not final for ever (the week data decides "Final"); a flat Kalshi price older than 15 minutes arrives as null.

**Dependencies and reach.** Server: none (route on main). Deploy: the owner's, after landing; a real live check is PENDING 2026-10-15 and is not claimed here.

**Skills.** `/jevgrep`: not used (`JEVGREP: not-checked`): the seam was named in the dispatch and the contract; files read directly (`game-card.tsx`, `game-header.tsx`, `queries.ts`, `client.ts`, `persist.ts`). `/graft`: N/A, same reason. `/tdd`: browser tests first, red before any production change. `/ponytail`: in every work order. `harness-engineering`: N/A (no runner, evaluator or approval boundary changes). Design Gauntlet: applies; brief below. Parallel lanes: lane web; `lane-guard` before landing.

**Design brief** (source: `design.md`; register product). The live state must be read in one glance on a phone: score first, then where the game is, then how it is going. Probability and uncertainty never share a visual; the model's pregame pick stays labelled as the model's and is never overwritten by a live number. Missing is an en dash, never a zero. Stale and unconfirmed are words, not colour alone. No new colour token, no animation that loops (no pulsing dot), no new element type.

**Carried in from 8a2 (item 4), done in this step because it edits the same card:** type the replaced `stars_out` object in ST3b and ST3c; one server test for the silent state; nits in `game-card.tsx` (`no_list.length > 0` twice, one mis-indented div), `views.py` (import style), `_clean_star_text(...) or ""`.

**Effort.** PLANNING and SPECIFICATION high; IMPLEMENTATION per work order (decision desk); VERIFICATION high.

## 2. SPECIFICATION

The first draft of this section (criteria L1 to L13) was reviewed before any test or code by a fresh UX reviewer: 3 critical, 12 major, 5 minor (`step-15-web-evidence/reviews/ux-spec-1.md`, every finding decided there). This is the rewritten, frozen text.

Public seam (frozen): `api.live()` in `packages/shared/src/client.ts` (`GET /live`, type `LiveOut`) and `keys.live`; `useLive(games)` in `apps/web/lib/queries.ts`; new components under `apps/web/components/live/`; browser tests `apps/web/e2e/live.spec.ts`. The fake in-progress fixture is made in the browser test by replacing the API's answers (`**/api/weeks/**`, `**/api/games/**`, `**/api/live`), the pattern `phone-layout.spec.ts` and `stars.spec.ts` already use. No real network call.

### Words

* A game is **started** when its status is `in_progress`, or its kickoff has passed on the clock `useLocked` uses and it is not `final`, not `postponed` and has a kickoff time. Everything below applies to started games only; a final game is the existing final card.
* **Not updating** = the live reply says `stale`, or the web's last good reply is over 120 seconds old. One failed request alone changes nothing. `updated_at` is never used for this (it stands still through halftime): the contract's rule, a deliberate departure from the plan row's wording.

### One state table (first match wins)

| # | State of a started game | Label | Score | Chance line | Screen-reader sentence |
|---|---|---|---|---|---|
| S1 | Week data says `final` | existing final card, nothing live | week's score | none | existing |
| S2 | Live row `post`, or no row now but a `post` row was seen in this session | "Ended · result pending" ("Ended · score not in yet" with no score) | live, no winner styling, no mark | none | "Ended, result pending: NE 14, KC 21." |
| S3 | Live row `lost` | "Not updating · last seen Q3 4:12" (period and clock when present) | live, secondary ink | none | "Score may be out of date: NE 14, KC 21." |
| S4 | Live row `in`, not updating | "Not updating · Q3 4:12" | live, secondary ink | "Last update 3m ago" (from `last_confirmed_at`), or "No update yet" when it is null; no chances | "Score may be out of date, last update 3 minutes ago: NE 14, KC 21." |
| S5 | Live row `in` | "Live · Q3 4:12" | live | "KC to win now · ESPN 71% · Kalshi 68%" | "Live score NE 14, KC 21, third quarter, 4:12 left." then "Right now ESPN gives KC a 71 percent chance to win; Kalshi price 68 percent." |
| S6 | No row and none seen, or no good reply yet | "Started" | "No live score right now" | none | "Game started, no live score right now." |

Rules that go with the table
* **Score.** Away then home, each with its club code, tabular numerals. Both scores must be present; one null means no score ("No live score right now" in S5 too). While a game is started the score comes only from the live reply; the week's scores are drawn only in S1.
* **Period and clock.** "Q1" to "Q4"; period 5 "OT", 6 "2OT", 7 "3OT". Clock "0:00" in period 2 reads "Halftime", in period 1 or 3 "End of Q1" / "End of Q3", in period 4 "End of Q4". The clock is shown only with a period; any other clock text is shown as it arrives. Nothing is invented: no period, no period text.
* **Chances.** Stated for one club: the model's pick, else my pick, else the home club. Whole percents; under 1 reads "<1%", over 99 reads ">99%" (never "0%" or "100%" for a game in play); the away club's figure is 100 minus the rounded home figure. A null is never drawn as a number: the card shows "ESPN –" or "Kalshi –"; both null reads "No live win chance right now". No hold: a null shows at once.
* **Pregame words.** While a game is started the card's "Model pick" reads "Pregame model pick" and "Market" reads "Pregame line"; the hit-rate sentence and the "In progress" chip are not shown. These depend on the game's status only, never on the live reply.

### Acceptance criteria

Functional
* **L1 no started game, no call.** With no started game on screen the web makes no request to `/api/live`.
* **L2 polling.** With a started game on screen the web asks `/api/live` at once, then every 30 seconds; every 120 seconds when every started game on screen is in S2; not while the page is hidden. A board left open across a kickoff starts polling without a reload. The live reply is never written into the week or game data and is not kept in the offline cache.
* **L3 the card** shows each of S2 to S6 exactly as the table says, in the place of the date line and the kickoff time, with the chance line after the uncertainty row.
* **L4 missing stays missing**, as the rules above say (null score, null chance, null period, null clock, null `last_confirmed_at`).
* **L5 the game screen.** The header's centre column shows the label above the score; the "In progress" chip is not shown; the kickoff line stays. One block under the header shows the chance line with reasons for a missing number ("ESPN – · none right now", "Kalshi – · no fresh price"), "Checked just now" or "Checked 1m ago" (time of the web's last good reply, in the shared `ago()` words, which count in minutes), one sentence saying what the Kalshi number is ("Kalshi is a prediction market. The figure is the price of a KC win, not this app's forecast."), and one caption on the model's tiles ("Model win chance before kickoff. It does not change during the game.").
* **L6 never moves a pick.** With a started game and any live reply, the model's pick and its percentage, the sheet label word, the points and the pick buttons' state are what they are without the live reply.
* **L7 it ends.** When the week data turns `final` the live block is gone and polling for that game stops.

User-facing
* **L8 phone fit.** At 393 px and 320 px: no sideways scroll and nothing in the live block is cut, with the worst case on the card (three-letter clubs, two-digit scores, an upset watch, two QB alerts, a change note). Going live adds no height to that card (it is measured before kickoff and again live), and an ordinary live card is no taller than 400 px at 393 px (the board's existing density rule).
* **L9 accessibility.** No serious or critical axe finding (dark and light) with a live game on screen; the table's sentence is the only thing a screen reader gets for the label and score (visible parts hidden from it); "Not updating" and "Ended" are words, not colour alone; no live region.

Operational
* **L10 failure is quiet and honest.** `/api/live` answering 503 or not at all gives S6 when nothing was shown before, and S4 once the last good reply is over 120 seconds old; no error toast, no crash, and the next poll still happens. A 401 follows the app's standing rule for every request: the token is dropped and the sign-in card shows.
* **L11 no feed text in an attribute.** The club codes on screen come from the game the card already has, not from the live reply; `clock` is the only free text taken from the live reply and it is rendered as text only.

Not in this step: a weather or other delay cannot be told from period and clock (the server would have to pass ESPN's status text): carried to the integrator. Play-by-play, a chart, alerts, in-game grading (15f).

Gate: `docs/gauntlet/logs/step-15-web-evidence/gate.sh <label>` (pytest, ruff, `gen:api` no drift, typecheck, the whole browser suite), twice, under `res:gate` and `res:e2e`.

**Spec corrections during the build (coordinator, after the first run on work order 1; recorded, not hidden):**
1. L10 said a 401 from `/api/live` gives S6. The app's standing rule (`providers.tsx`: any 401 from any request drops the token and shows the sign-in card) is the right one and is a security rule; the test row was wrong. The row is replaced by a test of the standing rule.
2. L8 asked for 400 px at 320 px too. The board's density rule (`phone-layout.spec.ts` L1) is set at 393 px only; the worst live card measured 460 px at 320 px. The 400 px limit stays at 393 px; 320 px keeps "nothing cut, no sideways scroll". Carried to the integrator in the `done`.
3. Test defects of mine, fixed: the offline-cache check looked for `home_win_prob`, which the week's own predictions carry (now `kalshi_home_prob`); the fake's route handler threw when a request was still in flight at the end of a test; three `/^Live/` locators could match the screen-reader sentence.
4. L8 again, after work orders 4 and 4b: with normal padding the worst card (an upset watch, two QB alerts and a two-line change note at once) is 416 px live. The 400 px figure was reachable only by squeezing the padding, which the visual critic marked major. The rule that can be kept and checked: going live adds no height to the worst card (measured before kickoff, then live, in the same test), and an ordinary live card stays within 400 px. Carried to the integrator in the `done`.

## 3. IMPLEMENTATION

**Red.** `step-15-web-evidence/red-1.txt`: tests only at `9162fbb` on the build of main: 46 failed, 0 passed when the coordinator stopped the run to free the shared test slot (phone project whole).

**Work order 1 (data layer and the card; `wo-1.md`). Builder: Ryan, Codex default model, try 1.** Diff read by the coordinator: 6 files changed plus new `apps/web/components/live/state.ts`, all inside the allowed scope; no test edit, no schema change. Coordinator's proof: typecheck exit 0; ruff clean; `test_api.py` 12 passed; build exit 0; browser run `green-1` (load 13.22 10.02 9.82) `live`, `stars`, `phone-layout`: 92 passed, 18 failed. Of the 18: 8 are the game screen (work order 2); 9 were defects in the coordinator's tests or spec (section 2, corrections 1 to 3); 1 was the 320 px height limit (correction 2). Rerun `green-2` after the test fixes (load 9.92 10.46 10.17), `live.spec.ts`: 68 passed, 8 failed, the 8 being the two L5 tests and L9 on both sizes: work order 2. Screenshot looked at: `wo1-board-phone.png` (label, score, pregame words and chance line as specified). Noted for the design critics: the live card uses tighter padding (`p-2`, `gap-1`) than its neighbours.

**Work order 2 (the game screen; `wo-2.md`). Builder: Ryan, Codex default model, try 1.** Diff read: `game-header.tsx`, `game-view.tsx`, `live/state.ts`, inside the allowed scope, no test edit. Ryan flagged a fixture in the coordinator's test (an age that drifted with the page clock): he was right, fixed in the test. Proof: typecheck exit 0; build exit 0; run `green-3` started at load 20.70 (above the limit of 12; the run script did not wait then, it does now): 122 passed, 5 failed, all five by timeout or by a fixture ageing under load, none in work order 2's tests. Run `green-4` (load 10.04), `live.spec.ts`: 75 passed, 1 failed ("Checked 1m ago" on desktop). That one failure led to two things: the shared `ago()` counts in minutes, so the spec's "Checked 20s ago" became "Checked just now / 1m ago" (section 2, L5); and a real defect, below. Screenshots looked at: `wo2-game-phone.png`, `wo2-game-desktop.png` (label over the score, chance block with "Checked just now" and the Kalshi sentence, the "before kickoff" caption). For the design critics: the pick panel's existing "Live" chip beside "Model pick" now sits near live scores.

**Defect found by the coordinator, to a failing test first.** `useNow()` is server time; the live query's `dataUpdatedAt` is the device's. The "not updating by age" rule and the "Checked" line compared the two, so a phone two minutes behind the server would show "Not updating" on every live game. Tests added: "L4 a phone whose clock is five minutes behind the server still says Live" and "S4 one minute is singular" (the reader said "1 minutes ago"). The test's fake server now shares one clock with the fixtures. Red: `step-15-web-evidence/red-3.txt` (76 passed, 4 failed: those two tests on both sizes). Work order 3: `wo-3.md`.

**Work order 3 (one clock for the age of a reply; `wo-3.md`). Builder: Ryan, Codex default model, try 1.** Diff read: `queries.ts` (`checkedAt` = the query's time plus the `/api/meta` correction), `live/state.ts`, `game-view.tsx`; in scope, no test edit. Proof: typecheck exit 0; build exit 0; run `green-6` (load 8.29 11.20 13.79), `live.spec.ts`: **80 passed, 0 failed**.

**Design Gauntlet, round 1** (screenshots of live, ended, lost and not updating at three sizes, in `~/.claude/plans/nfl-pickem-lanes-logs/step-15-web/`): UX critic PASS WITH FIXES (`reviews/design-ux-1.md`), visual critic PASS WITH FIXES (`reviews/design-visual-1.md`).
Implementation critic PASS WITH FIXES, no critical or high (`reviews/impl-1.md`, each finding decided there). Triage of the two design reports: accepted into work order 4 (`wo-4.md`): UX 1, 2, 3, 7, 10 and visual 1, 2, 3, 4, 5, 6, 10. Not taken, with reasons: UX 4 (a chip or dimming for "Ended": the larger label carries it; no new chip style), UX 5 and 6 and visual 7 (the chance line's words and place were decided in the spec review, findings 8 and 17), UX 8 (visible "Score may be out of date": the label says "Not updating", now in the warning ink), UX 9 ("No update yet" kept), UX 11 (covered by the fixed label height), visual 8 and 9 (existing header pattern). Failing tests first: `red-4.txt` (78 passed, 4 failed: the new "polish" test and L5 with its new assertions, both sizes). Items 4 to 7 of the work order are judged on screenshots.

**Work order 4 (polish; `wo-4.md`). Builder: Ryan, Codex default model, try 1.** Diff read: five files, the ten items, in scope, no test edit. Proof: typecheck exit 0; build exit 0; run `green-7` (load 11.32 11.95 12.92) `live`, `phone-layout`, `step2`: 109 passed, 3 failed. Two were one loose locator of the coordinator's (the new "Live" check matched the label's own word; now scoped to the pick panel; `green-8`: passes). One is real: the worst live card is 476 px at 393 px (limit 400) now that it has normal padding: the locked points row and the pick buttons no longer share a line (`l8-393.png`). Sent back as work order 4b (try 2, `wo-4.md` second part). Screenshots looked at: `wo4-board-phone.png`, `stale4-game-phone.png` ("Not updating" in the warning ink, the block without a box, no "Live" chip in the pick panel).

**Work order 4b (try 2 for item 4). Builder: Ryan, Codex default model.** One line in `points-control.tsx`: the lock icon stays, the word "Locked" beside the points select is for screen readers only (the pick buttons keep their visible "Locked"). Proof: build exit 0; run `green-9` (load 9.59 9.42 10.95) `live`, `phone-layout`, `step2`, `sheet`: 121 passed, 1 failed: the worst card 416 px against 400 (`l8-393.png`: the points row and the buttons share a line again). Two tries used on this item; decided by the coordinator as spec correction 4 (section 2), not by a third squeeze. Run `green-10` (load 11.47) on the corrected test: 4 passed.

**Design Gauntlet, blind A/B** (a fresh subagent given the phone board and game screen before and after under neutral names, not told which is newer): the after version won both pairs and overall ("B shows no score and no quarter … reads like an upcoming kickoff"). Its three defects of the winner, decided: (1) the pregame 87% is still large on the game screen's tiles: not changed, the tiles are the model's own block and carry the "before kickoff" caption; on the card it was already cut to `text-xl` in work order 4; (2) the floating tab bar covers content in the picture: an artefact of a full-page screenshot, the bar floats over a scrolling page as on every screen; (3) no possession, down or last play: out of scope (play-by-play was cut in planning).

**`design.md`:** no durable change. The step uses existing tokens only; the one new pattern (a state word at the head of a label, in `text-warn` when the data is not updating, words always present) is recorded here and in `apps/web/components/live/live-label.tsx`.

## 4. CLEANUP

**Work order 5 (`wo-5.md`), scope-locked `/refactor`. Builder: Ryan, Codex default model, try 1.** Diff read: `live/live-label.tsx` (new, 14 lines) replaces the sliced-string label JSX that sat in two files; `dim` on the state replaces four "S3 or S4" tests; the S5 chance lines moved unchanged into `s5ChanceLines`; `LIVE_POLL_MS`, `LIVE_ENDED_POLL_MS`, `NOT_UPDATING_AFTER_MS` named; one comment on `refetchInterval`. `game-view.tsx`: no change needed. Nothing else proposed by the builder. Not changed, with reasons: `heldPosts` stays a module-level Map (marked `ponytail:`, ceiling named); the `checkedAt` tick offset (reads "just now"). Proof: typecheck exit 0, then the landing gate below (the whole suite on the cleaned code).

**Replay.** Lane replayed onto main `a1fd984` (40 commits, PR #23 among them) with no conflict; `npm run gen:api` after it: no change. All work orders in this step were built by Codex (Ryan, default model); none by Claude.

## 5. VERIFICATION

**Gate** (`step-15-web-evidence/gate.sh`: pytest, ruff, `gen:api` no drift, typecheck, the whole browser suite; summaries in `gate-summary.txt`, raw logs outside the repo in `~/.claude/plans/nfl-pickem-lanes/logs/step-15-web/`).

| Run | Commit | Load before | Result |
|---|---|---|---|
| g1 | `dedb762` | 13.74 | green: pytest 1340 passed, ruff clean, no drift, typecheck 0, browser 205 passed |
| g2 | `dedb762` | 19.36 | backend green; browser 204 passed, 1 failed: L8 at 393 px, `route.fetch` after the page closed. A defect in the coordinator's test (its own route handler lacked the teardown guard the shared `fake()` has); fixed in `2661605` (was `1e2cbad`), test only |
| g3, g4 | `1e2cbad` | 11.19 / 14.74 | cut short by another lane's stray stop signal (hive 1d8260); backend of g3 green; not counted |
| **g5** | `1e2cbad` | 11.19 | **green**: pytest 1340, ruff, no drift, typecheck, browser 205 passed |
| **g6** | `1e2cbad` | 10.62 | **green**: pytest 1340, ruff, no drift, typecheck, browser 205 passed |
| g7 | `e6bc37e` (replayed onto main `a028f2a`) | 12.92 | stalled at 74% of pytest after 3 h 31 min, Mac out of memory (load 76 to 115); stopped by process id on god's word (hive c10df0) |
| g8 | `e6bc37e` | 22.54 | stopped during pytest on god's ruling D71 |

**Ruling D71 (god, 2026-10-14 03:00 UTC, hive b7e15d), recorded here where the gate numbers go:** the Mac cannot finish a full test run in useful time. The full gate on the final head is the CI of the lane's pull request (alembic upgrade and check, whole pytest suite, ruff, web build and types, browser suite, docker build, on the merge with main); god merges only if it is green. Locally: g5 and g6 green on `1e2cbad` plus Dwight's PASS stand as the evidence. The replay onto `a028f2a` changed no file of this step (no conflict; main's changes since are docs, one backend test file and the group screen); lane-guard against main `6c2846a`: `OK`, no further replay needed.

**Security review (Dwight):** PASS at `6296c54`, nothing critical or high; seven findings, each decided in `reviews/security-1.md`. Code unchanged since, apart from the test-only fix above.

**Lane-guard:** `python3 ~/.claude/bin/lane-guard.py check ~/.claude/plans/nfl-pickem-lanes/lanes.md web main --repo .` → `OK`.

## 6. LANDING

**Landed by the integrator (god), 2026-10-14.** Critic-1 PASS on the final head (`reviews/critic-1.md`, committed by the integrator in `f6966f8`). Pull request #34 from `lane/web` at `f6966f8`: CI 9 of 9 checks green (backend, docker, e2e, web, each on push and pull request, plus CodeRabbit), the full gate under D71. Merged as `5029001`.

**Deployed:** to the owner's PC on his standing yes D73, deploy 10 at main `d1a0609` (with steps 18f and 18i part 1), 14:43 UTC: backup first, alembic at `0009`, row counts unchanged, `/api/health` 200, `/api/live` present (answers 401 without the token). **Not yet shown:** live scores during a real game; first check during the 2026-10-15 games (PENDING).

**Branch:** `lane/web` and its worktree stay; lane web carries step 10 web half next (HAG-64).
