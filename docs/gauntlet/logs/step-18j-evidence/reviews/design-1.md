# Design critic 1 — step 18j (fresh, read-only), on 3b0ffc9 screenshots

Screenshots: `~/.claude/plans/nfl-pickem-lanes-logs/step-18j/{before,after}-*.png`.

**Step 18j design critique: one MUST, then SHOULDs.** There is one blocker and a few clear fit problems. The section never reads as a pick: it uses no lime, gives no team any emphasis, and opens with "Shown only: not a pick".

I couldn't find `docs/design/design.md` in the worktree. Only copies under `docs/gauntlet/logs/*-evidence/` exist, so I judged against `market.tsx` and the `Section` component.

**Ranked defects**

1. **MUST: two different lines on one page, and the simulator's has no source.** At 1280 and 393, Market shows Spread **LV -3**. The simulator heading below it says **LV -3.5**. A reader sees two spreads with no explanation. This breaks "numbers the app cannot back are labelled".
   - File: `apps/web/components/game/simulation.tsx` lines 59-61 and 76.
   - Smallest fix: if the server sends the line's source, show it in the heading (e.g. "LV -3.5, line used by the simulator"). Otherwise feed the simulator the same latest line Market shows. If the gap is only fixture data, check the fixture and say so in the evidence.

2. **SHOULD: the gap under the section heading is doubled.** `Section` already wraps its children in `pt-4` (`apps/web/components/ui.tsx:76`), and `simulation.tsx` adds another `pt-4` on lines 30 and 32. The result is about 40px between the rule and the content, against about 24px in Market. The section looks detached in both screenshots.
   - Fix: remove `pt-4` from lines 30 and 32.

3. **SHOULD: the title is repeated in the note.** "Score simulator" is followed by "Score simulator, football-only inputs: …". Add the "Shown only…" sentence and you get three lines of preamble before the first number.
   - Fix: drop the leading "Score simulator, " from the server label. If the label must stay verbatim, strip that prefix on the client before passing it as `note`.

4. **SHOULD: on the phone, the board line pushes the Yahoo sheet button down.** Before the change, the button sat beside "2023 · 4 games". After it, the pick-mode line wraps to two lines, the head wraps, and "Yahoo sheet" drops to its own row. Everything below moves down about 88px, and the first card's pick buttons fall below the fold. At 1280 the button only moves about 16px, which is fine.
   - File: `apps/web/components/week/week-board.tsx:109`.
   - Fix: move `data.pick_mode.label` out of `sub` into a `<p className="text-xs text-subtle">` placed right after `<PageHead>`, so the head row keeps its height.

5. **SHOULD: the fact grids leave single items alone on a row at 393.** With three facts in a 2-column grid, "Total points" sits alone, and "Push" sits alone twice. Market has four facts, so it fills a 2×2 grid cleanly.
   - Fix: on the two percentage grids (lines 62 and 77), change `grid-cols-2 … sm:grid-cols-3` to `grid-cols-3`. Values like "48%" fit in about 110px.

6. **SHOULD: the headings don't match Market's type scale.** The simulator uses `mb-3 text-sm font-medium` for its sub-headings; Market uses `mb-2 text-xs font-medium`. Its footnote is `text-xs`; Market's is `text-[11px]`.
   - Fix: on lines 59, 76 and 86, use the Market classes.

7. **SHOULD: the margin sign reads against the spread.** "Home margin +3.1" sits above "LV -3.5". Both favour LV, but the opposite signs read as disagreement, and "Home" makes the reader work out who is home.
   - Fix: change the label to `` `${game.home.abbr} margin` `` (line 40). Optionally show the value as "LV by 3.1".

8. **OPTIONAL: team order flips inside the section.** Average score lists away then home (MIA, LV), but the cover chances list home then away (LV, MIA). Pick one order; home first would match the spread heading.

9. **OPTIONAL: the range notes wrap awkwardly at 393.** "80% of runs between -9.0 and +15.2" breaks badly.
   - Fix: shorten to "80% of runs: −9.0 to +15.2" (lines 43 and 49).

10. **OPTIONAL: `Fact` is now copied in two files.** It is duplicated in `simulation.tsx` and `market.tsx`, and the copies already differ (`min-w-0`). Move it into `components/ui.tsx`.

**Copy note (no fix proposed):** the board line "Both pick modes use the same order: win chance, then game id" reads like engine jargon. "Assumed … (pool rules unavailable)" is correctly labelled.

**Verdict:** it can land once item 1 is fixed or explained. Items 2-4 are small fixes and are worth doing in the same pass.

## Coordinator triage
Accepted (WO2): 1 MUST (each simulator line says it is the line the simulator used; the fixture's -3.5 against the
seeded -3 is test data, but a real gap happens when the line moves after the prediction run), 2, 4, 5, 6, 7, 8, 9.
Not taken: 3 (the server's label stays word for word: it is the disclaimer, S1); 10 (moving `Fact` into `ui.tsx`
touches a shared file for no user-visible change). Copy note on the pick-mode text: server wording, not lane web's.
