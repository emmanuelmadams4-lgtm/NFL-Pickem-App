# Design critic 1, UX — step 15 web (work orders 1 and 2 on `bf113cb`, work order 3 in the tree)

Fresh read-only subagent (Sonnet). It read the spec, the three production files and the before and after screenshots (live, ended, lost, not updating). Nothing was run. VERDICT: **PASS WITH FIXES**. Decisions are in the step log, section 3.

| # | Sev | Where | Finding | Its smallest fix |
|---|---|---|---|---|
| 1 | MAJOR | game screen, pick panel | The existing "Live" chip beside "Model pick" and 87% sits under live scores; it reads as "live model pick" and contradicts the "does not change during the game" caption. | Hide that chip while the game is started, or relabel the panel. |
| 2 | MAJOR | game screen header | The label is 12 px grey over a 40 px score; it is the only live-versus-ended cue. | Label to `text-sm`, "Live" in `text-text`. |
| 3 | MAJOR | board, not updating and lost | The only signals are a 12 px grey label and slightly dimmer score ink. | A warn tone on the not-updating label, as well as the words. |
| 4 | MAJOR | board, ended | The ended card looks almost the same as live. | Dim the pregame block in S2, or a chip. |
| 5 | MAJOR | board, chance line | Two KC percentages on one card (87% pregame, 71% now); the line is 12 px grey. | Prefix "Live:" and put the figures in ink. |
| 6 | MAJOR | chance line wording | "KC to win now 12%" after an upset in progress is right but alarming; nothing says the club is the pick. | "KC win chance now", or name the pick. |
| 7 | MINOR | game screen, phone | "Not updating · Q3 4:12" wraps and leaves "4:12" alone. | A no-break space between period and clock. |
| 8 | MINOR | game screen, S4 | "Score may be out of date" exists only for screen readers. | Show it. |
| 9 | MINOR | S4 | "No update yet" sounds like the game has not started. | "No update received". |
| 10 | MINOR | board | Live label and "Pregame model pick" are the same size; hierarchy between them is weak. | Label `text-sm`. |
| 11 | MINOR | game header | The centre column is 112 px on a phone; "Not updating · last seen End of Q3" may wrap to three lines at 320 px. | `text-balance`, or shorter S3 words. |
| 12 | MINOR | board, S2 | "Locked" lines say nothing about the live state. | None; note only. |

Could not verify (its list): the lost game screen and the desktop and tablet shots (not opened), contrast at 12 px and the light theme, 320 px wrapping, VoiceOver.
