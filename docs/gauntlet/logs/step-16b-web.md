# Step 16b (web) of 17: the Group screen

Session: owner's Mac, 2026-10-13, lane `groupweb` (worktree `.claude/worktrees/lane-groupweb`, branch `lane/groupweb`, base `main@6359c7f`). Coordinator: Claude (hive temp "Kelly"). coord task #22. Evidence folder: `docs/gauntlet/logs/step-16b-web-evidence/`.
**Every member name in this file, the seed, the spec, the screenshots and every log is made up.** The real files under `research/group-data/` were never opened.

## 1. PLANNING

* **In the owner's words (D56):** his Yahoo group's picks and confidence points come into the app from files he exports himself. The three server routes landed today (step 16b server, PR #16). This step is the screen on top of them: a new **Group** page where he (1) uploads one exported CSV file after confirming the season, (2) reads the standings of a week, (3) sees how the group split on each game of a week next to the app's own pick.
* **Replaces nothing. Is not:** a change to any existing page, the pick sheet, the game card or the model; group data as model input (never); a score from the spread (never: straight winners with confidence points only); a backend change.
* **Roadmap row:** PLAN.md row 16 (D56), web half of 16b. **Tier:** T2 (new user-facing behaviour; untrusted file input and untrusted text on screen). Reversibility: two-way (a new page, one nav entry, add-only client methods). Security review required: Dwight reviews the upload form and the rendering of member names.
* **Pre-flight:** Problem: the owner cannot see his group at all, and cannot get the exported files in. Why now: the server routes landed and nothing consumes them. Scope: one page, three sections; cut: charts, per-member pages, search, editing, deleting uploads, an AI summary, offline copy of group data. Success signal: he uploads his two exported files from his phone and reads the standings and a week's split (one user, no usage metric). Reversibility: two-way.
* **Decisions relied on:** D56; CLAUDE.md (never invent data, missing stays missing, no prediction logic in the client); `design.md` § 0 (reference 06: near-black, lime accent, condensed titles, card per game, floating pill tab bar), PRODUCT.md; lanes.md "Screen lane" grant; the route contract in `step-16b-server.md` § 6.
* **Assumptions:** `validated` the 3 routes and reply shapes (read from `api-types.ts`); `validated` client `call()` gives `AbortSignal.timeout(5000)` unless `init.signal` is set, so the upload passes its own longer signal and the other two reads use the default; `validated` **the app persists every successful React Query result into `localStorage` (`lib/persist.ts`, key `nflpi_cache`)**, so group replies must NOT go through React Query: the page uses its own small fetch hook in `lib/group.ts` (member names must never reach browser storage); `validated` the service worker skips `/api/`; `validated` `useWeek` already carries `sheet.app_pick` per game, so the app's pick is free (no new route); `assumed` the owner is one of the 32 members but the page cannot know which, so it does not highlight a row.
* **Interpretations:** where the confirm step lives: a panel in the page under the file chooser (not a modal), because a modal would trap focus on a phone for no gain. The season in the confirm step can be changed (a wrong year is the one thing the server cannot catch).
* **Skills:** `/jevgrep` N/A (all seams read directly: page patterns, client, persist). `tdd`: no project skill; the coordinator writes the failing browser spec first. `ponytail`: in every work order. Design Gauntlet: YES (user-facing screen), see § 1b. `harness-engineering`: N/A (no runner/evaluator).
* **Tools:** Codex probe: `codex exec -m gpt-6-luna` answered (Codex is back on this account), so Codex builds. Test database: container `nflpi-lane-group-db` on 127.0.0.1:15445, database `nflpi_groupweb_e2e`. The Bash sandbox blocks docker and `~/.claude/plans` writes, so those few commands ran unsandboxed.
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low/medium (Codex); VERIFICATION high.

### 1b. Design brief

```text
PRODUCT:          Group page of Pick'em Intel, for the one owner, mostly on an iPhone home-screen app.
USER GOAL:        get his exported group files in with no wrong-year accident, then read the standings and how the group picked.
REGISTER/PRESET:  product · design.md § 0 (reference 06, lime = me / interactive).
DESIGN DIRECTION: calm, exact, scannable; type and alignment before boxes; plain words.
EXISTING SYSTEM:  PageHead, Section, Card, Chip, Button, SelectField, EmptyState, ErrorState, Notice, Skeleton (components/ui.tsx); WeekPicker (pickers.tsx); useSelection (season/week in the URL); team abbreviations as text (no new logo fetches); pctOr/num (lib/fmt.ts). Reference screens: performance-view.tsx, sheet.
PROBLEMS:         (a) wrong year is invisible to the server; (b) 32 names must fit a 375px screen with four numbers; (c) names are untrusted text; (d) the app caches replies in localStorage.
SKILL WORKFLOW:   director = design.md + frontend-design-direction; critics (fresh general-purpose subagents, read-only): UX architect on the brief/spec before code; anti-slop + polish + implementation reviewer after build; security by Dwight. gstack browse/Playwright shots.
PROPOSED CHANGES: order: goal → IA → primary action → flow → hierarchy → layout → responsive. IA top to bottom: head (kicker "Your Yahoo pick'em group", title GROUP, week picker), Upload a file, Standings, How the group picked.
DESIGN.MD IMPACT: none (no new token or pattern); step log says so at LANDING.
BAR:              PRODUCT.md/design.md of this app plus the existing Results and Week pages at the same viewports (375x812, 1440x900; dark and light). No outside live product has a comparable group screen.
STATES:           loading (skeleton) · empty (no standings for week N yet; no group picks for this game yet; no games this week) · error (ErrorState with retry) · success · partial (some members without a pick: "x of y") · file chosen (confirm) · uploading (button loading) · upload result · upload error · hover/focus/disabled via existing Button.
```

## 2. SPECIFICATION (frozen)

Executable gate: `apps/web/e2e/group.spec.ts` (clauses below, one test each; it reads expected values from the API, seed in `backend/tests/e2e_seed.py`: four made-up members, picks for week 4, weekly points for weeks 1 to 3). Plus the scripted gates of the Design Gauntlet and the repo gate (§ 5).

**Page.** Route `/group/` (static export), query `?season=&week=` through `useSelection`. `<h1>` "Group" over kicker "Your Yahoo pick'em group". `WeekPicker` in the head. Nav: one "Group" entry in `DESKTOP_NAV` and `TABS` of `app-shell.tsx` (+ icon `People` appended to `icons.tsx`); links to `/group/<qs>`; `aria-current="page"` on it.
**Data.** `lib/group.ts` holds the helpers and one hook (`useGroupData`) built on plain `fetch` state, NOT React Query (privacy: `persist.ts` saves every query to `localStorage`). `packages/shared/src/client.ts` gets add-only methods `groupImport(season, file)`, `groupStandings(season, week)`, `groupShares(season, week)` (types from `api-types.ts`; upload sends the `File` itself as the body with its own 60 s signal, never `FormData`, never reads the file) and add-only `keys` entries. Member names: rendered as React text only, never `dangerouslySetInnerHTML`, never logged, never in browser storage.

| ID | Clause | Check |
|---|---|---|
| N1 | "Group" link in the primary nav on desktop and phone opens the page and is `aria-current` there | group.spec N1 |
| S1 | Standings table "Standings for week N": columns Rank, Member, Week, Total; rows in API order; rank null shown as en dash; text "Totals count weeks 1, 2, 3." from `weeks_counted` | S1 |
| S2 | Week with no rows: "No standings for week N yet", no table | S2 |
| S3 | A name with markup shows literally; no element created | S3 |
| P1 | Per game card: heading "AWAY at HOME"; per side row (`data-testid=side-<ABBR>`): "`picks` of `picked`", share % (en dash if null), "avg x.x pts" ("avg –" if null) | P1 |
| P2 | Each card shows "App pick: ABBR" (or en dash) taken from the already-loaded week data | P2 |
| P3 | Game nobody picked: "No group picks for this game yet", no side rows; season with no data: all cards say so + "No standings for week 1 yet"; no games: "No games this week" | P3 |
| X1 | The word "spread" never appears on the page | X1 |
| PV1 | After load + `pagehide`, no member name is in console output, `localStorage` or `sessionStorage` | PV1 |
| U1 | Choosing a picks file shows a confirm panel (file name, "The server cannot tell if the year is wrong", select "Season for this file" defaulting to the page's season); nothing is sent before "Upload file"; then ONE POST `/api/group/import?season=` with the raw bytes (not multipart); result "Picks file saved: N picks for the 2023 season."; the shares refresh | U1 |
| U2 | The season chosen in the confirm step is the season sent | U2 |
| U3 | Weekly file: "Weekly performance file saved: N member-weeks for the 2023 season."; standings show it | U3 |
| E1 | 422: the server's own message, verbatim, in an element with role alert; the confirm panel stays so it can be retried | E1 |
| E2 | 413: "That file is too large. The limit is 1 MB." 500: "The server could not save this file. Try again." A retry after a 500 can succeed | E2 |
| E3 | A file over 1,000,000 bytes is refused on the page with the 413 text, nothing sent, no Upload button | E3 |
| A1 | Axe finds no violation in dark and light: data, confirm step, error, standings | A1 |
| R1 | At 375x812 no horizontal scroll (standings, empty, confirm) and Upload/Choose another buttons >= 44px | R1 |

**Amendments from the UX architect critic (round 1, fresh sonnet subagent, before any code; 3 blockers accepted, spec changed, nothing built yet):**

| ID | Clause | Check |
|---|---|---|
| L1 | Standings and shares load and fail on their own; a failed one shows an ErrorState (role alert, "Could not load", Retry); the "No standings" text is never shown for an error; a skeleton shows while loading | L1 |
| L2 | A late reply for an earlier season/week never replaces the one now shown (cancel flag in the hook) | L2 |
| U1b | The confirm panel says "Saving to the {season} season" next to a season select whose options are `meta.seasons`; after a save into a season other than the one on screen the result carries a link "Show the {season} season"; a double tap sends once; a new file choice clears the old result and error; after a save the same file can be chosen again | U1, U2 |
| P3b | A week in which nobody picked anything shows ONE message "No group picks for week N yet" (hint: upload the picks file), not a wall of empty cards | P3 |
| R2 | 32 members and a 70-character name without spaces fit 375px with no sideways scroll, and the last row clears the tab bar | R2 |
| X1b | "spread" appears nowhere in the body text or markup, in the confirm step either | X1 |

**Amendments from the security review (Dwight, round 1: PASS, no critical; 4 medium taken):**

| ID | Clause | Check |
|---|---|---|
| E4 | A 401 on the upload or on a group read signs out like every other request ("Your token was rejected by the server. Sign in again.") | E4 (upload), E4b (read) |
| E5 | A 5xx other than 500 shows "Upload failed (HTTP nnn). Try again." whatever the body; server text is shown only for a 422 whose detail is a string; every other status or a list-form detail shows "The server could not read this file." | E5 |
| E6 | A timeout (60 s) says there was no answer, that the file may have been saved, and reloads the tables. **No browser check** (it needs a 60 s wait); carried gap | none |

Advisories carried, not built: collapsing the standings to a top ten; showing the detected file kind before saving (the server cannot tell without saving); per-member "x of 32" wording; explaining a null rank beyond the en dash; picks above standings on the page (the owner's order is kept: upload, standings, picks).

Out of the gate on purpose: Dwight's security review of the form and name rendering; design critics; repo gate (§ 5).

## 3. IMPLEMENTATION
* **RED (checkpoint SPECIFICATION):** spec and seed committed (`ba9b8c8`, amended `a8aef46` after the UX architect critic). Run against the base tree with the production files removed: `step-16b-web-evidence/red-e2e.log`: **21 failed**, every one at `getByRole('link'|'heading', { name: 'Group' })` not found = no Group page. Right reason. (A first red attempt failed at `next build` only because `node_modules` was empty in the fresh worktree; `npm ci`, rerun.)
* **Build ladder:** Codex was probed once (`gpt-6-luna` answered), so Codex built; no Claude subagent wrote code; the coordinator wrote only the spec, seed and logs.

| WO | What | Model, effort | Result |
|---|---|---|---|
| 1 | client methods, `lib/group.ts`, `People` icon, nav entries, empty page | gpt-6-luna, low, try 1 | built; typecheck green (re-run by me after `npm ci`) |
| 2 | the screen: upload panel, standings, group picks, page | gpt-6-sol, medium, try 1 | built; first spec run 18 of 21 green |
| 3 | spaces between the numbers of a side row (P1) | gpt-6-luna, low, try 1 | built |

Red-for-the-right-reason after WO-2 (`g1-e2e.log`): P1, U1, L1 failed. Not the builder: P1 text was glued ("MIA2 of 450%", fixed by WO-3), U1 asked Playwright to read a `File` body it cannot read (spec now checks `content-length` and that the server accepted the raw CSV), L1 used week 3 where nobody has picks (spec now expects the week-3 empty message). **Spec corrections after a red run are mine; recorded here.** Then `f1`: full `npm run e2e` **123 passed**, 0 failed (`f1-e2e.log`).
* **Privacy design found in PLANNING and enforced by PV1:** group replies never go through React Query (its cache is saved to `localStorage`).
* No existing page, component (other than the two granted lines in `app-shell.tsx` and the appended icon), spec or `design.md` was edited. Seam note carried to god: `apps/web/public/sw.js` `PRECACHE_PAGES` does not list `/group/` (the page still opens online; offline first open would need that line; lane web's file).

## 4. CLEANUP
Scope-locked `/refactor` read of the touched code after the build: `lib/group.ts` (66 lines), four components (27, 38, 60, 93 lines), nav and icon edits. **No change needed**: no duplicated block (the three load states are different per section), no dead export (every export of `lib/group.ts` is used), the `sending` ref beside the `loading` state is deliberate (a double tap in one tick must send once, clause U2), every value is a design token, no file near the size limit. Edits after the design critic and the security review are listed in § 5.

## 5. VERIFICATION
(pending)

## 6. LANDING
(pending)
