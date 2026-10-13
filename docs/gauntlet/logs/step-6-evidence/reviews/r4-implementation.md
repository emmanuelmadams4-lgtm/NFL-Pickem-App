# Implementation reviewer, round 4 (on `a12dc55`, before the rebase) — VERDICT: FAIL (one Medium)

Fresh subagent, read-only, given the queue files and the rule ("the last choice he made for a game is what the server ends up with, and no choice is dropped without him being told"). No build history.

| id | severity | file:line | what is wrong | smallest fix |
|---|---|---|---|---|
| R1 | Medium | `apps/web/lib/queries.ts:74-80` | A tap is written to the queue only when its turn in the per-game chain starts, not when he taps. Tap A online, the request is in flight (up to 5 s on a slow server). Tap B: it waits in the chain and is not on the phone yet. iOS closes the app. On reopen the queue holds A, the flush sends A, and B is gone with no message. | Write the choice to the queue at tap time, before the chain. Inside the send, skip if the queue no longer holds this value (a newer tap replaced it). Keep `unqueueIfCurrent` after the send. |
| R2 | Low | `sync.ts:157`, `pick-buttons.tsx:21` | Follows from R1: while A is in flight the queue entry A wins over the optimistic B, so the button keeps showing A until A finishes. | Removed by the R1 fix. |
| R3 | Low | `pick-buttons.tsx:66-70` | Every online tap is briefly queued, so "Waiting to sync" flashes on each tap (up to 5 s on a slow request). Cosmetic. | Accept, or show it only when the entry is not being sent. |
| R4 | Low | `sync.ts:189-191` | `warnedGameId` holds one game: two games that both keep failing warn again every 15 s. | A `Set` of warned ids. |
| R5 | Low | `sync.ts:184-185` | A 404 in the flush is reported as "locked at kickoff", the wrong reason. | Word it "locked or no longer valid". |
| R6 | Low | `client.ts:60` | A request that timed out on the phone could in theory still land after a later one. Very unlikely for one user on a tailnet. | None. |

Checked and clean: tap A then B quickly online ends on B; a flush that starts during a direct send is chained behind it and skips an entry already saved (no double send); a double PUT or DELETE is harmless (upsert; DELETE returns 204); a tap during a flush of an older value wins; a timeout after the server applied the request is resent and shown as waiting; the app killed mid-request after a single tap is resent on reopen; 500, 401, 409 and 422 on a direct send remove the entry only if current, roll back and toast; the "N waiting picks saved" toast cannot fire for a pick that was saved directly; tap-to-clear behaves like a team value everywhere; a rejected send does not break the chain; a 401 stops the flush and warns once.
