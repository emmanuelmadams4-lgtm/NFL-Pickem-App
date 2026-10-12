# Step 4 of 14: Pick sheet

Session: owner's Mac, 2026-10-12, `DIRECT_COORDINATOR / ONE_SHOT`. Branch `claude/step-4-pick-sheet`
from `main` `4df2622` (+ D42 docs). Builder: Codex (Build Ladder). Coordinator: Claude Opus 5.5.

## 1. PLANNING

**In the owner's words.** This step builds what he asked for on 2026-10-12: for every game the app
picks the winner, says if it is an *easy pick*, a *tough matchup* or a *coin flip*, and gives
*confidence points* from 1 up to the number of games, the most points on the surest pick. He can
change any winner or any number. It replaces the plain "pick a winner" card. It is not: predicted
scores (step 9), phone alerts (step 7), or the Claude chat (step 11).

* **Rigor tier:** T3 (new tables, changes what a pick is).
* **Skills:** `/graft`, `/jevgrep`: N/A, the seams were located by direct reads of `api/views.py`,
  `api/main.py`, `models.py`, `analytics/backtest.py`, `jobs.py` (named in § 2). `tdd`: red tests
  first (§ 2). `/ponytail`: in every work order. `harness-engineering`: N/A (no runner or approval
  boundary changes). Design Gauntlet: applies to the web work order (§ 3). `jev`: loaded this session.
* **Pre-flight.** Problem: his Yahoo league scores confidence points, the app gives only a winner.
  Why now: owner asked ("we forgot ... the confidence points"), week 6 opens Thursday. Scope: sheet
  on the Week screen, copy sheet, rank entry, scorecard; cut: tiebreaker scores, Claude's written
  check. Success metric: his league rank (D13), read from the weekly rank entry; guardrail: points
  per week vs the app's untouched sheet. Reversibility: two-way (additive tables).
* **Instrumentation ships here:** the scorecard and rank entry are the instrument. Baseline from
  data (`s4-label-cuts.log`, 2012-2025, 243 weeks): ranking by win chance earns 86.9 points a week
  of 120.8 possible (71.9%); a random order of the same picks earns 80.3 (66.4%).

### Owner decision added in this session

| # | Decision | Door | Revisit when |
|---|---|---|---|
| D43 | Owner, his words: "we could use jev to rank and give the confidence points first and have claude verify". Offered three ways, he chose: **win chance sets the order; Jev breaks near-ties; Claude checks.** Also chose: build step 4 on the Mac, now. | two-way | the scorecard shows Jev's swaps cost points |

### Assumptions

| Assumption | State |
|---|---|
| Yahoo uses 1..N and a tie scores zero | validated (help.yahoo.com, decisions file "Facts") |
| Label cuts 55% / 67% separate cleanly | validated: coin flip 52.4% (519 games), tough matchup 59.6% (1,483), easy pick 77.0% (1,647); same order in 2012-2021 and 2022-2025 |
| "Near-tie" can be a few points wide | **wrong, changed:** at 2 points there are 8.3 neighbour pairs a week (most of the sheet). Band set to **1 point** so Jev can only swap picks that are effectively equal |
| Claude can check the sheet now | **no:** the app has no working Claude connection until step 11 (D32). In this step the rule check is code (always on); Claude's written check lands with step 11. Told to the owner in the report |
| Yahoo's game order on its pick screen | unknown: the copy sheet uses kickoff order |

### Design (settled by the coordinator; two-way doors)

* Open games are never stored: his sheet and the app's sheet are computed from the latest
  prediction, his picks and his hand-set points. So nothing can drift.
* A game is written down once, when it kicks off (`sheet_entries`, never edited): the app's pick,
  win chance, label and points, and his pick and points. No pick from him = an `auto` pick (D11).
* Points with no hand-set number follow the win chance of **his** side, so picking an underdog
  drops that game down his sheet by itself.
* Jev runs in the worker's refresh, never in a page request, is cached per prediction, and the
  sheet works unchanged when Jev is down.

