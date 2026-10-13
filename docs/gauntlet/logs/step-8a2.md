# Step 8a2: star players and who is out, on screen (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · tier T2 · Design Gauntlet applies
Dispatch: hive message `2026-10-13T07-16-38-672Z-f56548`. Worktree `.claude/worktrees/lane-web`, branch `lane/web`, base main `a9ed486`. Coordinator Jim; builder Ryan (Codex); security reviewer Dwight; one fresh critic per round.

## 1. PLANNING

**In the owner's words (D21, D22, D27).** Step 8a already works out "the QB + top 2 on offense + top 2 on defense" for every club each week, and can answer "for this game, which stars are out or doubtful, and how old is that report?". Nobody can see it yet. This step puts it on screen:

* **What it builds:** on the game row, "a short who's out line, stars only, with its age"; on the game screen, the full list of both clubs' five stars with each one's status. The worker refreshes the star list on its normal round, and the data-freshness list shows the star list and the head-coach refresh.
* **What it replaces:** nothing. The Injuries section and the QB alert on the row stay as they are.
* **What it is not:** it never changes a pick, a win chance or a label (D24, D27: "The label never changes because of an injury"). No alert (8i), no news (8g), no model test (8b), no second source (D26), no re-ranking of the list (the known gap, Chris Jones fourth for Kansas City 2025, is shown as the data has it).

**Roadmap row:** `PLAN.md` row 8, sub-step 8a2 (wave 5: the API, worker and web wiring of step 8a). **Reversibility:** two-way: new API fields (additive), one new web section and one line on the row, two entries in the freshness list. No table, no migration.

**Decisions relied on:** D21, D22 (five per club, automatic), D23 and D27 (Out or Doubtful only on this line, with age; Questionable is for alerts, later), D24 (shown, never moves the pick), D39 to D41 and `design.md` (look), `CLAUDE.md` data rules ("Missing stays missing (null) and is shown as missing"), god's ruling in the dispatch (no re-rank; no migration; one web lane).

