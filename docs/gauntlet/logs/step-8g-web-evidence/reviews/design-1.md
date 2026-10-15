# Design critic 1: step 8g web, on `91da4a9` (fresh read-only subagent, screenshots `after-*` in `~/.claude/plans/nfl-pickem-lanes-logs/step-8g-web/`)

Report (summary): no blockers apart from the link colour; uses the shared Section/Chip/ErrorState/Skeleton; contrast fine
(subtle 5.3:1); focus is the global outline; nothing overflows at 1280.
1. MUST `news.tsx:27` links use `text-text underline`; design.md:24/110 and every other link use `text-accent-text underline underline-offset-2`. On the phone linked and unlinked titles barely differ.
2. SHOULD no cue that a title opens a new tab: sr-only "(opens in new tab)" and an aria-hidden arrow.
3. SHOULD a one-line title link is about 20 px tall (touch target).
4. SHOULD the skeleton is one 96 px block; match the final rows.
5. SHOULD "ESPN 3h ago" has no separator; add an aria-hidden "·" as History does.
6. COULD `key={index}`; use url or title.
7. COULD a fuller empty-state sentence.
8. COULD `ago()` switch to days after 24 h (a shared formatter).

## Triage (Jim)
- Taken: 1 (accent link class), 2 in part (the sr-only "(opens in new tab)"; no icon: ponytail, the text does the job),
  5 (a "·" between source and age). Tests first: N1 asserts the class, the accessible name and the separator (`s8g-red-2`
  fails on the class). WO2.
- Not taken: 3 (inline text links are exempt from the WCAG 2.2 target-size rule, and the app's other inline links are the
  same); 4 (a one-off loading flash; no sibling section uses a row skeleton); 6 (the list is replaced whole on each answer,
  never reordered in place); 7 (matches the sibling sections' empty copy); 8 (shared formatter, out of scope).
