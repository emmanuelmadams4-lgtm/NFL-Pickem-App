# Visual and anti-slop critic, round 1 (on `7611d89`) — DESIGN VERDICT: FAIL

Fresh subagent, read-only, given the screenshots, the diff, design.md and the brief.

| id | severity | evidence | fix |
|---|---|---|---|
| V1 | Critical | `after-week-full-393.png` (x≈103–165, y≈869) and `after-week-full-320.png` (y≈949): ", next kickoff" is near-black text on the dark card body, effectively invisible. It is the only wording that explains the lime card. | Use `text-text-2` in `apps/web/components/week/game-card.tsx:87`; `text-accent-ink/75` only works on lime. |
| V2 | Critical | `after-week-393.png` and `after-week-320.png` (x≈127 and x≈273, y≈197): week arrows are ~8px faint chevrons with no container, and read as disabled or decorative. Before, they were 44×40 bordered buttons. The code intends to hide them (`hidden … lg:inline-flex` in `apps/web/components/pickers.tsx:44,54`), but they still render. | Either hide them properly on the phone or restore the bordered 44px buttons. |
| V3 | Structural | `after-week-393.png` (y≈253): "Yahoo sheet" and "Updated just now" are gone from the first screen and appear nowhere in `after-week-full-393.png`. The code puts them, with Sort, at the end of the filter row, which ends flush at x≈388 with no fade or cut-off pill to hint at scrolling. | Take Yahoo sheet out of the scroller (page-head row or board footer) and add a right-edge fade. |
| V4 | Structural | `after-week-393.png` (y≈655–740): the "Counts as BUF…" helper sits above the buttons column only, leaving a dead block above "Points". At 320 the order changes to Points, helper, buttons. The sentence repeats on all four cards. | Use one stacking order at both widths, and say the rule once per board. |
| V5 | Visual | `after-week-full-393.png` (y≈620, 985, 1351, 1717): a red "High" chip on every card, and amber "Upset watch" on three of four, including the 87% "Easy pick". The chips no longer distinguish anything. | Show the uncertainty chip only when it is notable, and suppress Upset watch on easy picks. |
| V6 | Visual | Same file (y≈592, 1324, 1690): "Coin flip · Coin flips have won…" and "Easy pick · Easy picks have won…" repeat the label in the same line. | Change to "Coin flip · won 52% since 2012". |
| V7 | Visual | `after-week-393.png` (y≈775–840): the lime tab pill sits over the lime next-kickoff header and the two merge. | Give the tab bar an opaque dark backing with a stronger border or shadow. |
| V8 | Visual | `after-game-open-393.png`, byte-identical to before: 54% appears twice on the first screen (y≈362 and y≈720), and the pick pills sit at y≈578 below an explainer paragraph. | Drop the explainer, or move the pick pills directly under the tiles. |
| V9 | Polish | `after-week-393.png` (y≈350–368): the "Me" caption wraps to two lines and "Model" to one; at 320 both wrap. | Shorten to "None graded" / "None live". |
| V10 | Polish | `after-settings-393.png` (y≈629): the "Storage" row has no helper line or divider, unlike its sibling rows. | Match the sibling row pattern. |

Not verified by the critic: the final-game state (the seed has no final game, so the "game-final" shots show a scheduled game); `after-sheet-320.png` and `after-results-320.png` were not opened.

**Largest problem:** the compaction made room for the first card by demoting controls rather than resolving them. The week arrows are ghost glyphs, the Yahoo sheet link is hidden in an unsignalled sideways scroll, and the "next kickoff" label is invisible.
