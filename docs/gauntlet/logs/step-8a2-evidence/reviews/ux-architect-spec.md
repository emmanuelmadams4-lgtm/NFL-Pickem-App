# Step 8a2: UX Architect critic on the brief and the spec, before any code (fresh Sonnet subagent, read-only)

18 findings; the largest: the row said nothing in three different situations (nobody out, report not in yet, club has no list), so silence read as "no star is out". Coordinator's triage:

| # | Severity | Finding | Decision |
|---|---|---|---|
| 1 | Critical | Row silence means three things | ACCEPTED: silent only when the report is in, both lists exist and no star is Out or Doubtful. Otherwise a quiet text: "Injury report not in yet" or "No star list yet". ST3 rewritten. |
| 2 | Structural | One age for a line of stars with different ages | ACCEPTED, small: the row says "latest seen Xh ago" (the newest of the shown stars); each star has his own age on the game screen. |
| 3 | Structural | "seen" not defined | ACCEPTED: one note in the block: ages count from when this app first saw the status. |
| 4 | Structural | "Not listed" is ambiguous | ACCEPTED: "Not on injury report". |
| 5 | Structural | The injury text is in the contract but in no criterion | ACCEPTED: shown on the game screen (ST4), not on the row. |
| 6 | Structural | A star QB is shown twice (QB alert and stars line) | ACCEPTED: a player already named in the card's QB alert is left out of the stars line; "+N more" counts only what is hidden. ST2 rewritten, seed changed. |
| 7 | Structural | Missing states | PARTLY: the row line is for scheduled games only (a finished or running game has none); other statuses (IR and the like) are shown as text on the game screen. The rest are covered by existing behaviour (one request, the page skeleton). |
| 8 | Structural | Two clocks under one header | ACCEPTED: the block has its own heading and notes; "Report as of" stays with the injury table. |
| 9 | Visual | The flags row would wrap to three lines | ACCEPTED: the stars line is its own full-width line under the flags row, above the pick buttons. No one-line pixel assertion (font widths differ on CI); "no sideways scroll" is asserted. |
| 10, 11 | Visual | No new tap target, no alarm styling near the pick | ACCEPTED as constraints in the work order. |
| 12 | Structural | Could read as "the pick changed" | ACCEPTED: one line on the game screen says a star being out does not change the pick (ST4); B5 pins the data. No before/after render test: the page renders only what the API returns. |
| 13 | Polish | "Stars out or doubtful" | REJECTED: D27 names it "who's out"; each chip says Out or Doubtful. |
| 14 | Polish | "List from week N" | ACCEPTED: "Star list from week N". |
| 15 | Polish | Two empty texts read alike | ACCEPTED as worded in the spec. |
| 16 | Structural | Order left to the builder | ACCEPTED: away club first, then slot order, as the API returns it. |
| 17 | Structural | No stale marker for the star list on the board | CARRIED: Settings shows it and the block names the list's week; a board marker waits for evidence it is needed. |
| 18 | Polish | A report-not-in note on every card early in the week | CARRIED: one quiet text per scheduled card is accepted for now; a single board-level note is a later polish if the owner finds it noisy. |
