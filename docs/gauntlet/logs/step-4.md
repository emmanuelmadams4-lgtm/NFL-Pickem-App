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
| S4-A3 | Correction A4 | gpt-6-sol / high | see below |
| S4-B | Web: label, points control, whose pick, copy sheet page, rank entry, scorecard | gpt-6-sol / medium | see below |

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
