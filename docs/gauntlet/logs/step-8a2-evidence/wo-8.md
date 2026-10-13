# WORK ORDER 8 — step 8a2, lane web: the card's stars line names one star in full (critic round 1, finding F1)

Builder: a Claude Sonnet subagent (Codex is out of credits; god's rule of 2026-10-13). Try 1 of 2.

GOAL: make these red checks green without changing any test, and keep every other test green:
* browser `apps/web/e2e/stars.spec.ts` ST1 and ST2 (phone and desktop);
* `backend/tests/test_api.py::test_week_board_says_which_stars_are_out_and_the_game_view_lists_all_of_them` (order of `stars_out.out`).
Why: `reviews/critic-1.md` F1. The work order 7 line cut names and statuses at 393 px and "+N more" understated what was hidden.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, commit `1d5faef`. Read `apps/web/AGENTS.md` first.

ALLOWED SCOPE: `apps/web/components/week/game-card.tsx`, `backend/nflpi/api/views.py`. Nothing else. No schema change, so `npm run gen:api` must produce no change.

REQUIRED BEHAVIOUR

A. API order (`views.summaries`, the `StarsOut.out` list)
1. `out` lists every star whose status is Out before every star whose status is Doubtful. Inside each status the order stays what it is now: clubs away first, each club's rows in list order. One stable sort on the status; no other change. The client does not sort.

B. Card (`game-card.tsx`), inside the `role="group"` named "Stars out", one line that never wraps, in this order:
2. `Stars out` label (never shrinks).
3. The FIRST star of `stars` (the list already without `qb_alert` rows) and only that one:
   * one element whose whole text is exactly `{team} {player}`, for example "KC Cory Corner". It is the ONLY part that may shrink: `min-w-0 truncate` (ellipsis). It must not grow past its text (no `flex-1`), so a short name is shown whole.
   * then his position (`text-subtle`, never shrinks), when there is one;
   * then his status as its own element whose whole text is the status word, in its tone colour as now (never shrinks).
4. `+N more` when `stars.length > 1`, N = `stars.length - 1`; its own element, exact text "+3 more"; never shrinks.
5. The age of the named star's report: its own element whose whole text is `ago(observed_at)`, for example "3h ago" (the word "seen" goes); never shrinks; nothing when `observed_at` is null.
6. For each club in `no_list`: its own element with the exact text `{club}: no list` (for example "MIA: no list"); never shrinks.
7. Remove what this makes dead (`shownStars`, the `latestSeen` reduce).
8. No stars: the standalone notes stay exactly as now. The page never scrolls sideways at 320 px.

PROOF (the coordinator reruns all of it): `cd backend && uvx ruff check nflpi tests`; `tests/test_api.py` and `tests/test_stars.py`, one file at a time, `DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test uv run pytest tests/<file> -q -p no:cacheprovider`; `npm run typecheck`; browser `e2e/stars.spec.ts` and `e2e/phone-layout.spec.ts` (coordinator only); then the full gate.

DESIGN (source: `design.md`): register product; existing tokens only; no new element type, icon, tooltip or `title` attribute.

CONSTRAINTS: /ponytail: the smallest diff. No test edits. You may run ruff, typecheck and the two single pytest files above (one at a time). Do not build the web app, do not start a server or a browser, do not run the full suite, no CPU-heavy loops. Do not commit and do not touch git state; report the diff item by item and anything you could not do.
