# Design critic 2 — the one-name stars line on the card (commit 0633ad5)

Fresh read-only subagent, no build transcript. Screenshots: `~/.claude/plans/nfl-pickem-lanes-logs/step-8a2/after5-board-{phone,tablet,desktop}.png`.

Verdict: FIX (two major, both wording or format). It confirmed that critic 1's F1 is fixed as stated: no status, count, age or club note is cut at any of the three widths. Contrast passes (grey about 5.3:1, red about 6.6:1). The line does not compete with the pick buttons.

| # | Severity | Finding | Decision (coordinator) |
|---|---|---|---|
| 1 | MAJOR | The name is cut from the end, so a long name loses its surname ("BUF Maximil…"). Asks for "M. Featherstonehaugh" and a minimum width. | Not changed. The app never rewrites a name from the feed (data rule: show what the source says; initials collide and break on "Amon-Ra St. Brown", suffixes). Measured on the 393 px shot: with both clubs' lists present the name has about 137 px, about 23 characters ("SF Christian McCaffrey" is 22); with "Doubtful" about 18. The cut seen is the 39-character stress name in the rare state where a club has no list. A minimum width would push the status or the missing-list note off the line, which is what F1 forbade. The full name is in the page for a screen reader and on the game screen, one tap away. Carried to god. |
| 2 | MAJOR | "MIA: no list" reads as "nobody listed", good news. It means the data is missing. | Accepted: "MIA: no star list" (work order 9). Missing must read as missing. |
| 3 | MINOR | "+3 more 3h ago" runs two numbers together. | Accepted: a middle dot before the age (work order 9). |
| 4 | MINOR | The count does not say which club. | Not changed: D27 asks for a short line; the game screen lists both clubs. Same decision as U9, V9 in round 1. |
| 5 | MINOR | The count leaves out the QB shown in the chip above. | Not changed: decided in round 1 (the same man is not shown twice on one card). |
| 6 | MINOR | "3h ago" does not say what is three hours old. | Not changed: D27 says "with its age"; the game screen says "seen 3h ago" and explains what the age counts from. |
| 7 | MINOR | The group name is read twice by a screen reader. | Not changed: same as I8 in round 1 (no serious or critical axe finding; ST7). |
| 8 | NIT | "Out" is a chip on the QB line and plain text on the stars line. | Not changed: the chip does not fit one line; it also sets the order of weight (QB above stars). |
| 9 | NIT | Desktop clips the long name though the card has room. | Not changed: one rule at every width. |
