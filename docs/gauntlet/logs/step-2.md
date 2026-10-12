# Step 2 of 8 — Desktop web app (T2)

Session started 2026-10-12 in the cloud sandbox (`/home/user/NFL-Pickem-App`), coordinator on Opus 5.5. `DIRECT_COORDINATOR / ONE_SHOT`, from the step 2 handoff in STATE.md `## 0` (owner request 2026-10-11: finish the remaining steps in the cloud).
Evidence and review reports: `docs/gauntlet/logs/step-2-evidence/` (in the repo, because this container is wiped when the session ends).

## What this step builds, in plain words

* **Builds:** the desktop app you open each week, checked by a robot that clicks through it: sign in, sort, pick and clear, a game locking at kickoff while you watch, every matchup section, Results, CSV in and out, Backtest, Settings. Results stops mixing after-the-fact predictions into the model's headline. A game with no kickoff time says "Time TBD" instead of midnight. A weather outage stops shouting. The look moves to the agreed design system (Geist type, stronger control borders, unboxed sections, real icons).
* **Replaces:** the pre-built web screens' unverified state, the blue probability bar, the five KPI cards, boxed Matchup sections.
* **Is not:** phone layouts, the floating tab bar, offline polish (step 4), deploy (step 3), alerts UI (step 5).

## 1. PLANNING

* Step, base, branch: PLAN.md roadmap row 2. Branch `claude/nfl-pickem-intelligence`, draft PR #1, HEAD at start `94d389d` (CI green, 6/6 checks, mergeable clean).
* Baseline (ran 2026-10-12): `uv run pytest -q` 48 passed · `uvx ruff check nflpi tests migrations` clean · `npm run gen:api` no drift · `npm run typecheck` exit 0 · `npm run web:build` exit 0 (8 static routes). Postgres 17 container `nflpi-db` restarted (`dockerd`, image cached).
* Environment: Codex not installed, so `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit: Codex not installed)`; builders are general-purpose subagents on the matching rung. Jev unavailable (no `jev.sh`, no `OPENROUTER_API_KEY`): routing decided by the coordinator, recorded `JEV: unavailable`. `/graft`, `/tdd`, `/ponytail`, `/refactor`, `harness-engineering`, `ecc:*` agents: not installed; behavioral equivalents applied and named below. Playwright 1.56.1 matches the preinstalled Chromium 1194.
* Prior decisions read: PLAN.md § Owner decisions, STATE.md § User constraints, CLAUDE.md § Decisions, step-1 log § carried items, PRODUCT.md, design.md.
* Skills: repository discovery by targeted `grep` and file reads (graft equivalent): pinned `api/views.py` `performance`/`is_locked`, `ingestion/service.py` `ingest_weather`, `predictions/engine.py` `backfill_season`, `components/pick-buttons.tsx`, `components/week/week-board.tsx`, `components/freshness.tsx`, `components/performance/performance-view.tsx`. TDD: no project `tdd` skill; `/tdd` rules applied (red first, one slice at a time). `harness-engineering`: N/A beyond PLAN.md § Harness, except one new feedback surface (the e2e CI job, below). Design Gauntlet: design.md and PRODUCT.md are the source of truth.

### Product Mode (T2)

