# CODEX WORK ORDER 4 — step 8a2, lane web: design review fixes (round 1)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: fix the accepted findings of the three design reviews (`docs/gauntlet/logs/step-8a2-evidence/reviews/ux-critic-1.md`, `visual-critic-1.md`, `impl-critic-1.md`; finding ids in brackets below). Make the new red checks green without changing any test: `backend/tests/test_api.py::test_a_star_quarterback_named_in_the_qb_alert_is_marked_by_the_api_whatever_the_spelling` and the new assertions in `apps/web/e2e/stars.spec.ts` (ST1 club prefix, ST2 "No star list yet for MIA", ST4 headings). Every other test stays green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message. Read `apps/web/AGENTS.md` first.

ALLOWED SCOPE: `backend/nflpi/api/schemas.py`, `backend/nflpi/api/views.py`, `backend/nflpi/analytics/stars.py` (only if the matched report row must be passed out), generated `packages/shared/openapi.json` and `packages/shared/src/api-types.ts` (`npm run gen:api`), `apps/web/components/week/game-card.tsx`, `apps/web/components/game/star-players.tsx`, `apps/web/components/game/injuries.tsx`. Nothing else: no test file, no `globals.css`, no new dependency, no new token.

REQUIRED BEHAVIOUR

API
1. [I1, I2] `StarStatus.qb_alert: bool`: true when this star's matched injury-report row is one that produces a `qb_alerts` entry for the game (the row's position is "QB" and its status is an alert status). Decide it from the matched row (the id, else the normalised name), never by comparing display text. False for every other star, in `stars_out.out` and in `GameDetail.stars`.
2. [I2] `qb_alerts` keeps its content and wording; entries for a star quarterback come first (stable otherwise), so the two alerts the card shows always include him.

Week board, `game-card.tsx`
3. [I1] Leave a star out of the "Stars out" line when `star.qb_alert` is true. Delete the string-prefix match.
4. [U2, I7] Each star is prefixed with his club: "KC Cory Corner CB Out".
5. [U1, V12, I3] The quiet notes show also when stars are listed: `no_list` not empty gives "No star list yet for MIA" (clubs joined with ", ", API order); else `reports_seen` 0 gives "Injury report not in yet". They stay inside the same block as the stars line; when there are no stars to show there is still no `role="group"` named "Stars out".
6. [U8, V8] The age sits on the label line: "Stars out · latest seen 3h ago", then the names. A long name wraps; no truncation.
7. [V7] On the card a star's status is plain text in the tone colour the chip would use (existing tone text classes), not a chip. The chips of the QB alert and the other flags stay.
8. [I13] React key `${team}-${slot}-${rank}`.

Game screen, `star-players.tsx` and `injuries.tsx`
9. [U4, V1, I4] The existing per-club injury lists get their own `h3` "Full injury report", level with "Star players"; the "Report as of ..." note moves directly under that heading. Club names under both headings are `h4` (same look as now).
10. [U5, V2, I5] A star's status uses the same lowercasing `statusTone` chip as the injury list (export it from `injuries.tsx` or move it beside `Chip`; one copy). "Questionable" looks the same in both lists.
11. [U6, V4] Drop the slot word (QB, Offense, Defense) from the row; the position carries it. When `position` is null, show the slot word in its place.
12. [V3] "Star list from week N" sits inline after the club name, as "0 listed" does in the injury header.
13. [U7, V6] A club with no star list: one plain quiet line "No star list yet" under its name, no dashed box.
14. [V10] "Not on injury report" and the en dash are `text-subtle`. [I9] The en dash carries an `sr-only` "Not known yet".
15. [I6] The status on the right may wrap: no `shrink-0`; long text breaks instead of squeezing the name.
16. [I10, I11, I14, I15] No empty detail line when a status has neither injury nor `observed_at`; an empty `stars` array is treated as no list; one text-size token for small text in the file; `club?.stars_week != null`.
17. [V11] The star block uses the section's existing vertical gap.

NOT ACCEPTED (do not build): per-club "report not in" (U3: when the week's report holds one club of the game it holds both; a club with no entry is truly not on it); totals or folding the QB into the stars line (U9, V9); moving a note to a tooltip (V5); `aria-labelledby` and `ul` on the card line (I8); helpers moved to `@nflpi/shared` (I12).

FAILING EVIDENCE: `docs/gauntlet/logs/step-8a2-evidence/red-3-api.log`; the browser assertions are red by reading (no club prefix, no "for MIA", no "Full injury report" heading in the current code); the coordinator runs the browser proof.

PROOF (the coordinator reruns all of it): `cd backend && uvx ruff check nflpi tests`; `DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test uv run pytest tests/test_api.py tests/test_stars.py -q -p no:cacheprovider` (one file at a time); `npm run gen:api` leaves no further drift; `npm run typecheck`; browser `e2e/stars.spec.ts`.

DESIGN (source: `design.md`): register product; near-black, lime accent only for the primary action; existing tokens and components only (`Chip`, `text-subtle`, `text-label`); no new card, box, icon or pill. Missing data is said in words, never left blank.

CONSTRAINTS: /ponytail: the smallest diff that does the above; delete what item 3 makes dead. No logic in the client beyond filtering on the flag and formatting. Do not build the web app, do not start a server, do not run the full suite or a browser. Do not commit; report the diff.
