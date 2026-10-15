# Fresh critic 1: step 18j, on `5a91a18` (read-only subagent, no transcript, 2026-10-14)

Verdict: PASS with one MEDIUM. Gate: typecheck 0; `s18j-critic-1` (sim18j on a fresh build) 6 passed, 0 failed.
The integrator's question (does 18j add a query before the cards render?): No. `week-board.tsx:201` reads the week reply
the board already loads; `simulation.tsx:25` reads the game reply the page already loads.

Findings and triage (Jim):
- MEDIUM `week-board.tsx:201`: `data.pick_mode.label` with no guard. A week reply saved by the phone's offline cache
  (kept up to 7 days, `lib/persist.ts` VERSION not raised) from before 18h has no `pick_mode`, so the board throws.
  **Accepted**: red test S5b (`s18j-red-3`, no game card), fix in WO4.
- LOW S4 "the pick panel is unchanged" has no test. Not taken: the section is a separate component placed after Market,
  and the pick panel's own specs (step2, restyle) cover the panel.
- LOW S5 placement is not asserted. Not taken: phone-layout L1 guards the reason for the placement.
- LOW S2: no test for "Pick'em" at 0, or for the total push value. Not taken: one-line formatter branch; cosmetic.
- LOW S6 axe is scoped to `#simulator`. Not taken: the rest of the page is covered by the existing axe specs.
- LOW S1 order: the spec text lists away first, while the code shows home first. That order came from design finding 6,
  accepted in WO2; S1 now reads home first (amendment 3 below).
- LOW `signed(-0.04)` shows "-0.0". Not taken: the server rounds the margin to 1 dp; cosmetic.
- Missing evidence: the full suite on the final head is owed to PR CI (D71, god 22:20 UTC); WO3 was a one-line move
  (no new security surface); after-WO3 board screenshot: not retaken (the line moved below the cards).