1. **Problem:** Emmanuel's weekly desktop review runs on screens nobody has verified; they mix after-the-fact predictions into the model's record, show a TBD game at midnight, keep a pick button live past kickoff until the next fetch, and put a weather outage in a full-width warning.
2. **Why now:** week 6 starts Thursday 2026-10-15 (SEA @ DEN); the desktop board is where he makes 14–16 picks before then.
3. **Scope:** PLAN row 2 (C3, C4, B3, B9, verify and fix every desktop screen) plus the carried A7 follow-ups (`time_tbd` in the API and UI; weather ingest and backfill skip TBD/postponed games) plus the design tokens and the desktop findings of design.md § 15. **Cut:** phone-only design items (a card per game on the phone, the floating tab bar, 48px phone pills) → step 4; the pick radiogroup keyboard pattern (design.md § 12) → step 4 with the phone pills; the ESPN visual verdict → PENDING (no screenshots yet); a server clock override (not needed, see assumptions).
4. **Success metric:** the e2e gate below, 12/12 (baseline 4/12), and axe 0 serious/critical on six screens in both themes (baseline: issues on five screens). Product number: Emmanuel's live season accuracy on Results, now kept apart from backfill.
5. **Reversibility:** two-way for the UI. The API changes are additive (`time_tbd`, `model_backfill`, `weeks[].model_backfill_total`) except that `model` now counts live predictions only: a contract meaning change, approved by PLAN row 2 (B9), single user, the web app is the only client.

