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
