# Design critic 2, visual — step 15 web (work orders 1 and 2 on `bf113cb`, work order 3 in the tree)

Fresh read-only subagent (Sonnet). It read `design.md`, the brief, the three components and four phone screenshots (live board and game, not-updating board, lost game). It did not open the tablet, desktop, before or ended shots. Nothing was run. VERDICT: **PASS WITH FIXES**. No new colour, animation, icon or chip style found. Decisions are in the step log, section 3.

| # | Sev | Place | Finding | Its smallest fix |
|---|---|---|---|---|
| 1 | MAJOR | board, live card, score row | The pregame "KC 87%" is in the display face at the same size as the live score, so the score does not clearly win. | Pregame figure to `text-xl` while started. |
| 2 | MAJOR | game header, centre column, phone | The label wraps in the 112 px column for lost and not-updating and pushes the score down about 16 px; the score's place differs between states. | A fixed label height (`min-h-8`), or shorter words. |
| 3 | MAJOR | board, live card | `p-2` / `gap-1` is visible: text sits 4 px nearer the edge than on neighbour cards and off the spacing scale. | `p-3`, `gap-1.5`. |
| 4 | MAJOR | game screen, block under the header | A bordered card for three small lines is heavy as a container; `design.md` § 7 says a box is the last resort. | No box: `border-t border-border pt-3`. |
| 5 | MINOR | board, not updating | The label has the same ink as normal labels; it does not read as a state change. | "Not updating" in `text-warn`, words kept. |
| 6 | MINOR | board, live label | Period and clock are the weakest item at 12 px. | Clock `text-sm text-text`. |
| 7 | MINOR | board, chance line | It sits beside "Pregame line KC 58%": two sources in one cluster. | Move it under the score row. |
| 8 | MINOR | game header | The score block sits about 30 px higher than the logos. | Centre the middle column on the logos. |
| 9 | MINOR | board, score row | Club codes look small beside the figures; same as the final-score pattern. | Leave. |
| 10 | MINOR | game screen | The pick panel's "Live" chip is a second place saying "Live". | Remove it from the pick panel while started. |
