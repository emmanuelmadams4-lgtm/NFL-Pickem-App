# CODEX WORK ORDER 1 — step 18j: score simulator on the game page, pick mode on the week board

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message (on origin/main `60833f4`).

GOAL: the six tests in `apps/web/e2e/sim18j.spec.ts` pass (S1-S6). The spec is section 2 of
`docs/gauntlet/logs/step-18j.md`; read it and the test file first. Red run `s18j-red-1`: all six fail because there is
no `#simulator` section and the board does not show the pick-mode label.

ALLOWED FILES (nothing else):
- new `apps/web/components/game/simulation.tsx` (one `SimulationSection` component)
- `apps/web/components/game/game-view.tsx`: add `{ id: "simulator", label: "Simulator" }` to `SECTIONS` right after
  "market", and render `<SimulationSection game={game} />` right after `<MarketSection game={game} />`
- `apps/web/components/week/week-board.tsx`: show `data.pick_mode.label` word for word, one small line under the week
  heading (in the `PageHead` `sub`, after the season line, `text-xs text-subtle`, its own line)

REQUIRED (`SimulationSection`, data from `game.prediction?.simulation`; types from `@nflpi/shared`, no new type file):
1. `<Section id="simulator" title="Score simulator" note={...}>` using the existing `Section` from `@/components/ui`.
   The note is the server's `simulation.label` word for word; with no simulation the note is omitted or generic.
2. No simulation (`null` or no prediction): one line "No simulation for this game yet." and nothing else.
3. With one: a first line "Shown only: not a pick, and it does not change the pick above." Then a `<dl>` of facts in the
   `Fact` style of `components/game/market.tsx` (copy that small pattern; do not import from market.tsx):
   - "Average score": `<away abbr> <away_points>` and `<home abbr> <home_points>`, one decimal each, two lines.
   - "Home margin": `expected_margin` signed with one decimal ("+3.1", "-2.0"), and below it a small line
     "80% of runs between <margin_80[0]> and <margin_80[1]>", both signed, one decimal.
   - "Total points": `expected_total`, one decimal, and "80% of runs between <total_80[0]> and <total_80[1]>",
     one decimal, unsigned.
4. Against the spread: if `home_spread` is null, "No spread yet." Otherwise a heading line "<home abbr> <signed spread>"
   ("Pick'em" when 0; one decimal only when the number has one, e.g. "-3.5", "+3"), then three facts:
   "<home abbr> covers" `home_cover`, "<away abbr> covers" `away_cover`, "Push" `spread_push`, each `pct(x, 0)` from
   `@nflpi/shared`.
5. Over/under: if `total` is null, "No total yet." Otherwise "Over/under <total>", then "Over" `over`, "Under" `under`,
   "Push" `total_push`, each `pct(x, 0)`.
6. Last line, small: "Based on <n_simulations, with a thousands separator> simulated games."
7. Never the words "lock", "guaranteed" or "bet"; no colour that suggests a pick (no accent/good/bad tones); existing
   text tokens only. No prediction maths in the client: only formatting of what the API sends.
8. Layout: the facts wrap in a two-column grid at phone width (`grid-cols-2`, `sm:grid-cols-3` or `sm:grid-cols-4` as
   fits), no sideways scroll at 320 px.

STYLE: match `components/game/market.tsx` (same structure, naming, Tailwind tokens). Keep lines under 140 characters;
break long JSX over several lines like that file. /ponytail: smallest working diff, no helpers file, no abstraction for
one use.

PROOF: `npm run typecheck`; the coordinator reruns `e2e/sim18j.spec.ts` and the full browser suite on a fresh build.
CONSTRAINTS: no test edits (if a test looks wrong, say which and why); typecheck only: no build, no server, no browser,
no pytest; do not commit; no backend or `packages/` change. Report per item.
