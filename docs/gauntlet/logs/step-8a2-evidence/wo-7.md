# CODEX WORK ORDER 7 — step 8a2, lane web: the gate's finding and the security reviewer's findings

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make these red checks green without changing any test, and keep every other test green:
* browser `apps/web/e2e/phone-layout.spec.ts` L1 (existing; red in `g1-a-e2e.log`: the first card's pick buttons end at 827 px, the limit is 778 px) and the new ST2 assertions in `apps/web/e2e/stars.spec.ts` (one line, "MIA: no star list"), and the new ST4 assertions ("No game status");
* `backend/tests/test_stars.py`: `test_game_stars_lists_every_star_of_both_clubs_with_his_status` (`listed`), the accent case of `test_a_star_with_no_id_is_matched_...`, `test_a_name_that_fits_two_reports_takes_the_exact_one_or_none`;
* `backend/tests/test_api.py::test_week_board_says_which_stars_are_out_and_the_game_view_lists_all_of_them` (`StarStatus.listed`).
Red log: `docs/gauntlet/logs/step-8a2-evidence/red-4.log`.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message. Read `apps/web/AGENTS.md` first.

ALLOWED SCOPE: `apps/web/components/week/game-card.tsx`, `apps/web/components/game/star-players.tsx`, `apps/web/lib/persist.ts`, `backend/nflpi/analytics/stars.py`, `backend/nflpi/api/schemas.py`, `backend/nflpi/api/views.py`, generated `packages/shared/openapi.json` and `packages/shared/src/api-types.ts` (`npm run gen:api`). Nothing else.

REQUIRED BEHAVIOUR

A. Card: the stars line is one line (owner decision D27: "a short who's-out line"; existing density rule L1)
1. In `game-card.tsx` the whole stars block becomes ONE line that never wraps, in this order, inside the `role="group"` named "Stars out":
   `Stars out` (label, never shrinks) · the names (takes the free width, `min-w-0 truncate`: one line, ends in an ellipsis when it does not fit) · `+N more` when more than three (never shrinks) · `seen {ago}` (never shrinks; the word "latest" goes) · for each club in `no_list`: `{club}: no star list` (never shrinks, `text-text-2`).
   Names keep the format "KC Cory Corner CB Out" with the status word in its tone colour, separated by the existing gap or a middle dot.
2. When there are no stars to show the standalone notes stay exactly as now ("No star list yet for MIA, LV" / "Injury report not in yet"), and there is no "Stars out" group.
3. When `no_list` is empty and there are stars but `reports_seen` is 0: cannot happen (a star needs a report); do not add code for it.
4. The page never scrolls sideways at 320 px; the line clips inside the card.

B. Offline cache (security review M1)
5. `apps/web/lib/persist.ts`: `VERSION = 2`. A phone holding a week saved before this step has no `stars_out`; the old cache must be dropped, not rendered.

C. Name matching (security review M3), `analytics/stars.py`
6. `_normal_name` also folds accents (NFKD, drop combining marks): "José" equals "Jose".
7. When a star or a report has no player id, the match by name is: a report on that club whose raw name equals the star's exactly wins; otherwise the normalised match counts only when exactly one report on that club fits; two or more fit: no match. An id on both sides still decides alone (existing test).

D. On the report, no game status (security review M4)
8. `game_stars` rows carry `listed: bool`: true when a report row of this week matched the star, whatever its game status. `StarStatus.listed: bool` in the API (`stars_out.out` rows are always true).
9. `star-players.tsx`: a star with `listed` true and no status shows "No game status" (`text-text-2`) instead of "Not on injury report". Nothing else changes there.

PROOF (the coordinator reruns all of it): `cd backend && uvx ruff check nflpi tests`; `tests/test_stars.py`, `tests/test_api.py` (one file at a time, `DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test`); `npm run gen:api` then no further drift; `npm run typecheck`; browser `e2e/stars.spec.ts` and `e2e/phone-layout.spec.ts`; then the full gate.

DESIGN (source: `design.md`): register product; existing tokens only; no new element type, icon, tooltip or `title` attribute (feed text never goes into an attribute). The primary action stays "tap a team to pick": the card must not grow by more than one text line because of stars.

CONSTRAINTS: /ponytail: the smallest diff. No test edits. Do not build the web app, do not start a server or a browser, do not run the full suite. Do not commit; report the diff, item by item, and anything you could not do.
