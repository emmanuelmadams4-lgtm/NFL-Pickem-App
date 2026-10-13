# Security review (Dwight), round 1, on `89600bd` (diff `a71e112..89600bd`)

Hive message 23c1f1, 2026-10-13. Own full read; `ecc:security-reviewer` and `ecc:silent-failure-hunter` run read-only. No tests run.

**VERDICT: PASS on security. No critical, no high.** Six medium, three low.

Four points asked: feed text to the web OK (`_clean_star_text` drops control and format characters; React renders text children only; nothing from the feed in an attribute); database reads are ORM selects, bounded; the worker step is OK (failure recorded, rolled back, round goes on); every route still needs the token, no new route.

| id | Finding | Decision |
|---|---|---|
| M1 | `apps/web/lib/persist.ts` `VERSION` still 1: a phone with a week cached before this step has no `stars_out`; the board throws when it opens from the offline cache | **Accepted** (WO-7 item 5: `VERSION = 2`). No red test: reproducing it needs a hand-built old cache; proof is by reading the version check at `persist.ts:19`. |
| M2 | `checked_at` is sent but the web does not show it; if the injury refresh fails for days, old statuses keep showing | **Not changed**: when `injuries` is stale the top-bar freshness indicator turns amber (`MODEL_INPUTS` in `freshness.tsx`) and Settings says how old it is. A per-line stale mark is carried (it was carried at the spec review too). |
| M3 | Name match without an id: no accent folding; a suffix can merge "X" and "X Jr." on one club | **Accepted**, red tests first (WO-7 items 6, 7). |
| M4 | A report row with no game status reads "Not on injury report"; `reports_seen` is per game | **Accepted in part**, red tests first: `listed` flag, "No game status" (WO-7 items 8, 9). Per-club count not changed: the week's report arrives whole, so a club with no row is not on it. |
| M5 | About seven queries per game on the week board | **Carried** to step 13 (backend speed); single user, behind the token. |
| M6 | A status outside Out, Doubtful, Questionable is dropped without a word; the card does not say when a club's list is old | **Carried**: the feed holds only those three game statuses; the old-list note is on the game screen. |
| Low | No `max_length` on `StarStatus` fields; `last_error` text for two more datasets; `key={a}` can repeat for QB alerts; `qb_alerts` text not cleaned | **Carried** (existing behaviour or second layer). |

Dwight asked for the delta after the fixes to confirm by reading.
