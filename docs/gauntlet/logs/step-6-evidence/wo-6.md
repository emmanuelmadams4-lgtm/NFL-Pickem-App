# CODEX WORK ORDER 6 — step 6, lane pwa: round 4 finding R1

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-6 → sol (0.98), effort high (1.0), route follow.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red test pass (`apps/web/e2e/pwa.spec.ts` P17) without breaking any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa` (rebased on main `3d87fa0`), the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-6-evidence/reviews/r4-implementation.md` (R1, R2).

ALLOWED SCOPE (edit only these):
- `apps/web/lib/queries.ts` (`useSetPick` only)
- `apps/web/lib/sync.ts` (only to export what `useSetPick` needs, for example a way to read one game's queued value)

REQUIREMENT

The rule: every tap is on the phone (in the `nflpi_pick_queue` queue) from the moment he taps until the server has answered for that choice, and the last tap for a game is what the server ends up with.

Today the choice is queued inside the function passed to `orderedPickSend`. That function, and `mutationFn` itself because of the mutation `scope`, runs only when the earlier send for that game has finished. So a second tap made while the first is in flight is in memory only; if iOS closes the app then, it is lost and the older tap is sent on the next open.

1. Write the choice to the queue synchronously when he taps: `queuePick(v.gameId, v.team)` as the first statement of `onMutate`, before any `await`. Check in the installed TanStack Query version that `onMutate` runs at once for a mutation that is waiting on its `scope`; if it does not, stop and tell Jim instead of guessing.
2. The queue is written once per tap, at tap time. Remove the later `queuePick` calls in `mutationFn`.
3. When the tap's turn in the chain comes:
   - if the queue no longer holds this tap's value for the game (a newer tap replaced it, or something else removed it), send nothing and return `{ queued: true }` so `onSettled` does not refetch over the newer choice;
   - if offline or the server is marked unreachable: return `{ queued: true }` (already queued);
   - otherwise send. Success: `unqueueIfCurrent`, return `{ queued: false }`. Network error: leave it queued, return `{ queued: true }`. Any other error: `unqueueIfCurrent`, rethrow (today's rollback and toasts).
4. `onError` rollback: it must not put an older optimistic value on screen over a newer queued tap. The queue already wins in `effectivePick`, so do not add code for this unless a test shows a wrong display.

P17: he taps the away team (the request is held 2 s), then the home team. Within 1 s the queue must hold the home team and the home button must read as picked. The page is then reloaded mid-request; the next open must send the home team and empty the queue.

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-r4-findings.log`: P17 fails at "the second tap is on the phone before its turn to send". (That run also shows four timeouts in P2, P11, P12 and P13 from a machine under heavy load, load average 18 to 26; they are not part of this order. All of them passed in `wo5-e2e.log`.)

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo6`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup.
- Do not edit any file under `apps/web/e2e/`, any seam, or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- P4 and P11 to P16 exercise the same code and must stay green.
- Match the surrounding style. No `console.log`. Immutable updates.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, what you found about `onMutate` and `scope`, and any blocker.
