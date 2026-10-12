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
