# CODEX WORK ORDER 2 — step 18j: design critic 1 fixes

Try 1 of 2. Baseline: the newest `lane/web` commit (WO1 is `3b0ffc9`). Read `reviews/design-1.md` (items 1, 2, 4-9)
and the amended spec at the end of `docs/gauntlet/logs/step-18j.md`. Red: run `s18j-red-2`, S1 fails at
`Expected substring: "<home abbr> margin"`; the other new assertions follow it.

ALLOWED FILES: `apps/web/components/game/simulation.tsx`, `apps/web/components/week/week-board.tsx`.

REQUIRED
1. Spread heading: "<home abbr> <signed spread>, the line the simulator used"; total heading:
   "Over/under <total>, the line the simulator used" (the phrase must be its own text in each heading's element).
2. Remove the extra `pt-4` (lines with `pt-4`; `Section` already pads, `components/ui.tsx:76`).
3. Week board: move the `pick_mode.label` line out of the `PageHead` `sub` into a `<p className="text-xs text-subtle">`
   placed right after `<PageHead …/>`, so the header row keeps its height on a phone.
4. The two percentage grids: `grid-cols-3` at every width.
5. Sub-headings `mb-2 text-xs font-medium` (as Market); the last line `text-[11px]`.
6. Margin fact label "<home abbr> margin" (value stays signed, home view).
7. Average score lists the home team first, then the away team (same order as the cover chances).
8. Range notes read "80% of runs: A to B" (margin signed, total unsigned, one decimal).
Nothing else; texts not named here stay word for word.

PROOF: `npm run typecheck`; the coordinator reruns `e2e/sim18j.spec.ts` and the full suite on a fresh build.
CONSTRAINTS: /ponytail; lines under 140 characters; no test edits; typecheck only; do not commit.
