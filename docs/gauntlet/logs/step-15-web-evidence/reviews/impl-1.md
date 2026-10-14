# Implementation critic 1 — step 15 web (work orders 1 to 3, tree of `ae073e9`)

Fresh read-only subagent (`ecc:react-reviewer`, Sonnet). It read the production diff against `d8276a2`. Nothing was run: every finding is by reading. VERDICT: **PASS WITH FIXES**, no CRITICAL or HIGH.

| # | Sev | Where | Finding | Decision (coordinator) |
|---|---|---|---|---|
| 1 | MEDIUM | `game-card.tsx`, chance line | S5 with both chances missing: the visible words are `aria-hidden` and there is no `sr-only` twin. | Accepted: work order 4 item 8, failing test first. |
| 2 | LOW | `game-view.tsx`, chance block | S4: a screen reader hears the age twice. | Accepted: item 8. |
| 3 | LOW | `live/state.ts` | `cardLiveState` is about 60 lines; the "S3 or S4" test is repeated four times. | To CLEANUP. |
| 4 | LOW | `queries.ts` | `heldPosts` is a module-level Map, never cleared (not on sign-out). No bug today. | Not changed: marked `ponytail:` with its ceiling; ended rows are public scores, and a reload clears it. |
| 5 | LOW | `game-card.tsx` | A game past kickoff whose status is still `scheduled` shows pregame star news. | Accepted: item 9, failing test first. |
| 6 | LOW | `WinSplit` | The started caption drops the backfill words (CLAUDE.md: backfill is always labelled). | Accepted: item 10. |
| 7 | LOW | `checkedAt` against the 2 s tick | The age can be slightly negative right after a poll; `ago()` reads "just now". | No change needed. |
| 8 | LOW | `refetchInterval` | Rebuilt every tick; safe because the library compares the computed interval. | One comment, in CLEANUP. |

Checked and found right (by reading): feed text is a text child only and club codes come from the game; a null never prints as 0, "null" or "NaN"; the percent ends; hook order; a failed poll keeps the data, so S4 follows by age; a 401 goes through the global handler; the persist filter; no `aria-live`.
