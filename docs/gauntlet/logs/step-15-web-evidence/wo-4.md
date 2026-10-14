# CODEX WORK ORDER 4 — step 15 web, lane web: polish from the design and implementation critics

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: the accepted findings of three fresh critics (`reviews/design-ux-1.md`, `reviews/design-visual-1.md`, `reviews/impl-1.md`), nothing more. Make the failing tests in `apps/web/e2e/live.spec.ts` green without changing any test (red log `step-15-web-evidence/red-4.txt`): the "polish: …" test and the two "L5 the game screen: label above the score…" tests. Keep every other test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE: `apps/web/components/week/game-card.tsx`, `apps/web/components/game/game-header.tsx`, `apps/web/components/game/game-view.tsx`, `apps/web/components/game/recommendation.tsx` (item 1 only), `apps/web/components/live/state.ts`. Nothing else. Existing tokens and utilities only (`design.md`): no new colour, animation, icon or chip style.

REQUIRED CHANGES
1. Pick panel (`recommendation.tsx`): the "Live" chip (it means "a pregame prediction that is not backfilled") is not rendered while the game is started (`startedGame(game, useNow())`). The backfill chip stays.
2. "Not updating" is marked: in S3 and S4 the words "Not updating" at the start of the label are in `text-warn`, on the card and in the game header (one element with that class whose text starts with "Not updating"; the rest of the label keeps its ink). The words stay; colour is added, not swapped in.
3. The label is `text-sm` (card and game header); in S5 the word "Live" is in `text-text`. The rest keeps `text-text-2`.
4. Board card: the live card has the same padding as every other card (`p-3`; the `p-2` and `gap-1` variants go). If the 393 px height test (L8) then fails, use `gap-1.5` for the live card's body and say so.
5. Board card: while a game is started the pregame model figure (the "87%" under "Pregame model pick") is `text-xl` so the live score is the only large figure. Text unchanged.
6. Game header, phone: a no-break space between the period and the clock ("Q3 4:12", in `periodWords`, so the card gets it too), and the label keeps a fixed two-line height below `sm` (`min-h-10` with the text at the bottom, or the same effect) so the score does not move between states.
7. Game screen, the block under the header: no box. Plain lines, no border, no background, no padding of its own.
8. Screen readers:
   * card, S5 with both chances missing: "No live win chance right now" also has an `sr-only` twin (today the visible line is `aria-hidden` and there is none);
   * game screen, S4: the age line is not `aria-hidden` and has no `sr-only` twin (the header's sentence already says it): the text "Last update 4m ago" appears once in the DOM.
9. Board card: the "Stars out" / "No star list yet" / "Injury report not in yet" block is not rendered once the game is started (today it is keyed on `status === "scheduled"` only, so a game past kickoff whose status has not moved still shows it).
10. `WinSplit` caption while started keeps the backfill words: "Model win chance before kickoff, backfilled after the fact from pre-game inputs. It does not change during the game." for a backfill prediction; unchanged otherwise.

NOT TO DO (decided): no chip for "Ended"; no "Live:" prefix; no change of the chance line's words or place; no visible "Score may be out of date"; no clearing of `heldPosts`.

PROOF (the coordinator reruns it): `npm run typecheck`; browser `e2e/live.spec.ts`, `e2e/phone-layout.spec.ts`, `e2e/step2.spec.ts`, then the whole suite; screenshots.

CONSTRAINTS: /ponytail, the smallest diff. No test edits. `npm run typecheck` only: no build, server, browser or pytest. Do not commit; report each numbered item and anything you had to decide.

---
## Work order 4b (try 2 for item 4): the live card at normal padding must still keep the 400 px limit at 393 px

FAILING EVIDENCE: `live.spec.ts` "L8 phone fit at 393 px": 476 px (limit 400) after item 4 (`green-7`, `green-8`; picture `~/.claude/plans/nfl-pickem-lanes-logs/step-15-web/l8-393.png`). Cause, seen in the picture: on a locked card the row "Points [select] (lock) Locked" plus the two pick buttons is 8 px too wide at `p-3`, so the buttons drop to their own row. The earlier `p-2` hid it. The word "Locked" is on the card twice (beside Points and under the pick buttons).

ALLOWED SCOPE: `apps/web/components/week/points-control.tsx` only.

REQUIRED: beside the points select of a locked game keep the lock icon; the word "Locked" there becomes `sr-only` (the pick buttons' own "Locked" line stays visible). Nothing else changes; the unlocked card is untouched. Do not go back to `p-2`.

PROOF (coordinator): typecheck; `live.spec.ts`, `phone-layout.spec.ts`, `step2.spec.ts` (its "Locked" check must stay green), `sheet.spec.ts`.

CONSTRAINTS: as work order 4. If this does not bring the row back onto one line by your reading of the classes, say so instead of trying other changes.