## 2. SPECIFICATION (frozen 2026-10-12)

Gate file: `backend/tests/test_sheet.py` (21 tests) + the changed A12 migration test. Red evidence:
`s4-red.log` ("cannot import name 'sheet'": the feature does not exist), old suite 56 pass, 1 fail
(A12 now expects migration `0002`). Baseline before the spec: 57 passed, ruff clean
(`s4-baseline-pytest.log`).

| # | Criterion | Layer | Test |
|---|---|---|---|
| S1 | Label = coin flip under 55%, tough matchup 55 to under 67%, easy pick from 67%, of the pick's win chance. Backtest reports games and hit rate per label. Each label carries its measured hit rate | functional | `test_label_is_three_steps...`, `test_backtest_reports...`, real numbers in the gate log |
| S2 | Every game in a week: app pick, label, points 1..N unique, highest on the surest. Untouched: his sheet = the app's. Postponed: no points, N shrinks | functional | `test_every_game_gets...`, `test_postponed...` |
| S3 | His side's win chance orders his sheet: picking the underdog drops the game; the app's sheet does not move | functional | `test_picking_the_underdog...` |
| S4 | Setting a number swaps with the game that had it; both become his; `differs` shows where he and the app disagree; clearing gives the game back; outside 1..N is refused | functional | `test_setting_points_swaps...`, `test_hand_set_points_stay...`, `test_clearing...`, `test_points_outside...` |
| S5 | A started game keeps pick, label and points for both sheets; open games re-rank over the numbers left; no number moves onto or off a started game (409) | functional | `test_a_started_game_keeps...`, `test_points_cannot_move...` |
| S6 | Untouched at kickoff = `auto` pick with the app's pick and points, written by a page view or by the worker tick; his own pick is never marked auto | functional | `test_a_game_he_never_touched...`, `test_the_worker_tick...`, `test_his_own_pick_is_kept...` |
| S7 | Auto picks are scored apart from his own in Results | functional | `test_auto_picks_are_scored_apart...` |
| S8 | Scorecard per week: his points, the app's points, max, picks changed and whether the change was right, auto count, his rank and the leader's points; by label; a tie scores zero | functional + operational | `test_scorecard_compares...`, `test_a_tied_game...`, `test_rank_entry_refuses...` |
| S9 | Jev: order by win chance; a neighbour pair within `TIE_BAND` (1 point) swaps only if Jev scores the lower one's evidence a full level stronger with confidence 0.8+ on both; asked once per change, one `score` question per game, never asked with no near-tie; Jev down changes nothing | functional | `test_order_is_by_win_chance...`, `test_jev_is_asked_once...`, `test_jev_is_not_asked...` |
| S10 | Migration `0002` adds the tables explicitly; `alembic check` clean | operational | A12 (changed) |
| S11 | API contract regenerated, no drift; typecheck and build pass | operational | `npm run gen:api`, `typecheck`, `web:build` |
| U1 | Week screen: each game shows the label, the points with a way to change them, and whether the pick is his, the app's or auto; started games show as locked | user-facing | e2e |
| U2 | "Copy to Yahoo" sheet: games in kickoff order with winner and points, one button copies it as text | user-facing | e2e |
| U3 | Results: rank entry for the week and the scorecard table | user-facing | e2e |
| U4 | axe: 0 serious or critical on the changed screens; existing e2e stays green; design critic PASS | user-facing | e2e + critic |

Not in this step (named so nobody assumes them): tiebreaker scores (step 9), Claude's written check
of the sheet (step 11), alerts when a label changes (step 7).

### Spec amendments after the first build (coordinator's faults, found in review; not builder failures)

