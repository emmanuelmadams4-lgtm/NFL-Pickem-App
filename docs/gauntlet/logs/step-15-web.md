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
* **L5 the game screen.** The header's centre column shows the label above the score; the "In progress" chip is not shown; the kickoff line stays. One block under the header shows the chance line with reasons for a missing number ("ESPN – · none right now", "Kalshi – · no fresh price"), "Checked 20s ago" (time of the web's last good reply), one sentence saying what the Kalshi number is ("Kalshi is a prediction market. The figure is the price of a KC win, not this app's forecast."), and one caption on the model's tiles ("Model win chance before kickoff. It does not change during the game.").
* **L6 never moves a pick.** With a started game and any live reply, the model's pick and its percentage, the sheet label word, the points and the pick buttons' state are what they are without the live reply.
* **L7 it ends.** When the week data turns `final` the live block is gone and polling for that game stops.

User-facing
* **L8 phone fit.** At 393 px and 320 px: no sideways scroll; a live card is no taller than 400 px with the worst case on it (three-letter clubs, two-digit scores, an upset watch, two QB alerts, a change note); nothing in the live block is cut.
* **L9 accessibility.** No serious or critical axe finding (dark and light) with a live game on screen; the table's sentence is the only thing a screen reader gets for the label and score (visible parts hidden from it); "Not updating" and "Ended" are words, not colour alone; no live region.

Operational
* **L10 failure is quiet and honest.** `/api/live` answering 401, 503 or not at all gives S6 when nothing was shown before, and S4 once the last good reply is over 120 seconds old; no error toast, no crash, and the next poll still happens.
* **L11 no feed text in an attribute.** `clock` and club codes from the live reply are rendered as text only.

Not in this step: a weather or other delay cannot be told from period and clock (the server would have to pass ESPN's status text): carried to the integrator. Play-by-play, a chart, alerts, in-game grading (15f).

Gate: `docs/gauntlet/logs/step-15-web-evidence/gate.sh <label>` (pytest, ruff, `gen:api` no drift, typecheck, the whole browser suite), twice, under `res:gate` and `res:e2e`.
