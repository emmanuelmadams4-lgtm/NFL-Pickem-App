# Implementation reviewer, round 2 (on `d0d7b9e`) — VERDICT: FAIL

Fresh subagent, read-only, given the diff, the round-1 findings F1-F8 and the brief. No build history.

| id | sev | file:line | what is wrong | fix |
|---|---|---|---|---|
| N1 | High | `apps/web/lib/sync.ts:158,162` | A flush has `PUT A` in flight for game G. Reachability flips false (a concurrent query times out) or the phone goes offline, the user taps B, and `useSetPick` queues `{G:B}`. `PUT A` then resolves and `unqueue(G)` runs unconditionally. B is deleted, the server keeps A, the UI reverts to A and the toast says "1 waiting pick saved." The line 154 guard only checks before the send. | After the await, unqueue only if `readQueue()[gameId] === team`. |
| N2 | Medium | `apps/web/lib/queries.ts:80-82`, `apps/web/lib/sync.ts:156` | The mutation scope does not cover a flush. With `{G:X}` queued, the user taps A (direct PUT in flight) and a timer or visibility flush sends `PUT X` at the same time. Two concurrent requests can commit in either order, so the older X can win; both paths unqueue. Also applies to tap-to-clear during a flush. | Remove G's queue entry before a direct send, or skip games with a send in flight. |
| N3 | Medium | `apps/web/lib/sync.ts:166-169` | `break` on a non-network error. One game that keeps returning 500 blocks every later queued pick until those hit 409 at kickoff. | `continue` for per-game errors; break only on network errors or 401. |
| N4 | Low | `apps/web/lib/sync.ts:110,167` | `warnedGameId` suppresses a later, different failure for the same still-queued game (500, then 401 hours later). No 15 s repeat found. | Key the warning on game and status. |
| N5 | Low | `apps/web/components/toast.tsx:54-65` | The update toast has no dismiss; it stays above the tab bar until Reload. | Add a dismiss button; reset `updateOffered` on dismiss. |
| N6 | Low | `apps/web/components/week/week-board.tsx:118`, `apps/web/components/game/game-view.tsx:82` | The fade is 15% of row width but end padding is a fixed 48px. At 393 wide the last chip or tab is still 6-11px inside the fade; at 768 it is far more. Whether `pr-12` adds scroll-end padding on iOS Safari is not verified. | Fade from `calc(100% - 48px)`. |
| N7 | Low | `apps/web/components/game/game-view.tsx:93`, `apps/web/components/week/points-control.tsx:64` | Section tabs (`h-10`) and the points clear button (`min-h-10`) are 40px on the phone. | `h-11` below `lg`. |

Checked and clean:
- Queue: a 5 s timeout on a write the server applied is re-sent idempotently (PUT, and DELETE returns 204). The `queries.ts:82` unqueue cannot drop a newer tap, because the scope serialises taps per game.
- Timer: cleared on unmount, skipped when the tab is hidden or offline, cannot pile up (5 s health timeout against a 15 s interval, plus the `flushing` flag).
- Update prompt: `updateOffered` never resetting is harmless, since the toast only leaves through Reload. The already-installing path and the no-waiting-worker reload both work.
- Layout: pick buttons carry their own `relative z-10`, so the `contents` wrapper does not let the card link swallow taps. `order-first w-full` is inert at `lg`. Duplicate copies are `display:none`.
- Client: the timeout exemptions match `/picks/import` and `/refresh`.

F1 to F8: F1-F7 fixed (N1, N2 are what remains of F1; N6 of F4). F8 not fully fixed: dedupe and reload fallback done, dismiss missing (N5).

**Largest problem:** N1. A flush that completes for a game silently deletes a newer pick queued for that game during the request, and reports success.
