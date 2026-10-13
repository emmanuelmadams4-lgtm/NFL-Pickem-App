# Visual and anti-slop critic, round 1 (fresh subagent, read-only), on the `after-*.png` shots and `eed7c61..4657935`

| id | pass | severity | evidence | fix | rule broken |
|---|---|---|---|---|---|
| V1 | C | Structural | Game NE_KC: under "Star players", a second NE Team / KC Team pair follows with identical headers and no heading; three players appear twice. | Give the lower pair its own `h3` ("Full injury report"). | Weak hierarchy |
| V2 | F | Structural | Ron Runner is plain grey "Questionable" in the star row and an outlined warn chip four rows below. | Render star status with the `statusTone` chip from `injuries.tsx`. | Inconsistent component vocabulary |
| V3 | C/F | Visual | NE header stacks "Star list from week 3" under the name; the Injuries header puts its meta inline. NE's first row sits about 16px lower than KC's. | Put the week note inline after the club name. | Inconsistent heights |
| V4 | D/G | Visual | "QB Quin Backer QB", "Defense Russ Rush DE": slot prefix plus position on every row; names start at three x positions. | Drop the prefix, or a fixed-width column. | Redundant labels |
| V5 | G | Visual | Age is stated four ways on one screen. | Keep one caption line; move "Ages count…" to a `Tip`. | Too much explanatory copy |
| V6 | G/F | Visual | Game MIA_LV phone: two dashed "No star list yet" boxes, a dashed "No injury report entries" box and a line, about 300px saying nothing. | One text line per club with no boxes; one wording for the state everywhere. | Excess cards |
| V7 | E/G | Structural | Board phone, BUF card: four red chips on a card whose stars "do not change the pick". | Status as plain text in the line; keep chips for pick-relevant flags. | Excess pills; arbitrary color use |
| V8 | C | Visual | BUF card: the long name pushes "Stars out" onto its own line and the block runs four lines. | Surname only or truncate; cap at two lines; age on the label line. | Inconsistent heights |
| V9 | F | Visual | BUF card: the QB alert line sits above "Stars out"; the QB is a star but is left out of the stars line and its count. | Fold the QB into the stars line, or the same label treatment. | Inconsistent component vocabulary |
| V10 | D | Polish | Seven of ten rows read "Not on injury report" at the same weight as real statuses. | Set it in `text-subtle`. | Weak hierarchy |
| V11 | C | Polish | `mt-5 mb-6` spacing uneven around the star block. | Use the section's existing stack gap. | Inconsistent spacing |
| V12 | G | Visual | MIA @ BUF card: MIA has no star list, but because BUF has stars out the "No star list yet" line never renders. | Append "MIA: no star list" to the stars line. | Missing shown as missing |

**Single largest problem:** on the game screen the star block and the existing injury list read as the same component printed twice (V1), and the same status is drawn two ways (V2).
