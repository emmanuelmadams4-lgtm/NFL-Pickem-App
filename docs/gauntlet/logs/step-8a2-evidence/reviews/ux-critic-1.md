# UX critic, round 1 (fresh subagent, read-only), on the `after-*.png` shots and `eed7c61..4657935`

All three reference files applied. Game screens viewed at phone and desktop, not tablet.

| id | pass | severity | evidence | fix | rule broken |
|---|---|---|---|---|---|
| U1 | A | Critical | `after-board-*.png`, MIA@BUF and BUF@MIA cards: BUF stars are listed, but nothing says MIA has no star list. `game-card.tsx` reaches the `no_list` and `reports_seen === 0` texts only when `stars.length === 0`. | Show the quiet text as well as the stars line, naming the club ("MIA: no star list yet"). | Comprehension; ST3; "missing is shown as missing". |
| U2 | A | Structural | All cards with a stars line: "Cal Catch WR Doubtful · Cory Corner CB Out" names no club. The QB alert one line above does. | Prefix or group by club abbreviation, as the QB alert does. | Comprehension; consistency. |
| U3 | A | Structural | `after-game-2023_04_NE_KC-desktop.png`: NE shows five "Not on injury report" while NE's table below says "0 listed / No injury report entries". `star-players.tsx` tests `reports_seen` for the game, not the club, so KC's report vouches for NE. | Decide per club; a club with no entries gets an en dash or "No report from NE yet". | ST6 (not known is not shown as available). |
| U4 | B | Structural | Same capture, phone too: the full injury table follows the star lists with no heading, and the club headers repeat in identical style. "Not A Star G Out" reads as a star row. "Report as of 3h ago" sits above Star players, not with the table. | Add an "All injury report entries" subheading carrying "Report as of…", directly above the table. | Information hierarchy. |
| U5 | A | Visual | KC: Ron Runner is plain grey "Questionable" in the star list and an amber chip 300px below. | One treatment for the same status in both lists. | Consistency. |
| U6 | A | Visual | Star rows: "QB Pat Passer QB" says QB twice; slot labels of unequal width stop names aligning. | Drop the slot label when it equals the position; fixed-width slot column or put it after the name. | Cognitive load; scan efficiency. |
| U7 | B | Visual | `after-game-2023_04_MIA_LV-phone.png`: one grey line plus three dashed empty boxes all say "nothing". | When neither club has a list, collapse to one line. | Empty-state coverage; density. |
| U8 | A | Polish | BUF cards, phone and tablet: "latest seen 3h ago" is orphaned on a fourth line. | Keep the age on the label line ("Stars out · seen 3h ago"). | Hierarchy. |
| U9 | A | Polish | BUF cards: all five BUF stars are out, but the line shows three names "+1 more" because the QB sits in the alert row, so it reads as four. | Add a total or count the QB in "+N". | Comprehension. |

**Single largest problem:** the board line does not say which club its stars belong to (U2), and it suppresses the "no star list / report not in" text whenever the other club has a star out (U1). U3 is the same failure on the game screen.
