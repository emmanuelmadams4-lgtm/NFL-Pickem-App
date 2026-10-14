# CODEX WORK ORDER 2 — step 15 web, lane web: live scores on the game screen

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make the two "L5 the game screen" tests and both "L9 accessibility" tests in `apps/web/e2e/live.spec.ts` green without changing any test, and keep every other test green.

READ FIRST: `apps/web/AGENTS.md`; the frozen spec `docs/gauntlet/logs/step-15-web.md` section 2 (the state table, its rules, criterion L5, L9, L11); work order 1's result: `apps/web/components/live/state.ts` (`cardLiveState`), `useLive` and `startedGame` in `apps/web/lib/queries.ts`, the live block in `apps/web/components/week/game-card.tsx`.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE
* `apps/web/components/game/game-header.tsx`, `apps/web/components/game/game-view.tsx`
* `apps/web/components/live/**` (extend `state.ts`; one new component file at most)
* `apps/web/lib/queries.ts` only if `useLive` / `startedGame` need a wider parameter type for `GameDetail` (no behaviour change)
Nothing else. No new dependency, no API or schema change.

REQUIRED BEHAVIOUR (a started game that is not final; a game that is not started, or is final, renders exactly as today)

1. `game-view.tsx` calls `useLive([game])` once and passes the result down. Same hook, same rules as the board: no started game, no request.
2. Header, centre column: the state's label above the score, the same words as the card (`cardLiveState`; do not write the table twice). Score from the live reply only, away then home, club codes from the game, tabular numerals, no winner styling, secondary ink in S3 and S4. No score: "No live score right now" in the label's size in place of the figure (not the "VS" disc). The week's own scores are drawn only when the game is final.
3. The "In progress" chip is not rendered for a started game. The kickoff line under the header stays.
4. One block directly under the header (above the model's tiles), drawn only when the state has a chance line:
   * S5: the chance line, with a reason on each missing number: "KC to win now · ESPN 71% · Kalshi – · no fresh price"; "ESPN – · none right now"; both missing: "No live win chance right now".
   * S5 also: "Checked 20s ago" (shared `ago()` on the query's `dataUpdatedAt`, against `useNow()`), and the sentence "Kalshi is a prediction market. The figure is the price of a KC win, not this app's forecast." with the club the chances are stated for.
   * S4: "Last update 4m ago" / "No update yet". No chances, no "Checked", no Kalshi sentence.
   * S2, S3, S6: no block.
5. `WinSplit`: while the game is started and not final, its caption reads "Model win chance before kickoff. It does not change during the game." in place of today's caption (keep the backfill wording rule as it is for games not started). The tiles and their numbers do not change.
6. Screen readers: as on the card. The table's sentence once in an `sr-only` element, the visible label and score `aria-hidden`; the chance line's own sentence with the visible line `aria-hidden`. The existing "Score …" sr-only sentence is not also rendered for a started game. No `aria-live`, no `role="status"`, no `title`. `clock` is a text child only.
7. Design (`design.md`): existing tokens and utilities only; no new colour, animation, icon or chip style. No sideways scroll at 393 px and 320 px.

PROOF (the coordinator reruns all of it): `npm run typecheck`; browser `e2e/live.spec.ts`, `e2e/step2.spec.ts`, `e2e/phone-layout.spec.ts`, then the whole suite.

CONSTRAINTS: /ponytail: the smallest diff; reuse `cardLiveState`, add fields to it rather than a second function when the game screen needs the reasons. No test edits. You may run `npm run typecheck`. Do not build the web app, do not start a server or a browser, do not run pytest. Do not commit; report the diff file by file, each numbered item, and anything you could not do or had to decide.
