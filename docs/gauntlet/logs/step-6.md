# Step 6 of 14 — iPhone PWA (T2), lane `pwa`

Coordinator: Jim (hive `jim-mv5mje0k`). Builder: Ryan (Codex dev, hive `ryan-mv5mjwq1`). Reviewers: Dwight (security), Angela (review and fresh critic).
Branch `lane/pwa`, base `main@9d41cb0`. State file: `~/.claude/plans/nfl-pickem-lanes/lane-pwa.md`. Evidence and logs: `docs/gauntlet/logs/step-6-evidence/`.

## What this step builds, in plain words

* **Builds:** the phone app. The same web app, added to the iPhone Home Screen, that opens with no connection, says clearly when it cannot reach the home server, keeps picks made meanwhile and sends them later, and updates itself when a new version is deployed.
* **Replaces:** the first-draft offline support, which kept two copies of the data (one in the service worker, the small background script that lets the app open offline; one in the app's own saved cache) and never said "the server is unreachable" while the phone itself was online.
* **Is not:** alerts (step 7), a native or App Store app (owner decision 2026-10-11), sign-in changes (step 10), or the dashboard polish list carried from step 4.

## 1. PLANNING

* Roadmap step: PLAN.md row 6. Dependencies: steps 4 and 5 are on main (`d01d0f8`). NEEDS: none (lanes.md).
* Scope (lanes.md OWNS): `apps/web/**`, `packages/shared/src/client.ts`, `packages/shared/src/format.ts`, `backend/nflpi/api/main.py`, `backend/tests/e2e_seed.py`, `backend/tests/test_web_contract.py`, `scripts/e2e-server.sh`, `design.md`, `docs/design/**`, this log and its evidence folder. Seams go to god.
* Prior decisions relied on: phone app = PWA (CLAUDE.md, 2026-10-11); S17 keep the saved query cache, the service worker caches shell and static files only (STRUCTURE_REVIEW.md); B4, B5, B11 (PLAN.md blindspot list); look = reference 06 (D39, D40); logos shown and cached offline (D38); the installed app keeps its own storage, sign in once inside it (OWNER_DECISIONS line 192).
* Deployment reach: none. Local only. On-device check stays `PENDING` (owner), as PLAN row 6 says.
* Rigor tier: **T2** (new user-facing behavior).

### Product Mode (T2)

1. **Problem:** on Sunday, away from home Wi-Fi or with Tailscale off, the owner opens the app and cannot tell whether what he sees is current, and a pick he taps may silently not save.
2. **Why now:** step 5 put the app on the home server behind Tailscale; the phone is the next thing he uses it from, and step 7 (alerts) needs the installed app.
3. **Scope:** make what exists correct and honest (one offline layer, unreachable state, update flow, storage status) and fix the phone layout items carried from step 3. Cut: background sync, push (step 7), any new dependency, the step 4 dashboard list.
4. **Success signal:** the owner's on-device check passes (install, open offline, pick queued and synced, update prompt). No number exists for a single user; recorded as qualitative.
5. **Reversibility:** two-way. All client code; no schema, API or data change.

Assumptions: service worker precache covers every route's chunks — `unknown`, tested by P7. Playwright can hold `/api/**` once the worker stops handling it — `assumed`, tested by P4. iOS Safari honors `scroll-padding` and `navigator.storage.persist()` — `unknown`, owner device check. Static export has a stable build ID per build — `assumed`, tested by P6.

Instrumentation: single-user private app, no analytics by design. The operational signal is on screen: the banner (offline or unreachable, with the age of the data), the "Waiting to sync" chip and the storage status in Settings.

### Baseline (untouched `9d41cb0`, lane database on 127.0.0.1:15436)

| Command | Result | Log |
|---|---|---|
| `uv run pytest -q` | PASS, 99 passed | `step-6-evidence/baseline-pytest.log` |
| `uvx ruff check nflpi tests migrations` | PASS, all checks passed | `baseline-ruff.log` |
| `npm run gen:api` + diff | PASS, no drift | `baseline-genapi.log` |
| `npm run typecheck` | PASS | `baseline-typecheck.log` |
| `npm run e2e` | see section 2 | `baseline-e2e.log` |

Environment: the repo's default test database is the live one on port 5432, which this lane must not touch. `step-6-evidence/gate.sh` points both test databases at the lane's own container `nflpi-lane-pwa-db` (postgres:17-alpine, port 15436, in-memory data). The sandboxed shell cannot bind ports, so the gate runs unsandboxed.

Tools: `JEVGREP: not-ready` (`jg doctor` failed its OpenRouter key check, `startup-jg-doctor.log`); discovery used `grep` and direct reads of the nine PWA files. `HEADROOM: not-routed` (`startup-headroom-doctor.log`). Jev (`decide.sh`) works.

### What exists today (read 2026-10-12)

`public/sw.js` (hand-written; caches static, pages, **and `/api/*`**; `VERSION = "v2"` bumped by hand; `skipWaiting()` on every install), `components/pwa.tsx` (register, offline banner keyed on `navigator.onLine` only, pick sync, iPhone install hint), `lib/sync.ts` (pick queue, last-sync time), `lib/persist.ts` (query cache in localStorage, 7 days), `app/manifest.ts`, Settings "Offline" section (save a week), safe-area padding in the shell.

Gaps against row 6: S17 (two layers), B4 (no unreachable state, no timeout), B5 (no `storage.persist()`), B11 (no build ID, no `reg.update()`, no reload prompt; a new worker takes over under a running page), `/sheet/` not precached, carried phone polish.

### Design brief

```text
PRODUCT:          Pick'em Intel on the owner's iPhone (393x852, installed to the Home Screen), one user.
USER GOAL:        open the week, see each game's recommendation, tap a pick. Primary action: the pick buttons.
REGISTER/PRESET:  product · consumer product leaning dense (reference 06)
DESIGN DIRECTION: dense, honest, calm, thumb-first. Status is said once, in words, where he is looking.
EXISTING SYSTEM:  design.md (reference 06: near-black, lime = mine, condensed headings, pill tab bar);
                  components/ui.tsx, app-shell.tsx, week/game-card.tsx, pick-buttons.tsx, toast.tsx. Tokens in app/globals.css.
PROBLEMS:         carried from step 3 (logs/step-3.md lines 84, 103): about one card per phone screen; doubled
                  "What changed: Changed:"; tooltip can sit under the tab bar; 2px sideways scroll at 320 on a final
                  game; lime on disabled AI buttons; Shift+Tab can hide a pick button under the top bar; section-tab
                  row has no right-edge fade; "next kickoff" in lime; KPI captions wrap to 3 lines at 320; chips near
                  the tab bar on a low card. New: no "server unreachable" state; no update prompt.
SKILL WORKFLOW:   director = design.md + frontend-design-direction; critics = fresh general-purpose subagents
                  (UX, visual/anti-slop, implementation, blind A/B, polish); ux-copy for the banner and prompt copy.
PROPOSED CHANGES: 1 unreachable/offline banner (one component, two messages) 2 update prompt 3 storage row in
                  Settings 4 card density on the phone 5 the carried list above.
DESIGN.MD IMPACT: add the status banner and update prompt patterns if they prove durable; else none.
BAR:              ESPN's mobile NFL scoreboard and game page, 393x852, same states (week list, one game).
STATES:           online · offline with saved data · offline with nothing saved · server unreachable · pick waiting
                  to sync · new version ready · storage kept / not kept · locked · focus-visible · disabled
```

Left for a later step, with the owner's list unchanged: "no chips on Results/Backtest/Settings" and "league-leader reference missing" (dashboard work, not phone-specific), and the eight step 4 items (logs/step-4.md line 222, "for the dashboard step").

## 2. SPECIFICATION

Public test seam: the production export in a real browser (Playwright), as steps 2 to 4. New file `apps/web/e2e/pwa.spec.ts`, 393x852, service worker on.

### Frozen acceptance criteria

Functional (the gate):

| ID | Criterion (PLAN row 6) | Test |
|---|---|---|
| P1 | Manifest valid: standalone, start and scope `/`, 192 and 512 icons plus maskable, all load; manifest and apple-touch-icon links; `viewport-fit=cover` | P1 |
| P2 | S17: the worker controls the page; its caches hold shell and static files and no `/api/` response | P2 |
| P3 | Offline reload shows the saved week and an offline banner | P3 |
| P4 | B4: `/api/**` held 30 s then aborted while online → saved data plus a "can't reach the server … Tailscale" banner with the data's age within 6 s; a pick is queued, not sent; it syncs when the server answers | P4 |
| P5 | Kickoff passes while offline → pick buttons disabled | P5 |
| P6 | B11: `sw.js` carries a build-stamped `BUILD_ID`; cache names carry it; `visibilitychange` finds build B (`reg.update()`); a "new version" prompt with Reload; build A serves until he reloads; after Reload only build B caches remain | P6 |
| P7 | Every tab opens offline, by tapping and by direct load, with no chunk load error | P7 |
| P8 | Standalone with empty storage → the sign-in card works; no install hint | P8 |
| P9 | B5: the app calls `navigator.storage.persist()` and Settings › Offline says whether storage is protected | P9 (two cases) |
| P10 | Install hint on iPhone Safari until dismissed | P10 |
| L1 | 393x852: the first game's pick buttons are on the first screen (above the tab bar, no scroll) and no game card is taller than 400px | phone-layout L1 |
| L2 | 320x568: no week-summary caption wraps past two lines; no sideways scroll | L2 |
| L3 | Game page section tabs fade at the right edge while more tabs are off screen | L3 |
| L4 | "next kickoff" is not lime (lime means mine) | L4 |
| L5 | No disabled button on the game page keeps the lime fill | L5 |
| L6 | A changed pick reads "What changed:" once (the engine's note already starts "Changed:") | L6 |
| L7 | Shift+Tab never leaves a focused pick button under the top bar | L7 |
| G | Whole gate: `gate.sh` (pytest, ruff, gen:api no drift, typecheck, build + every e2e spec), e2e twice in a row | gate.sh |

User-facing: on the phone layout he opens the week with no connection, taps a pick, reconnects, and the pick is on the server (P3 + P4 end to end). Blind compare against ESPN at 393x852 is a win or a tie, and no Critical or Structural design finding is open.

Operational: the banner states the cause (offline or server unreachable) and the age of the data; Settings shows storage status. No server logging change (client-only step).

Pending, not PASS: the owner's on-device check (install, offline open, alerts are step 7).

### Red run (spec committed before any production change)

Command: `npx playwright test e2e/pwa.spec.ts` in `apps/web`, lane database on 15436. Log: `step-6-evidence/red-pwa-spec.log`. Result: **6 passed, 5 failed**.

| Test | Result | Why |
|---|---|---|
| P2 | RED, intended | `expect(apiCall.fromServiceWorker()).toBe(false)` received `true`: the worker still answers `/api/` calls (S17 not done) |
| P4 | RED, intended | no "can't reach the server" banner within 6 s (B4 not built) |
| P6 | RED, intended | `out/sw.js` has no `const BUILD_ID` (B11 not built) |
| P9 kept / not kept | RED, intended | Settings › Offline has no Storage row (B5 not built) |
| P1, P3, P5, P7, P8, P10 | pass | already true on `9d41cb0`; kept as guards for the rewrite of the worker |

Spec faults found and fixed before this run (first full run, `red-e2e.log`: 52 passed, 6 failed):
* P2 failed on the 5 s default wait for the first signed-in load on a cold server. `boardLoaded` now waits 15 s. P2 then passed for the wrong reason (the saved week was fresh, so no API call went through the worker before the check); it now fires its own `/api/health` call and asserts the worker did not answer it.
* P8 emulated `display-mode` through the browser's debug protocol, which Playwright overwrites, and without an iPhone user agent the "no install hint" check could never fail. It now runs with the iPhone user agent and `navigator.standalone = true`, the signal iOS itself gives.

Baseline e2e on untouched code: run 1 had 3 failures (U3, E3, E4), run 2 passed all 47 old tests (`baseline-e2e.log`, `red-e2e.log`). Same cold-start slowness as the P2 fault; watched in every later gate run.

### Phone layout: before evidence and red run

Before screenshots (untouched `9d41cb0` build, seeded data): `step-6-evidence/shots/before-*.png` at 393x852 and 320x568 (week, game, sheet, results, settings), taken by `apps/web/e2e/shots.spec.ts` (`SHOT_TAG=before`; skipped in the gate).

Measured before: at 393x852 the first game card starts at y 534 and cards are 494 to 534px tall, so the first pick buttons end at y 1011, 233px below the tab bar (778). "No live picks graded" wraps to 3 lines at 320. The section-tab row is 745px wide in a 361px row with no fade. "next kickoff" and two disabled AI buttons are lime.

Red run: `npx playwright test e2e/phone-layout.spec.ts`, log `step-6-evidence/red-phone-layout.log`: **7 failed, 0 passed**, each for the measured reason (L1 1011 > 778; L2 two captions at 3 lines; L3 mask "none"; L4 color is lime; L5 "Claude" and "Ask Claude" lime while disabled; L6 "What changed: Changed:"; L7 "Pick LV Team top 41 < bar 53").

Not scripted, judged by the design critics: a tooltip or chip sitting under the tab bar on a low card (the seed has no upset flag to open one); the 2px sideways scroll at 320 on a final game (not reproducible: 0px on the seeded game page).

## 3. IMPLEMENTATION

### Work order 1, try 1 (Ryan, Codex gpt-6-sol, effort medium) — `step-6-evidence/wo-1.md`

Diff inspected by the coordinator: 10 changed files and 1 new (`apps/web/scripts/stamp-sw.mjs`), all inside the allowed scope. Ryan could not bind ports, so his own proof stopped at syntax checks; the coordinator ran the gate.

Gate `gate.sh wo1` (logs `step-6-evidence/wo1-*.log`): pytest **99 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **56 passed, 9 failed**: the 7 phone-layout tests (work order 2, expected), P4 and P7. `out/sw.js` carries `const BUILD_ID = "kC3Bq2uFdDU5bgBsCrYbD"`, no placeholder left. P2, P6 and both P9 are green.

Two findings:
* **Spec fault, fixed by the coordinator.** P7 failed on the game page. The server log shows why the old build passed: Playwright's offline switch does not reach the service worker's own requests, so the old worker fetched `/api/games/…` from the live server while the page was "offline". Every offline test was softer than it read. `pwa.spec.ts` now cuts the worker off too (`goOffline`, through the browser's debug protocol, proven in each test by a request that must fail), and P7 opens the matchup online first, since a matchup he never opened has nothing saved. Rerun on Ryan's build (`wo1-pwa-spec-2.log`): **10 passed, 1 failed (P4)**. P3, P5 and P7 pass with the worker truly offline.
* **Product gap, back to Ryan (try 2).** P4: with a fresh saved week the app makes no API call when it opens, so it never learns the server is unreachable and shows no banner. Needed: a health check when the app opens and when it comes back to the foreground.

A type error in the coordinator's own `phone-layout.spec.ts` (`reducedMotion` belongs under `contextOptions` in this Playwright version) was found by Ryan's typecheck and fixed.

### Work order 1, try 2 (Ryan, gpt-6-sol medium)

One file changed (`apps/web/components/pwa.tsx`): a health check when the signed-in app opens, comes back to the foreground or comes online; a failed check raises the banner, a good one sends queued picks.

Gate `gate.sh wo1b` (logs `wo1b-*.log`): pytest **99 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **58 passed, 7 failed**, the seven being the phone-layout tests of work order 2. All 11 `pwa.spec.ts` tests pass (P1 to P10), all 47 older tests pass. `lane-guard check`: OK. Work order 1 closed in two tries.

### Work order 2, try 1 (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-2.md`

Model pick: Jev `model:pwa:wo-2` → sol 0.97 (follow), effort high 0.71 (advisor); Sonnet advisor → high. Diff inspected: 9 files, all in the allowed scope, 80 lines added and 59 removed.

Gate `gate.sh wo2` (logs `wo2-*.log`): pytest **99 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **65 passed, 0 failed** (L1 to L7 green, P1 to P10 green, 47 older tests green). After screenshots: `step-6-evidence/shots/after-*.png`. At 393x852 the first card, with its pick buttons, is now whole on the first screen.

Coordinator's notes for the critics: on the phone the previous/next week arrows render small and faint beside the week picker; "Yahoo sheet" and "Updated" are two copies each, one per breakpoint (cleanup candidate); the "Changed:" strip is written twice (cleanup candidate).

### Review round 1 (fresh critics on `7611d89`) — reports in `step-6-evidence/reviews/`

| Critic | Verdict | Blocking findings |
|---|---|---|
| Blind A/B vs ESPN (`r1-blind-ab.md`) | **WIN** for this app (X = ours by coin flip) | none; ESPN is denser and more legible per row |
| UX (`r1-ux.md`) | FAIL | U1 Critical, U2 to U4 Structural |
| Visual and anti-slop (`r1-visual.md`) | FAIL | V1, V2 Critical, V3, V4 Structural |
| Implementation (`r1-implementation.md`) | FAIL | F1 to F3 High |

The three agree on: an unreadable "next kickoff" note (my L4 only checked "not lime"), week arrows that render as faint 36px glyphs, and the Yahoo sheet link and data age pushed into an unmarked sideways scroll. F1 was confirmed in the code: a direct send never clears that game's older queued pick, so a later flush can put the old pick back.

Mapped to failing tests before any fix (`red-r1-findings.log`, **8 failed, 17 passed**): P11 (older queued pick must go), P12 (a refused queued pick is reported, kept and retried), L4 strengthened (same ink as the date), L8 at 393 and 320 (44px bordered arrows), L9 at 393 and 320 (Yahoo sheet and "Updated" on the first screen), L10 (last tab clear of the fade). Work order 3 (`wo-3.md`) also carries F4 to F8, V4, U9 and F10 as reviewed requirements.

Deferred, Visual or Polish, none blocks the step: V5 (uncertainty and upset chips on every seeded card: seed data, not layout), V6 and U11 (label wording, pinned by step 4 tests), V7 (tab pill over a lime header), V8 (game page first screen, not changed in this step), V9, V10, U5 to U8, U10, U12, U13, F9, F11. Listed for the dashboard step with the step 4 items.

### Work order 3, try 1 (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-3.md`

Model pick: Jev `model:pwa:wo-3` → sol 0.98, effort high 0.89 (follow). Diff inspected: 10 files, all in the allowed scope, 55 lines added and 40 removed.

Gate `gate.sh wo3` (logs `wo3-*.log`): pytest **99 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **72 passed, 0 failed** (the 8 red tests green, nothing else broken). After screenshots retaken (`shots/after-*.png`): Yahoo sheet, the data's age and 44px week arrows are on the first screen at 393, and the first card with its pick buttons still ends above the tab bar.

Committed as `d0d7b9e`.

### Review round 2 (fresh critics on `d0d7b9e`) — reports in `step-6-evidence/reviews/`

| Critic | Verdict | Blocking findings |
|---|---|---|
| Design, UX and visual in one (`r2-design.md`) | **PASS** | none; no Critical or Structural finding (Design Gauntlet stop rule met) |
| Implementation (`r2-implementation.md`) | FAIL | N1 High, N2 and N3 Medium, all in the pick queue |

The implementation reviewer confirmed F1 to F7 fixed and found what remains of F1: a flush that finishes can delete a newer pick queued for the same game while it was in flight (N1); a tap and a flush can have two requests for one game in flight, so the older can land last (N2); one game that keeps returning 500 blocks every other queued pick (N3). The design critic's C1 is a false statement about the data (the phone says the model has "No live picks" while every card shows one), so it is fixed now despite its Visual grade.

Mapped to failing tests before any fix (`red-r2-findings.log`, **4 failed, 25 passed**, commit `dd66d0e`): P13 (N1), P14 (N2), P15 (N3), L11 (C1). Work order 4: `wo-4.md` (`55bed45`).

Deferred, Low, Visual or Polish, none blocks the step: N4 (a second, different failure on the same queued game is not announced again), N5 and C6 (the update toast has no "Later"), N6 and C2 (the fade is 15% of the row, not a fixed width), N7 (section tabs and the points clear button are 40px), C3 and C4 (320-wide footer and first screen), C5, C7 to C9. Listed for the dashboard step with the round 1 items.

### Work order 4, try 1 (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-4.md`

Model pick: Jev `model:pwa:wo-4` → sol 1.0, effort high 1.0 (follow). Diff inspected: 3 files, all in the allowed scope (`sync.ts`, `queries.ts`, `kpi-strip.tsx`), 35 lines added and 13 removed. Saves for one game now go through one chain (`orderedPickSend`) from both the tap and the flush; a flush removes a queued pick only if it is still the value it sent; a non-network error moves on to the next game.

First gate run: 75 passed, P13 failed. The failure was in my test, not the build: it waited for the moment the older pick was on the server, which the fix makes too short to see, and it looked for the selected button under its unselected name. P13 now checks the end state (server, queue and button all on the newer pick, and still so 3 s later). Shown still red on the old queue code (`Expected "LV", Received "MIA"`) before I accepted it.

Gate `gate.sh wo4` (logs `wo4-*.log`): pytest **99 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **76 passed, 0 failed**. Committed as `cfbef46`.

### Review round 3 (fresh reviewer on `cfbef46`) — `reviews/r3-implementation.md`

N1, N2 and N3 confirmed fixed. Verdict FAIL on one Medium: the direct send removed the game from the queue before the request, so the pick lived only in memory during the request; if iOS closed the app then, it was lost with no message (F1). Mapped to a failing test first: P16 reloads the page mid-request and expects the pick on the phone during the request and on the server after the next open (`red-r3-findings.log`, **1 failed, 16 passed**, commit `b8890c4`). Low findings F3 to F5 deferred with the others.

### Work order 5, try 1 (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-5.md`

Model pick: Jev `model:pwa:wo-5` → sol 0.98; effort split 54/46 (confidence 0.08, route advisor); the Sonnet advisor chose high. Diff inspected: 2 files, both in scope, 8 lines added and 7 removed. A tap is written to the queue before it is sent and removed only if it is still the value sent.

Gate `gate.sh wo5` (logs `wo5-*.log`): pytest **99 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **77 passed, 0 failed**. Committed as `a12dc55`. After screenshots retaken.

## 4. CLEANUP

A separate, scope-locked refactor pass after the last review fix, by a fresh read-only subagent over the production code this step touched (`git diff 9d41cb0..cfbef46 -- apps/web packages/shared scripts`, tests excluded): `reviews/cleanup-pass.md`.

| Item | Decision | Reason |
|---|---|---|
| R1: `gameId in queue` before `queue[gameId] !== team`, three places in `sync.ts` | **Changed** (work order 5, part B) | A missing key reads as `undefined`, which never equals a `string \| null` team. No behaviour change. |
| "Changed:" strip written in `game-card.tsx` and `recommendation.tsx` | No change | Two one-line uses; sharing it needs a new export. |
| Phone and desktop subtitle spans in `week-board.tsx` | No change | The two texts differ on purpose; same pattern as `kpi-strip.tsx`. |
| Literal `12px` in `scroll-padding-top` | No change | No token means "gap below the header"; the line above uses a bare `84px`. |
| `sw.js`, `stamp-sw.mjs`, `persist.ts`, update flow in `pwa.tsx` | No change | No dead code, debug output or false comments; the removed API cache and `replay` helper have no references left. |

Proof after the edit: the `wo5` gate above ran on the tree that contains R1 (77 browser tests passed).

Work order 6 below came after this pass. It changed 9 lines in `useSetPick` and added one four-line export; I read the diff and saw nothing to simplify; the VERIFICATION reviewers read it fresh.

## 3b. IMPLEMENTATION, continued after the cleanup pass (review round 4)

### Rebase on main `3d87fa0`

Step 12 landed on main while this step was in review, so god asked for a rebase before verification and released the integration lock for it once. 17 lane commits replayed with no conflict. **Every commit id above this heading is from before the rebase**; `step-6-evidence/pre-rebase-commits.txt` lists them with their subjects, which are unchanged. `lane-guard.py check … pwa 3d87fa0`: `OK`.

First gate on the rebased branch (`rebased-*.log`): pytest **115 passed** (main added 16) · ruff clean · gen:api no drift · typecheck 0 · e2e **void**: the Mac went to sleep during the run (the power log shows a wake from deep idle at 18:15; three tests took 6 to 17 minutes against a 30 s limit). Browser runs since then use `caffeinate -i`.

### Review round 4 (fresh reviewer on the queue code after work order 5) — `reviews/r4-implementation.md`

Verdict FAIL on one Medium, R1: a tap was written to the queue only when its turn to send came. A second tap made while the first was in flight was in memory only, and lost with no message if iOS closed the app. Mapped to a failing test first: P17 (two taps, the first held; within 1 s the queue and the button must show the second; the page is reloaded mid-request; the next open must send the second). `red-r4-findings.log`: P17 red at the intended check. Four other tests in that run timed out with the machine's load average at 18 to 26; all four pass in the `wo6` gate below.

Low findings deferred with the others: R3 ("Waiting to sync" shows briefly on every online tap, which is true but new), R4 (same as F3), R5 (a 404 in the flush is worded as "locked at kickoff"), R6.

### Work order 6, try 1 (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-6.md`

Model pick: Jev `model:pwa:wo-6` → sol 0.98, effort high 1.0 (follow). Diff inspected: 2 files, both in scope, 6 lines added and 3 removed. The choice is queued as the first statement of `onMutate`; a send whose value a newer tap has replaced is skipped. Ryan read the installed TanStack Query source: `onMutate` runs before a mutation waits on its `scope`; P17 proves it in the browser.

Gate `gate.sh wo6` under `caffeinate -i` (logs `wo6-*.log`): pytest **115 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **78 passed, 0 failed** (2.6 min). Committed as `9aa5990`.

Work orders in this step: six, seven tries in all (work order 1 took two; no other used its second try). No climb above gpt-6-sol.

## 5. VERIFICATION

Each result is recorded separately with its log. Commit ids in this section are the current ones (after the move onto main `3d87fa0`).

### Review round 5, my own fresh reviewer (on `9aa5990`) — `reviews/r5-implementation.md`

PASS: no Critical, High or Medium finding in the pick queue; five Low, deferred. It read the installed TanStack Query source and confirmed a tap is queued at tap time.

### Coordinator gate, twice in a row, on `aaa2d63` (logs `wo6-*.log`, `final-*.log`)

Both runs: pytest **115 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **78 passed, 0 failed**. `lane-guard.py check … pwa 3d87fa0`: `OK`.

### Security review, Dwight (on `efd3625`) — `reviews/security-dwight.md`

**PASS.** No Critical, no High. Checked clean: the worker never caches or answers `/api/` or anything carrying the token; cross-origin caching is limited to images; the update flow cannot loop; the build id is validated before it is stamped; no secret in the diff; error text is rendered as plain text. Seven Medium (D1 to D7) and eight Low (D8 to D15) about picks lost or mislabelled in rare cases; he left the timing to me and god.

### Review and fresh-critic gate, Angela, first critic (on `893acb9`) — `reviews/critic-angela-1.md`

**FAIL.** Her gate (`critic-angela-*.log`, `critic-angela-run2-*.log`): run 1 e2e 77 passed, **1 failed** (U3, the Yahoo rank form); run 2 e2e 78 passed, 0 failed; pytest 115, ruff, gen:api and typecheck clean both times. All 31 step 6 tests passed in both runs. Checkpoints PLANNING through CLEANUP: PASS. Tests weakened: no. Deferred list: none must block.

| Blocking finding | What | Outcome |
|---|---|---|
| A1 (High) | The rank form's effect wipes what he typed when the scorecard arrives, so U3 fails now and then. Older than this step, but in the lane's files and it makes the gate red. | Red test U3b, fixed in work order 7 **Correction:** U3 had a second cause, found by the third critic and fixed in work order 9 (below). |
| B1 (Medium), same as Dwight D2 | A failed storage write leaves a waiting pick in memory only, shown as waiting, lost on reload. | Red test P19, fixed in work order 7 |
| B2 (Medium), same as Dwight D8 | Two open copies of the app overwrite each other's waiting picks. | Red test P20, fixed in work order 7 |
| A2 | No VERIFICATION section. | This section |
| A3 | The proof that the rewritten P13 still fails on the old code was not saved. | Accepted. I ran it and quoted the result in the work order 4 notes, but kept no log. Red proofs since then are saved (`red-r3-`, `red-r4-`, `red-verification-findings.log`). |

God upheld all three blockers (hive message `2026-10-12T22-51-59-523Z-f655b2`).

Also taken now: Dwight D1 and Angela C5 (a damaged stored queue crashes the app on every load; red test P18) and Angela T1 (a test for a waiting pick the server refuses as locked; P21, green on the code as it was).

Red run before the fix (`red-verification-findings.log`): **5 failed** (P18 for `null` and `7`, P19, P20, U3b), **30 passed**. P20 hit the 30 s limit in that log; rerun alone with a 90 s limit it failed at "both picks are still waiting" (the first copy's pick was missing from storage).

### Work order 7, try 1 (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-7.md`

Model pick: Jev `model:pwa:wo-7` → sol 0.98, effort high 0.98 (follow). Diff inspected: 4 files, all in the allowed scope (`sync.ts`, `fmt.ts`, `queries.ts`, `scorecard.tsx`), 53 lines added and 21 removed. A stored queue that is not a plain object reads as empty; a queue write reports failure and a pick left waiting that could not be stored says "Could not save this pick on the phone. Keep the app open until it syncs."; every queue change starts from storage and the `storage` event refreshes the other copy; the rank form keeps typed input.

Gate `gate.sh wo7` and again `gate.sh final2` on the commit `3f5f6ff` (logs `wo7-*.log`, `final2-*.log`), both under `caffeinate -i`: pytest **115 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **87 passed, 0 failed**, both times. `lane-guard.py check … pwa 3d87fa0`: `OK`.

Work orders in this step: seven, eight tries in all.

### Not fixed in this step (for the integrator to schedule)

None of these was judged blocking by Dwight, Angela or the five fresh reviewers. Angela: T2 (test for a 401 during a flush), T3 (sign-out test; the queue is not cleared on sign-out), T4 (two games offline), T5 and T6 (fixed sleeps and 30 s holds in my tests), C1 (no timeout on the worker's page fetch: watch in the owner's iPhone check), C2 (opaque image cache cap), C3 (cache version is a constant), C4, C6 to C8. Dwight: D3 (a non-JSON 200 counts as saved), D4 (a 401 during a flush does not sign out and retries every 15 s), D5 (404 and 422 worded as "locked at kickoff"), D6 (queue kept across sign-out), D7 (a "not saved" toast can be pushed out by a newer one), D9 to D15. Earlier rounds: listed under each round above.

### Re-review, Dwight (on `f2c9af8`) — `reviews/security-dwight-2.md`

**PASS for security**, no Critical or High. One Medium he asked to be fixed before landing, R1: while the phone keeps refusing to store the queue, the in-memory copy was laid over the stored copy, and a merge cannot record a removal. An older stored pick for a game could come back after the newer one was sent, and the next flush sent it over the newer one. Five Low (R2 to R6), listed below as not fixed.

### Second fresh critic, Angela (on `f2c9af8`) — `reviews/critic-angela-2.md`

**PASS.** Her own gate, twice (logs `critic2-angela-a-*.log`, `critic2-angela-b-*.log`): pytest 115 passed · ruff clean · gen:api no drift · typecheck 0 · e2e 87 passed, 0 failed, 2 skipped (the 2 skips are `shots.spec.ts`, screenshots only). Lane guard OK. All criteria and all checkpoints through VERIFICATION pass; no test weakened. She found the same bug as Dwight's R1 (her F1) and rated it advisory. Security review decides (owner's rule 4), so it is fixed in this step. Her note: the e2e counts above leave out "2 skipped"; that is true of every count in this log.

### Work order 8, two tries (Ryan, Codex gpt-6-sol, effort high) — `step-6-evidence/wo-8.md`

Red test P22 first, commit `f5862f1` (`red-r1-dwight.log`): **1 failed**, at "the older stored pick was not sent over the newer one" (expected `LV`, received `MIA`); P19 and P20 passed in the same run.

Model pick: Jev `model:pwa:wo-8` → sol 1.0, effort high 1.0 (follow). Try 1: one line in `apps/web/lib/sync.ts` (`currentQueue()` returns the in-memory queue when one exists, otherwise storage). Gate `wo8` green (88 passed), but reading the diff I found `unqueue` then edited that object in place, against the work order's immutable-updates constraint, so the screen might not refresh. No failing test for that; it is a code-reading finding. Try 2: `unqueue` copies before removing. Final diff: 2 lines changed, one file, in scope. Commit `9670cdf`.

Gate on `9670cdf`, twice in a row under `caffeinate -i` (logs `wo8b-*.log`, `final3-*.log`): pytest **115 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **88 passed, 0 failed, 2 skipped**, both times. `lane-guard.py check … pwa 3d87fa0`: `OK`.

Work orders in this step: eight, ten tries in all (work orders 1 and 8 used two).

Not fixed from these two reviews (Low unless marked; for the integrator to schedule): Dwight R2 to R6; Angela F6 (**Medium**: "showing data from" is the time of the last good reply of any kind, not the age of what is on screen; closest to the never-invent-data rule, schedule early), F2 to F5, F7, F8, S4.

### Dwight's confirmation of R1 (on `9670cdf`, HEAD `3de3036`) — `reviews/security-dwight-3.md`

**PASS for landing on security.** No Critical, no High. R1 closed within one app session. Read-only; he ran no tests. New, not blocking: R7 (Medium, older than this fix: the same wrong-pick outcome survives an app restart if storage refused every write until the app closed) and R8 (Low: P22 does not assert that a write was refused).

### Third fresh critic, Angela (on `3de3036`) — `reviews/critic-angela-3.md`

**FAIL.** Her gate run a: e2e 88 passed, 0 failed, 2 skipped. Run b: **87 passed, 1 failed** (U3, `sheet.spec.ts:151`), 2 skipped (logs `critic3-angela-a-*.log`, `critic3-angela-b-*.log`). A gate must be green twice. She confirms the work order 8 fix is correct, P22 fails on the old code, and no test was weakened.

Blocking, F-1 (High): if he saves his rank while the page's first scorecard request is still in flight, `invalidateQueries` reuses that request, so "Rank saved" appears beside the scorecard from before the save. A second cause of the U3 flake; the first (typed input wiped) was fixed in work order 7. Advisory: F-2 and F-3 (Low, queue with refused writes; F-3 is Dwight's R7), F-4 (this log said A1 was fixed; corrected above).

### Work order 9, try 1 (Ryan, Codex gpt-6-sol, effort medium) — `step-6-evidence/wo-9.md`

Red test U3c first, commit `5ea3b2f` (`red-critic3.log`): **1 failed**, at "the scorecard shows what was just saved, not the answer from before the save" (expected "Leader 55 points", the row showed "Leader 61 points"); U3 and U3b passed in the same run. The test holds the first scorecard answer until the save has returned, so it does not depend on timing.

Model pick: Jev `model:pwa:wo-9` → sol 0.98, effort medium 0.92 (follow). Diff inspected: one line in `apps/web/components/performance/scorecard.tsx`, in scope (`await qc.cancelQueries(...)` before `invalidateQueries`). Commit `7a90207`.

Gate on `7a90207`, twice in a row under `caffeinate -i` (logs `wo9-*.log`, `final4-*.log`): pytest **115 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **89 passed, 0 failed, 2 skipped**, both times. `lane-guard.py check … pwa 3d87fa0`: `OK`.

Work orders in this step: nine, eleven tries in all (work orders 1 and 8 used two).

Added to the not-fixed list for the integrator: Dwight R7 (**Medium**, same as Angela F-3; his fix sketch: on a refused write, remove the key and write once more; add a reload step to P22), R8; Angela F-2.

### Pending, not PASS

* A new fresh critic on the commit that adds this text: the result is appended below when it arrives. Dwight is not asked again: the only code change since his PASS is the one line in `scorecard.tsx`, which touches no auth, input handling, storage or request path.
* The owner's check on his iPhone (Add to Home Screen, open offline, update prompt, a pick with Tailscale off): **PENDING**. It needs the live app rebuilt from this branch, which god does after landing. Angela asks him to watch app launch with Tailscale off (C1).
