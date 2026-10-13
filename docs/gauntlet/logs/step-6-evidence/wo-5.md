# CODEX WORK ORDER 5 — step 6, lane pwa: round 3 finding F1 and the cleanup item

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-5 → sol (0.98); effort split 54/46 (confidence 0.08), route advisor; Sonnet advisor: high.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red test pass (`apps/web/e2e/pwa.spec.ts` P16) without breaking any other browser test, and make the one cleanup change.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-6-evidence/reviews/r3-implementation.md` (F1) and `reviews/cleanup-pass.md` (R1).

ALLOWED SCOPE (edit only these):
- `apps/web/lib/queries.ts` (`useSetPick` only)
- `apps/web/lib/sync.ts`

REQUIREMENT

A. F1, P16: a tapped pick must be on the phone (in the `nflpi_pick_queue` queue) from the moment it is sent until the server has answered. In `useSetPick`'s direct path: write the choice to the queue first (`queuePick(v.gameId, v.team)`, which also replaces any older queued choice for that game), then send. Then:
   - success: remove the entry only if it still holds the value that was sent (export and use `unqueueIfCurrent`); return `{ queued: false }`.
   - network error: leave it queued; return `{ queued: true }` as today.
   - any other error (409, 422, 404, 500, 401): remove the entry if it still holds the sent value, then rethrow, so today's rollback and toasts stay as they are.
   The offline / unreachable branch is unchanged. Everything still runs inside `orderedPickSend`.
   P16: he taps while online, the request is held, the page is reloaded mid-request; the queue must hold his pick during the request and the next open must send it.

B. R1, cleanup, no behaviour change: in `sync.ts` the `gameId in queue` test before `queue[gameId] !== team` is redundant (a missing key reads as `undefined`, which never equals a `string | null` team). Remove it in the three places: `unqueueIfCurrent` and the two checks in `flushPicks`.

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-r3-findings.log` (1 failed, 16 passed).

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo5`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, nothing else cleaned up.
- Do not edit any file under `apps/web/e2e/`, any seam, or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- P4, P11 to P15 exercise the same code and must stay green.
- Match the surrounding style. No `console.log`. Immutable updates.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