**Scope (lane web's files only):** `backend/nflpi/api/schemas.py`, `api/views.py`, `analytics/stars.py`, `jobs.py`, `config.py`, `backend/tests/test_api.py`, `test_stars.py`, `e2e_seed.py`, `packages/shared/**` (generated), `apps/web/**`, `design.md` if a durable rule changes.

**SEAM open with god (sent 07:25Z, `s8a2-seam-freshness`):** the freshness list is `STALE_HOURS` in `backend/nflpi/ingestion/service.py`, which this lane does not own (the dispatch placed it in `jobs.py`). Asked for exactly two entries there (`stars`, `head_coaches`). Criterion F1 waits for the answer.

**Carried from step 8a, taken here (in my files):** worker loop; API and web; a per-club star-list week (today `stars_week` is one number over both clubs); a star with no league id matched by name despite "Jr.", "II" and the like; control characters stripped from names before they reach the web, with Dwight's review of that path.
**Carried again, not here (ingestion code, another lane's files):** `checked_at` per season; an empty injuries file still logging ok; a distinct message for expected failures (N5, L3); Dwight's lows L1, L2; critic 4's test gaps inside `ingestion/`.

**Pre-flight (Product Mode, T2)**
1. Problem: the owner picks every game without seeing whether a club's best players are out, unless he reads the long injury list.
2. Why now: step 8a's data landed and step 7 freed the web files.
3. Scope: one line on the row, one section on the game screen, the worker call, freshness. Cut: alerts, Questionable, re-ranking, news.
4. Success signal: on a week with a star out, the owner sees it on the row without opening the game. No number exists for this; qualitative.
5. Reversibility: two-way.

**Assumptions**
* validated: `stars_out(session, game_id)` returns `out`, `reports_seen`, `stars_week`, `checked_at` (read in `analytics/stars.py`).
* validated: `age_hours` counts from when this app first saw the status, not from when the club filed it (docstring). The screen must say "seen", not "reported".
* assumed: the week board may call the star question once per game (16 games). If it is slow, step 13 (speed) batches it.
* unknown, does not change the design: how often nflverse publishes the two star files in-season (hand check at go-live).

**Discovery (jevgrep, `step-8a2-evidence/jg-1.log`):** the row is `apps/web/components/week/game-card.tsx` fed by `views.summaries` (`GameSummary`); the game screen is `components/game/game-view.tsx` fed by `views.game_detail` (`GameDetail`); the existing Injuries section (`components/game/injuries.tsx`) is the reference component for a per-club list with status chips; freshness is `components/freshness.tsx` over `service.freshness`.

**Specialist skills:** `/graft` and `/jevgrep` (above) · project TDD (red tests first, public seams: the API JSON, the worker's `cycle`, the rendered page) · `/ponytail` in every work order · Design Gauntlet (`references/design-gauntlet.md`; brief below) · `harness-engineering`: N/A (no runner or approval boundary changes) · Parallel Lanes (`lanes.md`, lane-guard before landing).

**Baseline:** `base-a` on `a9ed486` (gate script `step-8a2-evidence/gate.sh`, the lane's own test database on `127.0.0.1:15436`); result recorded in section 2 when it returns.

### Design brief (Design Gauntlet section 6)

```text
PRODUCT:          NFL Pick'em Intelligence, a private one-user app (phone PWA first, desktop second).
USER GOAL:        While picking a week, see at a glance which games have a star player out or doubtful, and how
                  fresh that is. Primary action stays "tap a team to pick"; this step adds reading, not a control.
REGISTER/PRESET:  product · consumer product with a dense data card (design.md: DENSITY 6 phone / 7 desktop).
DESIGN DIRECTION: quiet, scannable, honest about age and gaps, same voice as the QB alert already on the card.
EXISTING SYSTEM:  design.md section 0 (reference 06, lime = me only; warn/bad tokens for doubtful/out) ·
                  row: apps/web/components/week/game-card.tsx (the flags line with QB alerts and Chip tones) ·
                  list: apps/web/components/game/injuries.tsx (per-club list, status chips, "Report as of") ·
                  Section, Chip, TeamLogo in components/ui and components/team · ago() in @nflpi/shared.
PROBLEMS:         the row shows only a QB's status; any other star out is invisible until he opens the game and
                  reads up to 2 x 8+ injury rows (before-* screenshots, taken at SPECIFICATION).
SKILL WORKFLOW:   director = design.md + ECC frontend-design-direction; UX Architect critic on this brief and the
                  spec before code; after the build: UX, Visual/anti-slop and Implementation critics in parallel,
                  then blind A/B, then Polish. All fresh general-purpose subagents, read-only.
PROPOSED CHANGES: 1 row: one "Stars out" line in the existing flags area, only when at least one star is Out or
                    Doubtful: name, position, status chip, and "seen 3h ago"; at most 3 names then "+N more".
                  2 game screen: a "Star players" section before Injuries: both clubs side by side (stacked on
                    the phone), five rows each (QB, offense, offense, defense, defense) with status or "Not listed".
                  3 freshness list: "stars" and "head coaches" rows; neither can turn the top-bar indicator amber.
DESIGN.MD IMPACT: none expected (no new token, no new component kind); confirm at LANDING.
BAR:              the app's own Injuries section and QB alert line (same viewport, same game), as the reference
                  for tone and density; a blind A/B of the game screen before/after must be a win or a tie.
STATES:           row: none out (no line) · 1 to 3 out · more than 3 · long name (truncates) ·
                  game screen: loading (existing page skeleton) · both lists ready · one club has no list ·
                  no list at all · no injury report yet this week · list older than the game's week ·
                  a star Out / Doubtful / Questionable or other status (shown as text, no alarm colour) / not listed.
```

## 2. SPECIFICATION

**Baseline `base-a` on `a9ed486`** (load 4.48 before): pytest 222 passed, ruff clean, no API type drift, typecheck 0, browser 102 passed. Logs `step-8a2-evidence/base-a-*.log`.

**Gate (executable):** `caffeinate -i bash docs/gauntlet/logs/step-8a2-evidence/gate.sh <label>` = pytest, ruff, API type drift (`npm run gen:api` then no diff), typecheck, `npm run e2e` (builds the web app, then every browser spec). Run under coord locks `res:gate` and `res:e2e`, lease renewed every 45 s, load recorded beside each run.

**Public seams tested:** the API's JSON (`/api/weeks/{season}/{week}`, `/api/games/{id}`, `/api/freshness`), the worker's `jobs.ingest`, the two questions in `analytics/stars.py`, and the rendered pages in a real browser.

### Frozen contract (API, additive)

```text
GameSummary.stars_out : { out: StarStatus[], reports_seen: int, checked_at: datetime|null, no_list: string[] }
GameDetail.stars      : [TeamStars(away), TeamStars(home)]      (GameDetail also carries stars_out)
TeamStars             : { team, stars_week: int|null, stars: StarStatus[] }   stars_week null = no list for this club
StarStatus            : { team, player, position|null, slot: "qb"|"off"|"def", rank, status|null, injury|null,
                          observed_at|null }      status null = not on this week's report
analytics.stars.game_stars(session, game_id, now=None) -> { game_id, season, week, reports_seen, checked_at,
                          teams: [ {team, stars_week, stars: [ ...StarStatus fields..., age_hours|null ]} x2 ] }
```

### Frozen acceptance criteria (frozen after the UX Architect review, before any production code)

UX Architect critic (fresh subagent, read-only) on the brief and the first draft: 18 findings, 1 Critical (the row's silence meant three things). Triage and decisions: `step-8a2-evidence/reviews/ux-architect-spec.md`. ST1 to ST6 below are the amended wording.

Functional (server):
* **B1 each club's own list.** For a game, each club's stars come from that club's newest list of the same season at or before the game's week. A club whose list is older than the other's is not dropped (today it is). `test_stars_out_uses_each_clubs_own_latest_list`.
* **B2 the full five.** `game_stars` returns both clubs, away first, each with its list week and every star in slot order (QB, offence 1 and 2, defence 1 and 2) with his newest status of the game's week or null. A practice note alone is not a status. A club with no list is returned with `stars_week` null and no stars. `test_game_stars_lists_every_star_of_both_clubs_with_his_status`.
* **B3 names spelled two ways.** When either side has no league id, a star matches a report of the same club whose name is the same after ignoring case, dots, apostrophes and a trailing Jr, Sr, II, III, IV or V. A different name never matches. When both sides have an id, only the id decides. Three tests named `..._spell_his_name_differently`, `test_a_different_name_is_never_matched_to_a_star`, `test_an_id_on_both_sides_still_decides...`.
* **B4 the API carries it, cleaned.** `GameSummary.stars_out` and `GameDetail.stars` follow the contract. Control and invisible formatting characters (Unicode categories Cc and Cf) are removed from every player, position, status and injury text before it leaves the API. A game with nothing known returns an empty `out` and `reports_seen` 0, not an error. `test_week_board_says_which_stars_are_out_and_the_game_view_lists_all_of_them`.
* **B5 never moves a pick (D24, D27).** The prediction and the pick sheet of a game are the same before and after its stars are reported out. Same test.
* **B6 the worker refreshes it.** `jobs.ingest` asks for this season's star list once per round and reports its status under `stars`; a failed star refresh does not stop the round. `test_the_worker_refreshes_the_star_list_and_a_failure_does_not_stop_the_round`.
* **F1 freshness (waits on the SEAM).** `/api/freshness` lists `stars` and `head_coaches`: never refreshed = stale with no time; a good run clears it. `test_freshness_lists_the_star_list_and_the_head_coaches`.

User-facing (browser, phone 393x852 and desktop 1280x800; `apps/web/e2e/stars.spec.ts`):
* **ST1** a scheduled game's row shows a "Stars out" group on its own line under the flags row: each star Out or Doubtful with position and status chip, then "latest seen 3h ago" (the newest of those shown). Questionable stars and non-stars are not on the row.
* **ST2** more than three: three names, then "+N more" (N = what is hidden). A player already named in the card's QB alert is not repeated in the stars line. A very long name never makes the page scroll sideways.
* **ST3** the row is silent only when the week's report is in, both clubs have a list and no star is Out or Doubtful. Otherwise a quiet text: "No star list yet" (a club has none) or "Injury report not in yet" (lists exist, no report this week). A game that is running or finished has no stars line.
* **ST4** game screen, in the Injuries section, under its own heading "Star players": one list per club named "<club> star players", five rows in slot order, each with his status or "Not on injury report"; an Out or Doubtful row shows the injury and when it was seen; a club whose list is older than the game's week says "Star list from week N"; one line says a star being out does not change the pick, and one says ages count from when this app first saw the status.
* **ST5** a club with no list says "No star list yet".
* **ST6** before the week's first injury report the section says "No injury report yet this week" and never "Not on injury report" (not known is not shown as available).
* **ST7** no serious or critical axe issue on the board or the game screen, dark and light.
* **ST8** Settings lists a `stars` row and a `head coaches` row in the freshness list.
* **ST9 (existing tests)** every browser test that passed at baseline still passes with the new seed.

Operational:
* **O1** the top-bar freshness indicator turns amber only for a model input; `stars` and `head_coaches` are not model inputs (they never move a pick). Covered by the existing indicator tests staying green plus the builder keeping `MODEL_INPUTS` unchanged; checked in the diff.
* **O2** no migration, no new dependency, no new table; generated API types regenerated, not hand-edited.

Subjective (Design Gauntlet): blind A/B of the game screen against the "before" capture is a win or a tie; no Critical or Structural finding open.

### Spec amendment after the freeze (before any web code)

* **`StarsOut.no_list: string[]`** (clubs of this game with no star list, away first). ST3, as amended by the UX review, needs the row to say "No star list yet"; the contract frozen an hour earlier gave the row no way to know. Red first: two new assertions in `test_week_board_says_which_stars_are_out_and_the_game_view_lists_all_of_them` (`red-2-api.log`). Built in work order 2.
* **Correction to my own red test (work order 1):** it asserted that the other week-4 games list nobody. A fixture club plays twice in week 4, so its star is rightly listed on both of its games. The assertion now says: another game lists a star only when his club plays in it.

### First failing tests (red for the intended reason)

* `red-1-stars.log`: 8 failed, 62 passed. B1 lists only the Jets' star (the club with the newer list); B2 `game_stars` does not exist; B3 six spellings unmatched.
* `red-1-api.log`: 3 failed, 7 passed. B4 `GameSummary` has no `stars_out`; B6 `ingest_stars` never called; F1 the two datasets are missing.
* `red-1-e2e.log` (load 10.08 before): all 17 browser tests of `stars.spec.ts` fail against the baseline web build: no "Stars out" group, no "Star players" heading, no `stars` row in Settings.

**Seed for the browser tests** (`backend/tests/e2e_seed.py`, `STAR_LISTS`): made-up players in the app's own domain: KC (week 4 list; Out, Doubtful, Questionable), NE (week 3 list), BUF (four out, one very long name), MIA and LV with no list; reports first seen three hours ago; one ok run each for `stars` and `head_coaches` so the freshness indicator does not change for the existing tests.

## 3. IMPLEMENTATION

Builder: Ryan (Codex). Coordinator inspects each diff and reruns the proof (Ryan cannot bind ports or reach the test database). Model choice: `decide.sh` returned route "advisor" (Jev unavailable); step-7 precedent used: work order 1 sol/medium, work order 2 sol/high. No climbs.

| Work order | Commit | What | Proof (mine) |
|---|---|---|---|
| WO-1 (`wo-1.md`), try 1 | `83d116e` | `analytics/stars.py`: each club's own newest list, `game_stars`, name matching; `views.py`, `schemas.py`: `stars_out`, `stars`, cleaned text; `jobs.ingest` refreshes the star list and survives its failure | `wo1-proof.log`: ruff clean; `test_stars.py` 70 passed; `test_api.py` 8 passed, 2 failed. One failure was my own wrong assertion (corrected, see the amendment above); the other is the freshness test, which waits on the seam. |
| WO-2 (`wo-2.md`), try 1 | `4657935` | `game-card.tsx` "Stars out" line; new `star-players.tsx`; `injuries.tsx`; `freshness.tsx` label; `stars_out.no_list` | ruff clean, typecheck exit 0, `gen:api` no further drift, `test_api.py` 9 passed 1 failed (freshness, seam). `wo2-e2e.log` (load 4.53): 13 passed, 4 failed. ST7 x3: axe measured an existing line ("Tap a team to pick", `recommendation.tsx`) mid fade-in; my test lacked the reduced-motion setting the existing E11 check uses. Fixed in the test; `wo2-e2e-st7.log` (load 7.64): 12 passed (4 checks x 3 repeats). ST8 waits on the seam. |

Diff inspection: both diffs touch only lane web's files; no untracked extras; no new dependency.

**Open seam (sent to god twice):** the freshness list (`STALE_HOURS`) lives in `backend/nflpi/ingestion/service.py`, not lane web's file. Two entries are needed (`stars`, `head_coaches`). Until granted, `test_freshness_lists_the_star_list_and_the_head_coaches` and browser ST8 stay red.

Screenshots: `~/.claude/plans/nfl-pickem-lanes-logs/step-8a2/before-*.png` (baseline build, `shots-before.log`) and `after-*.png` (HEAD of work order 2), board and two game screens at phone, tablet and desktop.

Work orders, continued:

| Work order | Commit | What | Proof (mine) |
|---|---|---|---|
| WO-3 (`wo-3.md`), try 1 | `f3c5e21` | Seam granted by the integrator (hive message 08276f): two settings in `config.py`, two `STALE_HOURS` entries in `ingestion/service.py` | Diff is exactly four lines. `test_api.py`: the freshness test is green (`red-3-api.log`: 10 passed; the 1 failure is the next red test). Browser ST8 is proven in the next browser run. |

### Design review, round 1 (three fresh critics in parallel, read-only, on `4657935`)

Reports: `step-8a2-evidence/reviews/ux-critic-1.md`, `visual-critic-1.md`, `impl-critic-1.md`. No finding was dropped silently:

| Decision | Findings | What |
|---|---|---|
| Accepted, red test first | U1, V12, I3 (Critical) | The "no star list" note also shows when the other club has stars listed, and names the club (ST2 assertion) |
| Accepted, red test first | U2, I7 | Club in front of each name on the card (ST1 assertion) |
| Accepted, red test first | I1, I2 | The API marks a star named in the QB alert (`StarStatus.qb_alert`); the card stops matching display text; star quarterbacks' alerts come first (`red-3-api.log`) |
| Accepted, red test first | U4, V1, I4 | "Full injury report" heading; club names one level below both headings (ST4 assertions) |
| Accepted, by inspection and screenshots | U5, V2, I5, U6, V4, V3, U7, V6, U8, V8 (age on the label line), V7, V10, V11, I6, I9, I10, I11, I13, I14, I15 | One chip style for one status; no slot word; inline week note; no dashed box for "no list"; plain-text status on the card; small fixes |
| Rejected | U3 | Per-club "report not in": the week's report arrives whole, so when it holds one club of a game a club with no entry is truly not on it |
| Rejected | U9, V9 | Totals, or folding the quarterback into the stars line: he is named with his club one line above |
| Rejected | V5 (tooltip), V8 (truncate or surname only), I8, I12 | Both notes are owner wording (D24, D27) and stay visible; names are never cut; group label is what the tests and screen readers use; no shared helper for two call sites |

Work order 4 (`wo-4.md`) carries the accepted items. Red tests committed in `f197494`.

| Work order | Commit | What | Proof (mine) |
|---|---|---|---|
| WO-4 (`wo-4.md`), try 1 | `f4198bf` | The accepted design findings: `StarStatus.qb_alert` set by the API from the matched report row, star quarterbacks' alerts first; card: club before each name, no-list note beside listed stars, age on the label line, plain-text status; game screen: "Full injury report" heading, club names one level down, one chip style, no slot word, no dashed box for "no list" | Diff touches only the eight allowed files. ruff clean; `test_api.py` 11 passed; `test_stars.py` 70 passed; typecheck exit 0; `gen:api` twice, same checksums. `wo4-e2e.log` (load 8.17, build ok): 17 passed, ST8 included. Screenshots `after2-*.png`; I checked the phone board and the phone game screen by eye. |

### Design review, rounds 2 and 3

* **Blind A/B judge** (`reviews/ab-judge-1.md`, images only, sets named by coin flip, key recorded after the verdict: X = before, Y = after work order 4): **winner Y**. Of its five remarks on the winner one is accepted (the missing-list note is too dim), four are not changed, with reasons in the report.
* **Polish critic** (`reviews/polish-critic-1.md`): four Polish findings, all accepted; **verdict: ship**. Work order 6 (`wo-6.md`) carries them and the judge's remark.
* **Scripted gates:** sideways overflow at 393 px: ST2 (0 px); accessibility (axe, serious and critical, dark and light, board and game screen): ST7, green; touch targets: not applicable, the step adds no link, button or input; console: the gate's browser run fails on page errors.
* **Stop rule:** gates green; blind A/B a win; no Critical, Structural or Visual finding open after work order 4; remaining remarks are variation no critic tied to a user-visible harm.
* **`design.md`:** no durable change. The step uses existing tokens and components only.

## 4. CLEANUP

Explicit scope-locked `/refactor` pass after the review fixes: work order 5 (`wo-5.md`), commit `989cac2`, behaviour unchanged.

| Item | Result |
|---|---|
| One star read per game on the week board | Done: `views.summaries` calls `stars.game_stars` once and builds `StarsOut` from it; the `stars_out` call, the key set and the row merge are gone. `analytics.stars.stars_out` stays (its tests and step 8b use it). |
| `report_id` | Kept only for one set and one sort key that put a star quarterback's alert first. |
| One list of alert statuses | Done: `ALERT_STATUSES` lives in `analytics/stars.py`; `views.py` imports it. `notify/push.py` has its own copy and is left alone (not part of this step's diff). |
| `statusTone` | Done: exported from `star-players.tsx`, imported by `injuries.tsx`; the function props are gone. No circular import. |
| Unused code after work order 4 | No change needed: `Chip` in `game-card.tsx` is still used by other flags; every `slotName` entry is the fallback when a position is missing. |

Proof after the edit (mine): ruff clean; `test_api.py` 11 passed; `test_stars.py` 70 passed; typecheck exit 0; `gen:api` no change; `wo5-e2e.log` (load 4.96, build ok): 17 passed. Screenshots `after3-*.png`.

Remaining, classified: the week board reads stars once per game (about five small queries per game, 16 games): acceptable for one user; a single batched read belongs to step 13 (backend speed). Carried to the ingestion lane (not this lane's files): `checked_at` per season, an empty injuries file logging ok, distinct failure messages.

## 5. VERIFICATION

### Polish and first gate pair (before the final HEAD)

* Work order 6 (`wo-6.md`): five class changes from the polish critic and the blind judge. Typecheck exit 0. Lane replayed onto main `a71e112` (no conflicts).
* **Gate pair g1 on `89600bd`: RED, kept as evidence** (`g1-a-*.log`; load 9.23 before).
  * `g1-a-pytest.log`: 1 failed, 658 passed: `test_health_is_degraded_without_a_fresh_worker_heartbeat`. Cause: health reports "degraded" while any freshness dataset is stale, and work order 3 added two datasets that the test's setup did not refresh. Production code is right (the worker refreshes both every round; a refresh that fails for days should show). Fixed in the test setup (my file). Operational consequence, said plainly: `/api/health` now turns "degraded" when the star list is more than 8 days old or the head coaches more than 30.
  * `g1-a-e2e.log`: 1 failed, 118 passed: existing check L1 (phone density): the first card's pick buttons ended at 827 px, limit 778 px. A real regression from this step: the stars block was up to four lines. The earlier browser runs had run only `stars.spec.ts`, so they could not see it.
  * `g1-b` is **void**: I edited tests and ran three single test files against the shared test database while it ran (661 errors are mine). Lesson recorded: nothing else runs during a gate.

### Security review (Dwight), round 1 on `89600bd`: PASS, no critical, no high

Report and decisions: `reviews/dwight-1.md`. Accepted with red tests first (`red-4.log`): M1 offline cache version, M3 name matching, M4 "No game status". Not changed or carried, with reasons: M2, M5, M6, lows.

### Work order 7 (`wo-7.md`), two tries, commit `7c5572d`

| Part | What | Proof (mine) |
|---|---|---|
| A | The card's stars block is one line that never wraps: label, names (truncate with an ellipsis), "+N more", "seen 3h ago", "{club}: no star list". This amends my round-1 decision "names are never cut": owner decision D27 asks for "a short who's-out line" with the full list on the game screen, and the density rule L1 is older than this step. | browser L1 and ST2 in the gate below |
| B | `persist.ts` `VERSION = 2` | by reading (`persist.ts:19` drops a cache of another version) |
| C | `_normal_name` folds accents; `_star_report`: id matches plus name matches where one side has no id; more than one distinct raw name: only the exact spelling counts; the newest report wins | `test_stars.py` 72 passed |
| D | `listed` on star rows and in `StarStatus`; "No game status" on the game screen | `test_stars.py`, `test_api.py` 11 passed, browser ST4 |

Try 1 broke one existing star test (`test_stars_out_takes_the_newest_report_when_one_has_an_id_and_one_has_none`: an id match returned at once, so a newer report without the id lost). Try 2 fixed that one function. Lane replayed onto main `e51ac48` (no conflicts); `npm run gen:api` after the replay: no drift.

### Security review (Dwight), round 2 on the delta at `7c5572d`: PASS

Hive message a0e34f. M1, M3, M4 fixed as described; nothing new of critical, high or medium severity; my decisions on M2, M5, M6 and the lows accepted. He checked that the replayed parent holds the same code he reviewed. One low carried on his advice: a namesake on the same club whose report has no id could still join the candidates when the star matched by id.

### Final gate pair g2 on `7c5572d` (lane replayed onto main `e51ac48`): GREEN twice

Command: `docs/gauntlet/logs/step-8a2-evidence/gate.sh <label>` under coord locks `res:gate` and `res:e2e`, lease renewed every 45 s, locks still mine at the end of each run. Packages installed first (`install-npm.log`, `install-uv.log`).

| Run | Load before (1, 5, 15 min) | pytest | ruff | gen:api | typecheck | browser |
|---|---|---|---|---|---|---|
| g2-a | 13.13 11.24 9.64 (measured right after my own package install; above the 12 line, said as it is) | 965 passed | clean | no drift | exit 0 | 119 passed |
| g2-b | 8.88 9.80 9.50 | 965 passed | clean | no drift | exit 0 | 119 passed |

Logs: `g2-a-*.log`, `g2-b-*.log`. Baseline before the step on the old main: `base-a-*.log`.

**Lane-guard** (`lane-guard.log`, against `e51ac48`): `OUT OF LANE: backend/nflpi/ingestion/service.py: owned by lane coaches`, 1 problem. That is the one edit the integrator granted (hive message 08276f: two `STALE_HOURS` entries) and said he accepts; no other finding.

Builders: work orders 1 to 7 were all built by Ryan (Codex). None by Claude.

Correction to the line above: work orders 8 and 9 (below) were built by Claude Sonnet subagents, because Codex ran out of credits about 09:00 UTC on 2026-10-13 (god's rule, hive message c11d28: a Sonnet subagent builds, never Opus; the coordinator still writes the spec and the failing test and reruns every proof; the builder is never the critic).

### Fresh critic, round 1 on `c5451ad`: FAIL (one major)

Report and decisions: `reviews/critic-1.md`. Its own gate run was green (`critic-a-*.log`: 965 passed, 119 browser checks, load 4.39 5.57 7.21). F1 (major): the one-line stars line of work order 7 was never screenshotted or design-reviewed and cut names and statuses at 393 px; "+N more" understated what was hidden; the tests passed on cut text. Accepted.

### Work order 8 (`wo-8.md`), one try, built by Claude Sonnet

Decision: the line names ONE star in full, the worst status first, then counts the rest; only the name may be cut; position, status, count, age and the missing-list note are never cut. The API orders `stars_out.out` Out before Doubtful (one stable sort in `views.py`); the client does not sort.

| What | Proof (mine) |
|---|---|
| Red first | `red-5.log` (`test_api.py`: 1 failed, 10 passed, the order assertion); `red-5-e2e.log` (ST1 and ST2 failed on phone and desktop, 13 passed) |
| After the build | diff in scope (two files); ruff clean; `test_api.py` 11 passed; `test_stars.py` 72 passed; typecheck exit 0; `gen:api` no drift; `wo8-e2e.log`: `stars.spec.ts` and `phone-layout.spec.ts` 30 passed with a fresh build |
| Screenshots | `~/.claude/plans/nfl-pickem-lanes-logs/step-8a2/after5-*.png`; I looked at the phone board: status, count, age and "MIA: no list" are whole; only the 39-character stress name is cut |

Check gate pair g3 on `0633ad5` (old main): green twice, 965 passed, 119 browser checks, loads 6.07 6.14 5.67 and 8.70 8.55 7.06 (`g3-*.log`).

### Security review (Dwight), round 3 on the delta `7c5572d..0633ad5`: PASS

`reviews/dwight-3.json`. No critical, high or medium. Two low notes, both as the work order intends (the age is the named star's; the sort is "Out before the rest", right while the set is Out and Doubtful). Work order 9 below came after his review: it changes one fixed string and adds one fixed character in `game-card.tsx`, no feed text and no logic, so I did not ask for a fourth round.

### Design critic 2 on the one-name line (`reviews/design-critic-2.md`): FIX, two accepted

It confirmed F1 is fixed (nothing a reader needs is cut at three widths). Accepted: "no list" reads as good news, so it says "no star list"; a dot between the count and the age. Not changed, with reasons in the report: rewriting names as initial plus surname (the app never rewrites a name from the feed; a real name fits in the normal state), per-club counts, the QB in the count, "seen", the group label.

### Work order 9 (`wo-9.md`), one try, built by Claude Sonnet

Two lines in `game-card.tsx`. Red by reading (ST2 asked for "MIA: no star list" and the dot; the code said "no list"). Proof: typecheck exit 0, then the gate below (ST2 green on phone and desktop).

### Landing gate pair g4 on `1f50f96` (lane replayed onto main `98ec875`, no conflicts; `npm run gen:api` after the replay: no drift): GREEN twice

| Run | Load before (1, 5, 15 min) | pytest | ruff | gen:api | typecheck | browser |
|---|---|---|---|---|---|---|
| g4-a | 4.92 5.99 6.42 | 1033 passed | clean | no drift | exit 0 | 119 passed |
| g4-b | 5.76 5.58 6.09 | 1033 passed | clean | no drift | exit 0 | 119 passed |

Logs: `g4-a-*.log`, `g4-b-*.log`. The backend count rose from 965 to 1033 because main gained the live lane's tests.

**Lane-guard** (`lane-guard.log`, against `98ec875`): `OUT OF LANE: backend/nflpi/ingestion/service.py: owned by lane coaches`, 1 problem: the granted edit, nothing else.
