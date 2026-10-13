# CODEX WORK ORDER 1 — step 15 web, lane web: live scores, the data layer and the game card

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make the card tests in `apps/web/e2e/live.spec.ts` green without changing any test: every test whose name starts with L1, L2, L3, L4, L6, L7, L8, L11, "S2 held", and L9 for the board. The two "L5 the game screen" tests and the game-screen half of L9 stay red: that is work order 2. Keep every other test green.

READ FIRST: `apps/web/AGENTS.md`; the frozen spec `docs/gauntlet/logs/step-15-web.md` section 2 (Words, the state table S1 to S6, the rules under it, criteria L1 to L11); the route contract `docs/gauntlet/logs/step-15d.md`; types `LiveOut`, `LiveGameOut` in `packages/shared/src/api-types.ts`.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE
* `packages/shared/src/client.ts` (add only: `live()` and `keys.live`; export the two types the way the file exports the others)
* `apps/web/lib/queries.ts` (add `useLive`), `apps/web/lib/persist.ts` (one filter)
* new files under `apps/web/components/live/` only
* `apps/web/components/week/game-card.tsx`, `apps/web/components/week/week-board.tsx`
* `backend/nflpi/api/views.py` (item F only)
Nothing else. `backend/nflpi/api/live.py` is another lane's: do not touch it. No new dependency. No API or schema change (`npm run gen:api` must produce no change).

REQUIRED BEHAVIOUR

A. Fetch
1. `api.live()` = `GET /live` returning `LiveOut`; `keys.live = ["live"] as const`.
2. `useLive(games)` in `queries.ts`, called once per screen with the games on that screen (the board passes the week's games). A game is **started** when its status is `in_progress`, or `isLocked`-style: `useNow()` has reached its kickoff and it is not `final`, not `postponed`, and `time_tbd` is false.
   * No started game: the query is disabled. No request at all (L1).
   * A started game: fetch at once; `refetchInterval` 30 000 ms while any started game is not in state S2, 120 000 ms when every started game is in S2; `refetchIntervalInBackground` false; `retry: false` (the next poll is the retry); no toast and no thrown error on failure.
   * A board left open across a kickoff starts polling without a reload (the hook reads `useNow()`).
3. The live reply is never merged into the week or game query data. `persist.ts`: queries whose key starts with `"live"` are not saved.
4. Ended rows are held for the session: when a good reply carries a row with `state: "post"`, remember it by game id; when a later good reply has no row for a game that is still started, that remembered row is used (S2). A module-level `Map` is enough; mark it with a `ponytail:` comment naming its ceiling (lives until reload).

B. State, one pure function (new file under `components/live/`)
5. One exported pure function turns (game, live query result, now) into what the table says: which of S2 to S6 applies (first match wins; S1 = the week says `final`: render nothing live), the label text, the score or its absence, the chance line or its absence, the screen-reader sentence. No JSX in it. The rules under the table are exact: period and clock words, "Halftime", "End of Q1/Q3/Q4", "OT", "2OT", "3OT", unknown clock text shown as it arrives, clock only with a period; chances for the model's pick, else my pick, else the home club; whole percents with "<1%" and ">99%"; away = 100 minus the rounded home figure; a null is never a number; no hold.
6. **Not updating** = `live.stale`, or the query's last good reply (`dataUpdatedAt`) is over 120 000 ms before `useNow()`. One failed request alone changes nothing. `updated_at` is not used for this. The reply's `stale` flag never changes an S2 game.
7. S6 also covers: the query has no data yet, or it failed and never had data.

C. The card (`game-card.tsx`), for a started game that is not final
8. In place of the date line: the label. In place of the kickoff time (and of the week's own scores, which are drawn only when the game is final): the live score, away then home, each with its club code taken from `game.away.abbr` / `game.home.abbr` (never from the live reply), tabular numerals (`tabular-nums`), no winner styling; S3 and S4 in the secondary ink (`text-text-2`). No score: the words "No live score right now" in the label's size, not in the display face.
9. The chance line is its own line placed after the row that holds "Uncertainty" and the market text, in `text-label`. Card wording for a missing number: "ESPN –" / "Kalshi –" (en dash); both missing: "No live win chance right now"; S4: "Last update 3m ago" (use the shared `ago()` on `last_confirmed_at`) or "No update yet".
10. Pregame words while started: "Model pick" reads "Pregame model pick", "Market" reads "Pregame line"; the hit-rate sentence (" · Easy picks have won 77% since 2012") and the "In progress" chip are not rendered. These depend on the game being started, never on the live reply.
11. Screen readers: the table's sentence, once, in an `sr-only` element; the visible label and score are `aria-hidden`. The chance line has its own sentence ("Right now ESPN gives KC a 71 percent chance to win; Kalshi price 68 percent.", leaving out a missing source) with the visible line `aria-hidden`. No `aria-live`, no `role="status"`, no `title` attribute anywhere in the live block. `clock` is rendered as a text child only.
12. Nothing else on the card changes: the model's pick and its percentage, the label word, points, pick buttons.
13. A live card is no taller than 400 px at 393 px and 320 px width with an upset watch, two QB alerts and a change note; no sideways scroll; the label and the chance line are never cut (they may wrap to a second line inside the 400 px).

D. Design (source `design.md`): register product; existing tokens and utilities only; no new colour, no animation, no pulsing dot, no icon, no new chip style. "Not updating" and "Ended" are words in the label; colour is never the only signal.

E. Carried from step 8a2 (same card): in `game-card.tsx` test `game.stars_out.no_list.length > 0` once (derive the note for the stars case once) and fix the indentation of the group div inside its wrapper. No behaviour change.

F. Carried from step 8a2: `backend/nflpi/api/views.py`: import `ALERT_STATUSES` use through the module like `stars.OUT_STATUSES` (one import style), and `_star_status`: a name that is empty after cleaning stays what the code does today (do not change behaviour; if you cannot do the import change in under five lines, leave F and say so).

PROOF (the coordinator reruns all of it): `npm run typecheck`; `cd backend && uvx ruff check nflpi tests`; `npm run gen:api` leaves no change; `backend/tests/test_api.py`; browser `e2e/live.spec.ts`, `e2e/stars.spec.ts`, `e2e/phone-layout.spec.ts`, then the whole suite.

CONSTRAINTS: /ponytail: the smallest diff that meets the table; no abstraction with one user beyond the pure function named above. No test edits. You may run `npm run typecheck` and ruff. Do not build the web app, do not start a server or a browser, do not run pytest or the full suite (the machine's test slot is shared). Do not commit; report the diff file by file, each lettered item, and anything you could not do or had to decide.
