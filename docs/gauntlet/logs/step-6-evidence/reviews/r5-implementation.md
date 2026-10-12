# Implementation reviewer, round 5 (on `9aa5990`, after work order 6) — VERDICT: PASS

Fresh subagent, read-only, given the queue files and the rule ("the last choice he made for a game is what the server ends up with, and no choice is dropped without him being told"). No build history. No Critical, High or Medium finding.

| id | severity | file:line | what is wrong | smallest fix |
|---|---|---|---|---|
| R1 | Low | `queries.ts:97,103-105` | Wrong rollback snapshot after a skipped tap: tap A (not sent yet), tap B, B fails with 409 or 500. The rollback restores the snapshot taken at B's tap, which already held the unsent A, so the card shows A although the server holds the earlier pick. The refetch that follows corrects it; after a persistent 500 it can stay until the next refetch (up to 120 s) or focus. He is told B was not saved. | Record the pre-queue server value per game and roll back to that. |
| R2 | Low | `sync.ts:188-189,206` | "Locked at kickoff" is also shown for 404 and 422, and for a pick whose first send timed out but was applied, then got 409 on the resend after kickoff. Wording only; the data on screen is right. | Separate count and message for 404 and 422. |
| R3 | Low | `sync.ts:193-194` | `warnedGameId` holds one game: two games that both keep failing warn again every 15 s. | A `Set` of warned ids. |
| R4 | Low | `queries.ts:103-107` | A superseded tap that fails still toasts "Pick not saved" although a newer tap then saves. | In `onError`, skip the toast and rollback when a newer choice is queued. |
| R5 | Low | `client.ts:48,60` | A request the phone gave up on after 5 s could still reach the server after a later one. Rare; needs a server-side sequence to fix. | Not fixable in the client alone. |

Checked and clean:
- Mutation ordering, read in `query-core` 5.104.2 `mutation.ts` `execute()`: `onMutate` runs before the wait on `scope`, so `queuePick` is synchronous at tap time; no deadlock with `orderedPickSend`.
- `mutations.networkMode` is `offlineFirst`, so the send function also runs offline and queues.
- Tap A then B quickly online: A is skipped, B is sent, unqueued, refetched.
- A, clear, A: ends on A. A then clear: the DELETE is sent; DELETE of a missing pick returns 204.
- A tap while a flush is mid-send for the same game: the flush does not remove the newer entry; the tap then sends it.
- A flush that starts between a tap's `onMutate` and its turn: the flush sends the tapped value; the tap's own send is skipped; nothing is lost and the flush refetches.
- Offline tap, then back online: `online`, `visibilitychange` and the 15 s timer all flush.
- A direct send that fails with 401, 409, 422 or 500 removes its entry (unless a newer one owns it), toasts and rolls back; it is not retried behind a "Pick not saved" toast.
- A flush error that is not 404, 409 or 422 stays queued, retries every 15 s, toasts once; a 401 stops the flush.
- Resends after a timeout are safe (PUT and DELETE are repeatable).
- App killed before, during or after a send: the entry persists and is resent.
- No request can hang the chain or the `flushing` flag (5 s abort covers the body read).
- `sw.js` leaves writes and `/api/` alone.