| # | What was wrong in the spec | Change | Test |
|---|---|---|---|
| A1 | The tests "kicked off" a game by moving its time into the past, leaving no prediction before kickoff. Codex added a fallback that accepted a later prediction, which breaks the "last snapshot before kickoff" rule | The test helper now also backdates that game's predictions; the fallback was removed (WO-A2) | all lock tests |
| A2 | Nothing stopped the sheet from writing down every past game in the database and inventing an "auto" pick for each | A game is written only if it is not final yet, or it kicked off after the sheet's first run (`app_settings.sheet_start`). Old games show no points | `test_games_played_before_the_sheet_existed...`, `test_a_game_that_started_and_ended_while_nobody_looked...` |
| A3 | A week with a rank but no finished games was left off the scorecard, so a rank he just typed would not show | Such a week is listed with zeros | `test_a_week_with_a_rank_but_no_finished_games...` |
| A4 | Games that kick off in the same minute were written one at a time, so the first took the highest number left (would scramble the Sunday 1:00 slate) | While one is written, the others of the same pass still count as open (WO-A3) | `test_games_that_kick_off_together...` |

Gate after amendments: `backend/tests/test_sheet.py` 34 tests.

## 3. IMPLEMENTATION

Provider: CODEX. `JEV: model for WO-A → sol (0.53, astra 0.31); effort → high (0.87)`. Astra needs the
owner's yes, so sol at high is the only allowed start. `CLIMBS: none`.

