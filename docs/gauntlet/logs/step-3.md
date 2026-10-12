# Step 3 of 14 — Restyle: reference 06 look and layout, owner logo (T2)

Session 2026-10-12, cloud sandbox, coordinator on Opus 5.5. `DIRECT_COORDINATOR / ONE_SHOT`. Owner said "Go build and complete it". Evidence: `docs/gauntlet/logs/step-3-evidence/`.

## What this step builds, in plain words
* **Builds:** the app looks like the owner's reference 06: near-black, lime, big condensed titles, a card per game with logos and "VS", split win-chance tiles, a floating pill tab bar on the phone, pill section tabs; his P logo as the app icon. Plus the seven items step 2's reviewers left (what changed, differs from model, the weather outage reason, backfill guards, CSV prediction kind, client-lock tests).
* **Is not:** the pick sheet (step 4), deploy (step 5), offline polish (step 6).

## 1. PLANNING
* Roadmap re-planned: PLAN.md now has 14 numbered steps folding owner decisions D1–D41 (this is step 3; old steps 3–8 moved to 5, 6, 7, 11, 13, 14).
* Base: `94a9eda` (step 2 landed, CI 8/8). Baseline: pytest 55, e2e 17, typecheck, build — all green at start (rerun below as part of the red run).
* Environment: Docker + Postgres restarted after a session restart; Codex not installed → `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit)`; Jev unavailable → `JEV: unavailable`; 21st.dev: themes/search free, 2 code retrievals a day.
* Skills: repo lookups by grep (graft equivalent); `/tdd` rules (red first); `/ponytail` rules in every work order; `harness-engineering` N/A (no new runner).