Assumptions:
* Ties: `views.winner` returns no winner for a tie, so ties are left out of every accuracy count (validated in code). The Yahoo tie rule is an open owner question; it does not change this step's design.
* "Fixed test clock": the seed puts games at times relative to the server's real clock; the browser clock is installed at the server's time and moved forward to a kickoff. The server's own lock is already covered by pytest (A3, A7). So no server clock override is built (validated: E4 is red today for the right reason).
* Phone-only findings belong to step 4 (assumed from PLAN row 4's scope).
* `geist` npm package is the font source (decided in design.md § 4; reason: the PWA renders offline).

Instrumentation: Results shows live and backfilled model records apart (`tally-model-live`, `tally-model-backfill`); the e2e job runs on every push. Read by: the owner on Results after week 6 (check 2026-10-20); guardrail: CI e2e green.

Open owner questions (not blocking; current behavior kept): Yahoo tie rule; a "submitted in Yahoo" mark per pick; ESPN reference screenshots.

## 2. SPECIFICATION — frozen acceptance criteria

Functional, backend (pytest, real Postgres, `backend/tests/test_web_contract.py`):

| ID | Finding | Criterion |
|---|---|---|
| W1 | A7 carry | `time_tbd` is a field of every game in `/api/weeks/{s}/{w}` and `/api/games/{id}`: true for a game with no clock time, false otherwise |
| W2 | A7 carry | Weather ingest asks for no forecast for a TBD game. Backfill writes no prediction for a TBD or postponed game; a started game still gets one |
| W3 | B9 | `/api/performance/{season}`: `model` counts live predictions only; `model_backfill` counts backfilled ones; `weeks[].model_backfill_total` sums to `model_backfill.total` |

User-facing (Playwright on the production export served by FastAPI, seeded by `backend/tests/e2e_seed.py`, `timezoneId: America/New_York`, 1440×900, `apps/web/e2e/step2.spec.ts`):

| ID | Finding | Criterion |
|---|---|---|
| E1 | verify | A wrong token shows "Wrong token"; the right one opens "Week N" of the current week |
| E2 | verify | "Most confident" sort orders the games by pick probability and survives a reload |
| E3 | verify | One tap saves a pick to the server; reload keeps it; a second tap clears it on the server |
| E4 | B3 | With the browser clock at server time, moving it past a game's kickoff disables both pick buttons within 5 s, no reload |
| E5 | verify, C3 | Every Matchup section renders (factors, teams, injuries, conditions, market, ai, ask, history, meetings); kickoff shows in Eastern time on the board and the matchup |
| E6 | A7 carry | A TBD game shows "Time TBD" on the board row and the matchup, and never "12:00 AM" |
| E7 | B9 | Results: `tally-model-live` says "No graded live picks yet" when no live prediction is graded; `tally-model-backfill` shows the backfilled record "c of n correct" |
| E8 | verify | CSV import of a past pick says "Imported 1 pick"; "Download CSV" returns it; Results `tally-me` counts it |
| E9 | C4 | A weather outage puts no "Stale data" banner on the board; Settings' freshness section says weather is not a model input |
| E10 | design § 4 | The body font is Geist and the Geist face is loaded |
| E11 | a11y | axe: 0 serious or critical violations on sign-in, Week, Matchup, Results, Backtest, Settings, in dark and light |

Design (grep gates + a fresh design critic):

| ID | Criterion |
|---|---|
| D1 | Proposed tokens landed in `apps/web/app/globals.css`: `--border-strong` (dark `#64707f`, light `#818b95`), light `--series-model #c9501c` and `--series-market #168a61`, motion tokens (120/200/320ms, `cubic-bezier(0.32, 0.72, 0, 1)`), type scale, Geist via the `geist` package. `docs/design/design-tokens.json` marks those groups `landed` |
| D2 | design.md § 15 desktop findings fixed: KPI strip unboxed (no row of equal cards); Matchup sections unboxed; probability bar fill `text-2`; `components/icons.tsx` SVGs replace typed ✓ ✗ and chevrons; inputs, selects and unselected pick buttons use `border-strong`; no Inter in the font stack; skeleton on the ease-out curve; weather banner gone (E9). Gate: `grep -rnE '"Inter"|Inter,|&#10003;|&#10007;|✓|✗|‹|›|ease-in-out' apps/web/app apps/web/components` finds nothing |
| D3 | Fresh design critic (no build transcript) on 1440×900 screenshots of every screen, both themes, against design.md: PASS. ESPN blind comparison: PENDING until the owner's screenshots arrive |

Operational:

| ID | Criterion |
|---|---|
| O1 | CI runs the e2e gate on every push (new `e2e` job: Postgres service, `npm run e2e`) and it is green, with the existing backend, web and docker jobs |
| O2 | `uv run pytest -q` and `uvx ruff check nflpi tests migrations` green; `npm run gen:api` no drift; `npm run typecheck`; `npm run web:build` |

First failing evidence (ran 2026-10-12, before any production change):
* pytest `tests/test_web_contract.py`: 4 failed for the intended reasons (`KeyError: 'time_tbd'`; weather asked for the TBD kickoff; backfill wrote `2023_04_MIA_BUF` (TBD); `KeyError: 'model_backfill'`).
* Playwright: 4 passed (E1, E2, E3, E5), 8 failed for the intended reasons: E4 buttons stay enabled past kickoff; E6 `time_tbd` undefined; E7 `model.total` 9 (backfill mixed in); E8 no `tally-me`; E9 one "Stale data" banner; E10 font stack starts `ui-sans-serif`; E11 dark week `color-contrast` (subtle on warn banner 4.49), matchup chip contrast 4.29 + `definition-list`, settings `label` (`#csv-file`, critical), light theme `color-contrast` on `text-warn` (4.37) across screens.

## 3. IMPLEMENTATION

`IMPLEMENTATION_PROVIDER: CLAUDE (limit hit: Codex not installed)` · `CODEX_POLICY: CODEX_FIRST` · `JEV: unavailable` (rungs picked by the coordinator) · `CLIMBS: none`. `/ponytail` rules (smallest diff, no speculative abstraction, no unrelated change) written into every work order.

| WO | Scope | Rung | Commit | Proof rerun by the coordinator |
|---|---|---|---|---|
| A | W1-W3: `time_tbd` in the contract, weather and backfill skip TBD/postponed, live-only `model` + `model_backfill` + `weeks[].model_backfill_total`, `gen:api` | sonnet, try 1 (general-purpose subagent, main checkout, backend files only) | `d7548e6` | pytest 52 passed · ruff clean · `gen:api` regenerated only `openapi.json` + `api-types.ts` · typecheck exit 0 |

WO-A review: diff read in full (4 backend files, +17/-3, plus the two generated files). In scope; no test edited. Builder's note accepted, not a defect: `WeekSummary.season_model_accuracy` reads `perf.model`, so the Week board's season model figure is now live-only too, which is what PRODUCT.md principle 5 asks ("backfilled results are never mixed into the live headline").

### Owner input that arrived during the step (2026-10-12, pushed from the owner's Mac: `132ab57`, `465feb2`)

* Design references now exist, on the Mac only (third-party images, git-ignored; described in `docs/design/references/README.md`). This cloud session cannot open them, so D3's ESPN/Yahoo blind comparison stays PENDING here and can run on the Mac.
* Owner statement: "I only want to predict winners and scores based on history and keep a database of who I picked so we can learn and get better over time." His Yahoo league uses confidence points and score tiebreakers (references 03, 04). Not in PLAN.md: a confidence rank per game and a predicted score per team. Open owner questions recorded in the README (does the league still run this way; does "only" cut AI, alerts, weather; does "based on history" drop the betting line). Step 2's frozen gate is unchanged by them: it verifies the screens he already uses. Proposed handling: a new roadmap step after step 2 for the Yahoo fill-in (confidence rank + predicted scores, scores checked walk-forward), once the owner confirms.
| C | D1, D2, E9, E10, a11y fixes: tokens (border-strong, light series, motion, type scale), Geist via `next/font/local` from the `geist` package, unboxed KPI strip and Sections, ink probability bar, `icons.tsx`, border-strong controls, ease-out skeleton, weather banner → Settings note, bezel on the pick panel and sign-in, light good/warn/bad darkened to clear 4.5:1 on `elevated` (design.md § 5 + tokens json updated) | opus, try 1 (isolated worktree, cherry-picked) | `d9fbede` | typecheck exit 0 · grep gate empty · e2e 6 passed (E1 E2 E3 E5 E9 E10); E11 blocked only by the missing `tally-me` testid (WO-B's); builder's own axe run with the Results wait swapped: 0 violations on all six screens, both themes |

WO-C review: 28 files, +495/-268, all in `apps/web`, design docs and the lockfile; no test or backend file touched. Carried for CLEANUP: `app/fonts.ts` points at `../../../node_modules/geist/...` (works because npm hoists to the root; check the package's own `geist/font/sans` export). Carried, not this step: phone header overflows at 320px (step 4); the spinner uses `linear` (design.md § 10; not a frozen criterion).

Spec fault found while re-running WO-C's proof (the coordinator's, not a builder's, so no rung climb): `e2e_seed.py` copied the first week-4 row of 2018, so the TBD game was stored under season 2018 and E6 could never pass. Fixed in `187b938` (copy a current-season row); verified in the e2e DB: `2023_04_BUF_MIA | time_tbd t`.
| B | E4, E6, E7, E8, E11: `lib/clock.ts` (`useNow` on one shared 15 s ticker, corrected by `meta.server_time − dataUpdatedAt`; `isLocked` = the API's `locked` or a known kickoff passed, same rule as `views.is_locked`) used by pick buttons, game row, matchup header and pick panel, the "Open to pick" filter and the KPI open count; `kickoffClock`/`kickoffWhen` show "Time TBD"; Results as one unboxed strip (me, model live, market, home) with the backfilled record in its own block and "incl. N backfilled" in the weekly table | sonnet, try 1 (main checkout) | `d39e941` | `npm run e2e` **12 passed** · typecheck exit 0 · grep gate empty |

WO-B review: 10 files under `apps/web` (+110/-65 plus the new `lib/clock.ts`); no spec, config or backend file touched. Carried, not fixed (traced, not worth code now): a TBD game's date is formatted in the viewer's zone, so a viewer west of Eastern would see the day before (the placeholder is midnight Eastern); the owner's commits are in Eastern (-0400). On Results the market and home records count every final game while the live model record counts only live-graded games; the labels say so, and the pick-sheet step (owner D13 scorecard) redesigns this block.

## 4. CLEANUP

Scope-locked to code touched in this step; `/refactor` is not installed, its behavioral equivalent applied. Picked by the coordinator, built by a Sonnet subagent (rung 1), no behavior change:
* C1 `app/fonts.ts` (relative path into the hoisted root `node_modules`) deleted; `layout.tsx` uses the `geist` package's own `GeistSans`/`GeistMono` exports; `--font-sans`/`--font-mono` are `var(--font-geist-sans|mono)` + the design.md § 4 fallback stacks. Observed body font: `GeistSans, "GeistSans Fallback", ui-sans-serif, …`.
* C2 unused `Card` import removed from `components/game/game-view.tsx` (`tsc --noUnusedLocals`). The same check flags `charts/calibration.tsx`, which this step did not touch: left.
* Not changed, with reasons: `views.performance` still returns `model_live_games`/`model_backfill_games` (now equal to the two totals) because removing them is a contract change and W3 reads one; the Results denominators note (see WO-B) belongs to the pick-sheet step.
* Spec strengthened (coordinator, recorded): E10's second check was `document.fonts.check('16px "Geist"')`, which is true for any family nothing declares. It now requires a loaded `FontFace` whose family starts with "Geist".

Proof after cleanup (coordinator): `npm run e2e` 12 passed · typecheck exit 0.

## 5. VERIFICATION, round 1 — FAIL (2026-10-12)

On `a931ea9` (code) / `36b0445` (+ evidence logs only). Coordinator validation, all green: pytest 52 passed · ruff clean · scratch-DB `alembic upgrade head` + `alembic check` clean · `gen:api` no drift · typecheck exit 0 · `web:build` exit 0 · `npm run e2e` 12 passed (`step-2-evidence/coord-*.log`).

* **Fresh critic (Opus, general-purpose; `ecc:*` not installed): VERDICT FAIL.** Its own gate matched (pytest 52, ruff, alembic, gen:api, typecheck, e2e 12/12, grep). Mutation checks: W2 fails without either skip; E4 passes with a 6-hour tick (bound untested). Blocking: (1) backfill still plain "Model" in the Results weekly bars and calibration and in the Week board's "Model accuracy, week" (`views.py` per-week and week-summary counts mix kinds); (2) E4's "within 5 s" not met (15 s tick; measured 12.1 s) and not tested. Non-blocking: log table/SHAs broken; E9 has no positive check; doc drift after CLEANUP (fonts.ts named in design.md and tokens json); locked buttons not per § 8; placeholders `subtle` on `elevated`; § 15 phone-card status vs the owner's reference 07 (step 4 PLANNING).
* **Fresh design critic (Opus): DESIGN VERDICT FAIL.** Blocking: the same backfill leak (Week 3 KPI 67% from backfill); team logos fetched from ESPN (`TeamLogo` loads `logo_url`; PRODUCT.md bans logos) and 8px monogram text (§ 4 floor 11px); locked state not per § 8; Matchup display probability without a bar (§ 2); Results charts draw backfill solid and unlabeled (§ 13); purple `--series-stats` (§ 15) and light `--series-elo` 2.69:1. Many non-blocking polish items (Geist Mono unused, pills vs 8px radius, radiogroup keys, "Saved" toast, sticky header, hover tint, one-click Sign out, 6/10px spacing, `transition-colors`), carried to step 4 or the pick-sheet step.
* Root cause, in the coordinator's spec: E7 checked only the two headline cells, E4 jumped 48 h, and nothing checked logos, the type floor or chart colors. These are spec gaps, not builder failures: no rung climb.

Fix round, spec first (red, committed before any fix): W3b (weekly live/backfill split, live-only calibration + `calibration_backfill`), W4 (week summary model figures live-only) — pytest 2 failed for the intended reasons (`KeyError: 'model_live_total'`; week-1 summary `(3, 2, 0.667)` instead of `(0, 0, None)`). E4 tightened (kickoff − 1 s enabled; +5 s disabled; lock icon; row says "Locked"), E5 + pick-panel meter, E9b (banner shows for stale schedules; guard, green), E10b (no purple series; each series ≥ 3:1 on `surface`, both themes), E12 (no `img` in `main`, no image requests, no visible text under 11px on five screens). Red run: E4 still enabled after +5 s; E5 no meter in the panel; E10b light `--series-elo` 2.69:1; E12 monograms at 8px.

### Fix round (WO-D)

| WO | Scope | Rung | Commit | Proof rerun by the coordinator |
|---|---|---|---|---|
| D | W3b, W4, E4 bound, E5 meter, E10b, E12 + design fixes: weekly `model_live_*`/`model_backfill_correct`, live-only `calibration` + `calibration_backfill`, live-only week summary; hollow "Model, backfilled" bars and calibration points; KPI "No live picks graded"; monogram-only `TeamLogo` (no `img`, text only at ≥ 11px); locked buttons per § 8 (no outline, lock icon, 60% ink); `ProbBar` in the pick panel; series colors (stats `#d9ae2e`/`#957100`, light elo `#c93673`, light home `#727c87`); 2 s tick; log loss 3 decimals; placeholders `text-2`; freshness comment; doc drift | sonnet, try 1 (new job, spec gaps were the coordinator's) | `4b97dac` | pytest 54 passed · ruff clean · `gen:api` no drift after commit · typecheck exit 0 · grep gate empty · `npm run e2e` **15 passed** |

Review: 21 files (+250/-130), in scope. Backend diff read in full (`schemas.py`, `views.py`: the split keys on the final snapshot's `kind`, matching W3). Builder went one step past the list and made the weekly table's Model column live-only with a backfilled note, so the table agrees with its chart (accepted: it is the chart's data alternative). Carried: `public/sw.js` still has a cache rule for the ESPN logo host (dead now; step 4 owns the service worker).

## 5. VERIFICATION, round 2 (on `704a021`)

* **Fresh critic (Opus): VERDICT PASS.** Own gate: pytest 54, ruff, gen:api no drift, typecheck, e2e 15/15, grep empty, alembic clean. Mutations caught: W1–W4 (8 backend mutants), E4 with 7 s and 60 s ticks, E12 with an `<img>`. Largest weakness: a client mutation that puts backfill back into the Results chart, table and calibration and drops the row chip still passes 15/15, and the API still serves mixed fields (`weeks[].model_correct/model_total`, `model_first*`) nobody reads. Log defects (WO-A/WO-B SHAs; table split). O1 PENDING (never reached CI).
* **Fresh design critic (Opus): DESIGN VERDICT FAIL.** Confirmed fixed: backfill apart everywhere, no purple, no text under 11px, blue only for me/interactive, all § 15 items. Blocking: teams drawn as empty rings at board sizes (read as radio buttons); missing values as a bare "-" without a reason (§ 2.5); pick buttons are 8px-radius rectangles, not pills, and locked-mine icons shrink to 9px; final scores at 48px, above the 40px probability (§ 3, § 4). Non-blocking carried: Geist Mono unused, chart heights/grid/lines, two primary buttons, "Performance" vs "Results", history dot for backfill solid, header "Locked" chip in warn tone, weather reason "No forecast yet" during an outage, `backdrop-blur` on the section bar.

Owner decision during review (in chat, 2026-10-12): **team logos come back** (D38; PRODUCT.md, design.md § 5, PLAN.md, CLAUDE.md updated). The reference images are now in the repo (owner's `75a867c`); the blind ESPN/Yahoo comparison is at phone size (393×852), so it runs in step 4.

Round 3 spec (red before any fix): W5 (no API field mixes live and backfill: `model_first*`, `weeks[].model_correct/model_total` removed) — pytest 1 failed for the intended reason; E12 rewritten for D38 (logos only from the API's `logo_url`; type floor kept) — red, 0 logo requests; E13 (backfill labeled on week rows, Results table, weekly chart) — green guard against the critic's surviving mutant; E14 (no bare "-" as a missing value) — red, 2 on the board.

Frozen criteria added after the first table, for the record: W3b, W4, W5 (backend); E9b, E10b, E12, E13, E14 (browser). E4 and E5 tightened in round 1.