| WO | Scope | Model / effort | Result (coordinator's own rerun) |
|---|---|---|---|
| S4-A | Backend: labels, tables + migration 0002, sheet module, Jev client, points / rank / scorecard API, auto picks in Results | gpt-6-sol / high, try 1 | 87 passed, ruff clean (`s4-wo-a-pytest.log`). Review found A1, A2, A4 above |
| S4-A2 | Corrections A1-A3 | gpt-6-sol / high | 90 passed, ruff clean (`s4-wo-a2-pytest.log`) |
| S4-A3 | Correction A4 | gpt-6-sol / high | 91 passed, ruff clean (`s4-impl-pytest.log`) |
| S4-B | Web: label, points control, whose pick, copy sheet page, rank entry, scorecard | gpt-6-sol / medium | typecheck and build pass; Codex could not launch a browser. Coordinator's e2e: 42 of 47 (`s4-e2e-2.log`) |
| S4-B2 | Scorecard table: phone overflow, keyboard-reachable scroll region | gpt-6-luna / low | e2e 45 of 47 (`s4-e2e-3.log`) |
| S4-B3 | One class: the scroll region contains its screen-reader-only spans (cause found with a browser probe) | gpt-6-luna / low | e2e **47 of 47** (`s4-e2e-4.log`) |

Live Jev check (one real call through `nflpi.ai.jev.decide`, `s4-jev-live.log`): a clean 71% pick scored 2.91
(confidence 0.92), a 70% pick with a QB change and stats/line disagreement scored 0.15 (0.85). Request and
answer shapes match the code; the near-tie swap fired as designed.

### Design brief (web work order)

Register: product (Operate). Character: dense, quiet, scannable; the step 3 look (design.md § 0), no new
colours or type sizes. Bar: owner references 01 (ESPN pick row) and 03 (Yahoo confidence number per game).
The label replaces the old "Strong favorite / Toss-up" words (one vocabulary, his). Points are a native select
(reachable, 48px on the phone) with the number repeated large; "Your number / App says N" in words, never
colour alone; lime stays "mine", so an untouched game shows no lime pill and names the app's team in text.
States covered: open, his number, locked, auto pick, no points (postponed / old game), loading, error, offline.
"Before" evidence: step 3's screenshots in `docs/gauntlet/logs/step-3-evidence/`.

Browser gate notes. The test browser was not on this Mac (the cloud session had its own); the owner said yes
to downloading Playwright's Chromium build 1194 (81.7 MiB). First real run: 42 of 47. The five failures:
four were the scorecard table on the phone (builder's, fixed in B2/B3); one was the coordinator's spec
(U1c picked the game with no kickoff time, which by rule never locks from its placeholder), fixed in the spec.
`gen:api`: no drift. `npm run typecheck`: pass.

## 4. CLEANUP

Scope-locked `/refactor` pass through Codex (WO S4-C, gpt-6-luna / medium), no behaviour change:

* one `_chance` helper replaces five copies of "win chance of a side";
* `compute_week` 59 -> 42 lines, `refresh_tiebreaks` 50 -> 31 (Jev request text and criteria moved out);
* `set_points` reuses the rows it already has for N;
* the label and its hit rate no longer run together on the card: the label is a chip, the hit rate is its own text.

Left as is, with reasons: `sheet` imports `is_locked` from `api.views` inside functions (a module-level import
would be circular; moving `is_locked` is step 13's layering work). `finalize` is 42 lines (under the 50 limit).

After cleanup, on commit `29b14b4`: pytest 91 passed (`s4-cleanup-pytest.log`), ruff clean, typecheck pass,
e2e 47 passed (`s4-e2e-5.log`). Real-data backtest (`s4-backtest-real.log`, 3,649 games): coin flip 14.2% of
games, 52.4% right; tough matchup 40.6%, 59.6%; easy pick 45.1%, 77.1%; same order in 2012-2021
(51.4 / 58.3 / 77.2) and 2022-2025 (54.8 / 62.6 / 76.7). Market 66.57%, blend 66.46%: unchanged from step 1.

## 5. VERIFICATION

### 5.1 Design critic, round 1: FAIL (no blocker, ten majors)

Fresh subagent, read-only, given the screenshots, design.md and the frozen criteria. Report:
`~/.claude/plans/nfl-pickem-intelligence-reviews/s4-design-critic-1.md`.

| # | Finding | Fix (work order S4-D) |
|---|---|---|
| M1 | Board said "3 still open to pick" while the sheet listed 4 picks | Card says "Counts as X, the model's pick, unless you tap a team."; the tile says "N yours, M model picks" |
| M2 | Three names for one thing (Model pick, App pick, Auto pick) | One word everywhere: the model |
| M3 | After kickoff the chip did not name the team | "Model picked X for you" |
| M4 | "Won 77% of the time" had no subject | "Easy picks have won 77% since 2012" |
| M5 | Label chip sat on the Uncertainty row | Label is plain words under the win chance |
| M6 | Points shown twice | One labelled select |
| M7 | The swap was silent | One toast naming both games |
| M8 | A game without points vanished | "No points yet" row; "N of M games have points" on the sheet |
| M9 | Sheet had no column labels or width cap | Game / Pick / Points header, max width, whose pick on each row |
| M10 | Phone scorecard scrolled sideways | Stacked rows under 640px; table first, rank form after |

Spec change, said openly: `apps/web/e2e/sheet.spec.ts` was edited by the coordinator for the new words only
("the model's pick", "Model says", "Use the model's number", "Yahoo sheet", column "Model") and two added
checks (the swap toast, "Rank saved"). No check was removed or weakened.

Coordinator edits after work order S4-D (small, said openly): the points row is hidden for a locked game from
before the sheet existed; the "back to the model's number" message reads the number from the server's answer;
the reserved line under the select applies from `lg` up only; the board tile counts only games that really
follow the model; the phone scorecard is a `<dl>` axe accepts; the phone tile reads "Yours"; an empty scorecard
says "No finished games on your sheet yet." Commits `d7b9570`, `cd25163`.

### 5.2 Objective critic, round 1: FAIL (one high, six medium) on `29b14b4`

Gates it ran: pytest 91 passed, ruff clean, typecheck clean, gen:api no drift, e2e 47 on a clean archive;
one in-repo run had E4 (a step 2 test with a 1 second clock margin) fail once, not reproduced in 6 repeats.

| # | Finding | Outcome |
|---|---|---|
| H1 | A malformed Jev answer was stored and made every week page fail | Fixed: only finite numbers are stored or read; test added |
| M1 | Tie-break spent the daily AI cap with no key; re-asked games Jev left out | Fixed: no call without a key; every asked game is cached by its inputs hash; tests added |
| M2 | "Best possible" wrong for a week in progress | Fixed: the sum of the points he had on finished games; test added |
| M3 | Postponement after a lock can leave a locked number above N | Accepted limit: a locked number is never rewritten; the open games still get unique numbers. Revisit if it happens in a real week |
| M4 | Evidence for the model's side used where he picked the other side | Fixed; test added |
| M5 | No test failed if evidence never reached the sheet | Fixed: a test now shows the swap in the API and that a stale hash is ignored |
| M6 | Export showed auto picks as his; a backfill prediction could become a sheet entry | Fixed: blank in the export; `finalize` skips backfill; tests added |
| L1 | `sheet_start` first insert race | Fixed: insert on conflict do nothing |
| L2 | Game page and export do not run `finalize` | Left: the worker tick and the week view do, within one tick |

Amendment A5 (spec faults of mine, tests added before the fix, commit `8284694`, "test: step 4 amendment
A5, red"): nine tests red, then green in `ff9396a` (Codex gpt-6-luna, work order S4-E; the number check was
folded into one helper by the coordinator). The existing Jev test now marks Jev as configured; no assertion
was removed. Admitted gap: `apps/web/e2e/sheet.spec.ts` first appeared in the implementation commit, so the
browser checks have no red-first commit.

Gates on `cd25163`: pytest 99 passed, ruff clean, typecheck clean, gen:api no drift, e2e 47 passed twice in a row.

### 5.3 Round 2 (on `cd25163`)

- Objective critic (fresh): PASS. Its own gate run: pytest 99, ruff clean, typecheck clean, gen:api no drift,
  e2e 47. It mutated a scratch copy and saw the H1, M1, M4, M5 and M6 tests fail as they should. Left one medium
  (the points dropdown offered fewer numbers than the server's 1..N when a game held no number) and one low.
- Design critic (fresh): FAIL, one major (N1: the phone scorecard printed 0 where the table shows a dash, and
  dropped the leader's points) plus minors. M1-M10 confirmed fixed.
- Fixes, commit `c5435db`: dropdown range counts every game that is not postponed (the server's N); the phone
  scorecard rows use the table's rules; "Rank saved" carries its icon; "Picked for you" on a final game the
  model picked; no label without its select; "Yahoo sheet" in the sheet page's kicker.

### 5.4 Round 3 (on `c5435db`, the commit that lands)

| Check | Result |
|---|---|
| Coordinator gates | pytest 99 passed, ruff clean, typecheck clean, gen:api no drift, e2e 47 passed twice in a row |
| Objective critic (fresh, clean archive) | PASS: same numbers; no critical, high or medium |
| Design critic (fresh, 16 screenshots) | PASS: no blocker, no major |
| Jev, Job 4 | review passed 0.92, open items stated honestly 0.91 (bar 0.8) |

Screenshots: `~/.claude/plans/nfl-pickem-intelligence-reviews/s4-shots-r3/`. Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/s4-*`.

Carried forward, not fixed (for the dashboard step unless the owner wants them sooner):
- Scorecard dashes have no visible footnote; zeros sit beside dashes when nothing is finished.
- The phone tile shows "0/4 Yours" without the model-pick count.
- With one week, the phone Total block repeats that week.
- A locked points select keeps its outline.
- Nothing says a higher number means a surer pick.
- The Yahoo sheet does not mark numbers he set by hand.
- About 40px of empty space under the points select on desktop.
- A postponement after another game has locked can leave a locked number above N (accepted limit).
- The game page and the export write down a started game only at the next worker tick.
- A phone card is about 530px tall (owner decision D40; density belongs to the dashboard step).
- Step 2's lock test (E4) has a 1 second clock margin and failed once in an early run.
- Claude's written check of the sheet waits for step 11 (no Claude connection yet).

No durable change to `design.md`.

## 6. LANDING

Pushed and PR opened under the owner's standing yes. Merge to `main` needs the owner's yes.