### Product Mode (T2)
1. **Problem:** the owner's chosen look (reference 06) and layout are not the app's; it still wears the blue system and a table board.
2. **Why now:** he asked for it ("the styling of the image is what I like the best"; "Go build and complete it"); the pick sheet (step 4) should be built once, in the new look.
3. **Scope:** D39 tokens and type, D40 layout, D41 icon, dark-variant team logos, R1–R7. **Cut:** pick sheet features, offline/push polish, any soccer elements, a theme switch (D37's "themes" stays the existing system light/dark).
4. **Success metric:** the gate below green; a fresh design critic picks ours as matching reference 06's structure with our information, blind side by side.
5. **Reversibility:** two-way (UI); CSV export gains one column (additive).

Assumptions: Barlow Condensed is an acceptable condensed display face for "LEAGUES"-style titles (assumed; reference face unknown) · `@fontsource/barlow-condensed` is a justified new dependency (offline PWA, design.md § 0) · ESPN `/500-dark/` logo variants exist for most teams (unknown here: ESPN blocked in this sandbox; fallback to the regular logo covers it).

## 2. SPECIFICATION
design.md § 0 written first (frozen tokens, type, layout, icon, logo rules).

| ID | Criterion (test) |
|---|---|
| S1 | One `game-card` per game with both teams and a "VS" badge (`restyle.spec.ts`) |
| S2 | `--bg` #0a0a0a, `--accent` #c6f135, `--accent-ink` #0a0a0a; h1 in Barlow Condensed, uppercase |
| S3 | Phone 393×852: fixed `nav[Primary]`, one active tab with a visible label, inactive tabs icon-only with names, no sideways scroll |
| S4 | `/icons/*.png` byte-equal to `docs/design/brand/app-icon/*`; manifest theme/background `#0a0a0a` |
| S5 | Matchup `win-split` tiles: both teams, percents summing to 100, "Model pick"; `nav[Sections]` with 8 pill links that jump |
| R1 | A change note shows on the card and in the pick panel |
| R2 | Picking against the model shows "Differs from model" on the card; clearing removes it |
| R3 | Weather outage: Conditions says the weather source is down, never "No forecast yet" |
| R4 | Backfill never reads as live: week-1 KPI `kpi-model` "–"; Results week-1 Model cell "–" + "backfilled"; weekly chart and calibration `aria-label`s state live vs backfilled; backfilled matchup panel and history never say "Live"; pytest `season_model_accuracy` live-only |
| R5 | CSV export has `model_pick_kind` (live/backfill) (pytest) |
| R6 | Client lock: TBD or postponed games stay open after their placeholder time; E4 now unlocks-within bound runs kickoff−1 s + 4 s |
| R7 | Every en dash has a reason where one is known (design critic) |
| K | E1–E14, W1–W5 stay green; axe 0 serious/critical both themes; design critic PASS vs reference 06 (393×852 and 1440×900) |

Red run (before any production change): pytest R5 failed (`KeyError: 'model_pick_kind'`), R4 season guard green (code already right; guard only). Playwright: 17 step-2 checks green; all 10 new checks red (no `game-card`, `win-split`, tab bar, tokens, icons, R1–R3, R6 cards).

## 3. IMPLEMENTATION
`IMPLEMENTATION_PROVIDER: CLAUDE (limit hit: Codex not installed)` · `JEV: unavailable` · `CLIMBS: none` · `/ponytail` rules in both work orders.

| WO | Scope | Rung | Commit | Proof rerun by the coordinator |
|---|---|---|---|---|
| F | R5 CSV `model_pick_kind` | sonnet, try 1 | `31ae11e` | pytest 57 passed · ruff clean |
| G | D39 tokens and Barlow Condensed titles, D40 cards/VS/split tiles/section pills/floating tab bar, D41 icons, dark-variant team logos, R1–R4, R6 | opus, try 1 | `f8a531e` | pytest 57 · ruff · gen:api no drift · typecheck 0 · grep empty · `npm run e2e` **27 passed** |

Reviews: WO-F diff read (one column, same prediction as `model_pick`). WO-G: 35 files (+657/-476), all `apps/web`, the lockfile and design docs. Recorded test-setup change: `playwright.config.ts` now sets `serviceWorkers: "block"` (Playwright's documented behavior: `page.route` cannot see requests a controlling service worker handles; R1 and E9b rewrite API responses). Accepted: no spec tests the worker; step 6 (iPhone PWA) adds the service-worker checks in a project without the block. Shared-index note: WO-F's commit also carries WO-G's staged `icon.svg` deletion; end state correct. Coordinator screenshots (393×852, 1440×900, dark): the structure matches reference 06. 21st.dev: not used (tab bar hand-built; the 2 daily code retrievals were already spent).

## 4. CLEANUP
No separate edits: both work orders landed minimal diffs, and the coordinator's read found nothing to simplify without a behavior change (design.md's older sections are superseded by § 0 by design; rewriting them is docs work for step 4's PLANNING). Recorded as `no change needed`.

## 5. VERIFICATION, round 1 — FAIL (on `782828e`)
* Coordinator validation green: pytest 57 · ruff · gen:api no drift · typecheck · grep empty · e2e 27/27.
* **Fresh critic (Opus): VERDICT FAIL.** Gate matched; mutation checks killed S1–S5, R1–R3, R5, R6 mutants and the chart/calibration R4 mutants. Blocking: R4's "never says Live" assertions were vacuous (`textContent` runs words together, so `\bLive\b` never matches) — the coordinator's spec fault. Also: S2 checks declared tokens only (hard-coded blue or an unloaded font would pass); CLEANUP missed dead code (`TeamBar`, `--text-hero`, unused text tokens); the evidence folder named in this log did not exist; the outage notice fires on `stale` without an error; the global service-worker block hides worker coverage; small step-2 losses (winner emphasis on final scores, Away/Home labels, no jump to Ask).
* **Fresh design critic (Opus): DESIGN VERDICT FAIL.** Blind: desktop Week ours; phone Week/Matchup/Results reference 06, narrowly. Blocking: every signed-in screen scrolls sideways at 320px (top bar); the Matchup pick panel never says "Differs from model"; the lime "✓ Model pick" tile shows a ✓ on a losing backfilled pick and colors the model lime (design.md § 0 contradicted itself). Structure gaps: chips not directly under the title; pick buttons below the fold; scroll-spy marks the wrong tab; final scores read like a clock.

Fix round spec (red, committed before any fix): R4 assertions use `innerText`; S2 also requires the font loaded and the active nav pill painted lime; F1 no sideways scroll at 320 on five screens; F2 "Differs from model" in the pick panel; F3 model tile never lime and no ✓, backfill says "Backfilled" on the tiles; F4 chips directly under the title, above the summary and cards, both visible on a phone; F5 pick buttons in view without scrolling at 393×852 and 1440×900; F6 the jumped-to section tab is `aria-current`, and "Ask" is reachable. design.md § 0 corrected (model tile outline + words, never lime). Service-worker block moved from the global config to the specs that rewrite responses (restyle.spec, E9b). Red run: F1–F6 failed for the intended reasons; E4 failed only in the full run (passes alone twice: picks left behind by the red F-tests), re-checked after the fix.

### Fix round (WO-H)
| WO | Scope | Rung | Commit | Proof rerun by the coordinator |
|---|---|---|---|---|
| H | F1–F6, S2/R4 confirmed, honest weather reason, away–home final scores with winner emphasis, Away/Home labels, Ask tab, dead code removed (`TeamBar`, unused text tokens), `BigDash` for missing big figures | opus, try 1 (new job; round-1 failures were spec gaps and a spec contradiction, the coordinator's) | `8ba91ea` | pytest 57 · ruff · gen:api no drift · typecheck 0 · `npm run e2e` **33 passed, twice in a row** (E4 order-dependence gone) · files in `step-3-evidence/` (logs + 393/320/1440 screenshots) |

Review: 13 files, all `apps/web`, no spec/config/backend change. CLEANUP for the step now has evidence: dead code removed in WO-H (the round-1 "no change needed" was wrong and is superseded).

## 5. VERIFICATION, round 2 (on `fadefd5`)
* **Fresh critic (Opus): VERDICT PASS.** Gate matched (pytest 57, e2e 33 twice, typecheck, gen:api, grep); fix-round red reproduced on 782828e; 29 mutants, 25 killed. Survivors (code correct today): hard-coded blue on pick/primary/chip; lime border or text on the model tile; "source is down" with no logged error; backfill mixed into the weekly bar data. Also: critical axe `select-name` on the phone Week board (E11 only runs at 1440); service-worker block wider than needed; doc drift in design-tokens.json and design.md §§ 5/7/8.
* **Fresh design critic (Opus): DESIGN VERDICT FAIL.** Blind: Matchup at 393 and Week at 1440 now ours; Week 393 and Results reference 06, narrowly. Blocking: week-1 Matchup Team comparison shows eight bare "–" (carried rule); week-1 Matchups scroll 2–7px sideways at 320 (factor bars, reported with logos loaded). Non-blocking: bar fills from the left even when the home team is the pick; waiting-to-sync pill looks synced; focus ring on lime nearly invisible and a focused pick button can sit under the tab bar; no chips on Results/Backtest/Settings; final pills lack the word "Locked"; Results note wording.

Round 3 spec (red before any fix): F1 now covers the week-1 matchups with logo images loaded; F3 also reads border and text color; G1 no bare "–" in Teams on a week-1 matchup (red: 8); G2 a picked pill and the selected chip paint lime (guard; green); G3 focus ring visible and not under the tab bar (guard; green); G4 stale weather without an error never says "down" (guard; green); G5 axe 0 serious/critical on five screens at 393 in both themes (red: `select-name`). Service-worker block scoped to the three tests that rewrite responses (R1, R6, G4) and E9b. Two red-run artifacts fixed in the specs (hover color read during G2; a pick left behind by it broke E3).

### Round 3 build (WO-I)
| WO | Scope | Rung | Commit | Proof rerun by the coordinator |
|---|---|---|---|---|
| I | G1 reasons in Team comparison, G5 select names, factor-row fit, bars fill from the pick's side, dashed waiting pill, "Locked" under locked pills, Results caption, chart label from the bar data, "Postponed" chip | sonnet, try 1 | `a890585` | pytest 57 · typecheck 0 · grep empty · `npm run e2e` **39 passed, twice** (`step-3-evidence/coord-r3-*.log`) |

## 5. VERIFICATION, round 3 (on `171e267`)
* **Fresh design critic (Opus): DESIGN VERDICT PASS.** Polish carried to step 6 (iPhone PWA): phone card density (about one card per screen); doubled "What changed: Changed:" copy; tooltip can sit under the tab bar; 2px sideways scroll at 320 from the sticky section nav on a final game; lime on disabled AI buttons; no chips on Results/Backtest/Settings; league-leader reference missing.
* **Fresh critic (Opus): VERDICT FAIL** on G3. With a real Tab key at 393×852, the first cards' pick buttons (y 782–836) sat under the floating tab bar (778–840): no `scroll-padding-bottom`. The old G3 also read the ring color mid-transition. Non-blocking, fixed in round 4 specs: F1 never really loaded logos (service worker not blocked); blue survivors possible on the primary button, phone active tab and section pill; F3 survivors through children, side borders and ✔; duplicate "Locked" on in-progress matchups. Doc drift (design.md §§ 5/7/8 still describe the blue system) goes to step 4 PLANNING.

Round 4 spec (red, `6ed3c5b`): G3 presses the real Tab key with reduced motion and checks up to four focused pick buttons: outline not none, width ≥ 2px, bottom above the tab bar (red: `Pick BUF Team` bottom 830 vs bar top 778). G2 also requires lime on the Sign in button, the active section pill, the phone active tab, a picked pill and the selected chip. F3 checks every descendant of the model tile for lime and no ✓/✔. F1 blocks the service worker so the logos really load.

### Round 4 fix (coordinator, `8973ec4`)
`html { scroll-padding-bottom: calc(84px + env(safe-area-inset-bottom)) }` below 1024px (tab bar 62px + 12px gap + margin); removed the second "Locked. The game has started." line from the pick panel (the pill row already says Locked). A first try also set `scroll-padding-top`; it stacked with the sections' `scroll-mt-32` and made F6 fail once in a full run, so it was dropped (top bar offset stays with `scroll-mt`).

Proof (`step-3-evidence/coord-r4-*.log`): pytest 57 passed · ruff clean · gen:api no drift · typecheck 0 · `npm run e2e` **39 passed, three runs in a row** after the rebuild.

Grep gate (empty on `8973ec4`):
```bash
grep -rnE "#3b82f6|#2563eb|blue-[0-9]" apps/web/app apps/web/components
grep -rnE "sk-ant-|sk-or-v1|VAPID_PRIVATE" apps/web/app apps/web/components apps/web/lib packages/shared/src
```

## 5. VERIFICATION, round 4 (on `8973ec4`) — PASS
* **Fresh critic (Opus): VERDICT PASS.** Gate matched: pytest 57, ruff clean, gen:api no drift, typecheck 0, web:build 0, e2e 39/39 three times. Mutants killed: round-3 `globals.css` brings back G3's red (830 vs 778); blue on the section pill or Sign in button fails G2. Own probe: Tab through every focusable on five screens at 393, 0 under the tab bar. Section jumps land below the sticky nav and set `aria-current`; no sideways scroll at 393/1440. "Locked" shown once on an in-progress game. Grep gates 0 hits.
* **Fresh design critic (Opus): DESIGN VERDICT PASS.** No regressions against reference 06 or design.md § 0 at 393, 1440 and 320; 104 focused controls at 393, none under the tab bar.
* Carried to step 6 (iPhone PWA): Shift+Tab can leave a pick button under the sticky top bar on the phone (pre-existing; needs top padding that does not double with `scroll-mt-32`); check iOS Safari honors `scroll-padding` on the device; section-tab row needs a right-edge fade; "next kickoff" text could drop lime; KPI captions wrap to 3 lines at 320; chips near the tab bar on a low card; plus the round 3 polish list.
* Carried to step 4 PLANNING: design.md §§ 5/7/8 still describe the blue system.

## 6. LANDING
Step 3 DONE on the round-4 head. Pushed to `claude/nfl-pickem-intelligence` (`3cd9964`), draft PR #1 updated. CI on `3cd9964`: 8/8 green (backend, web, docker, e2e; push and PR runs).
