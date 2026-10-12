# Implementation reviewer, round 3 (on `cfbef46`) — VERDICT: FAIL (one Medium)

Fresh subagent, read-only, given the commit, the queue files and the rule ("the last choice he made for a game is what the server ends up with, and no choice is dropped without him being told"). No build history.

N1, N2, N3 from round 2: all fixed (`sync.ts` re-checks the queue entry before the send and deletes it only if it still equals what was sent; `orderedPickSend` chains every send for a game from both paths; a non-network error continues to the next game and stops only on a network error or 401).

| id | severity | file:line | what is wrong | smallest fix |
|---|---|---|---|---|
| F1 | Medium | `queries.ts:80` | The direct path calls `unqueue` before the PUT, so the pick lives only in memory while the request is in flight. If iOS suspends or kills the app (or the page reloads) then, the request is lost, nothing is queued and he is not told. An older queued pick for that game is gone too. | `queuePick(gameId, team)` before the send, then `unqueueIfCurrent(gameId, team)` on success. |
| F2 | Low | `queries.ts:80,84-89` | On a 500 or 401 the older queued entry was already deleted; the rollback briefly shows it as picked and not waiting. Corrects itself on refetch and he is told. | Covered by the F1 fix. |
| F3 | Low | `sync.ts:110,189-190` | `warnedGameId` holds one slot: two games that both keep failing toast again on every retry. | A `Set` of warned ids. |
| F4 | Low | `sync.ts:156-158` | A tap that waits behind an in-flight send for the same game does not show until the chain reaches it (up to 5 s). | Covered by the F1 fix (queued at once). |
| F5 | Low | `queries.ts:108-113` | A refetch from the first tap can land while the second waits: a flicker. | Leave. |

Checked and clean: a rejected send does not poison the chain; map cleanup only removes the latest tail; no send can hang (5 s timeout, counted as a network error, re-queued, PUT and DELETE are repeatable); tap B then A again behind a flush ends on A; offline taps behind a flush overwrite in tap order; a direct send that finishes first makes the flush skip its stale value; the mutation `scope` cannot deadlock with the chain; `flushing` always resets; the toast counts only entries actually removed; a 409 on the direct path says "Locked at kickoff" and rolls back.
