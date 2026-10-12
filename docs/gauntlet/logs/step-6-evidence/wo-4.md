# CODEX WORK ORDER 4 — step 6, lane pwa: findings from review round 2

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-4 → sol (1.0), effort high (1.0), route follow.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the four red tests pass (`apps/web/e2e/pwa.spec.ts` P13, P14, P15; `apps/web/e2e/phone-layout.spec.ts` L11) without breaking the 25 that pass in those two files or any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, commit `dd66d0e`. Never work in any other checkout.

SOURCE: two fresh reviews of `d0d7b9e`, in `docs/gauntlet/logs/step-6-evidence/reviews/r2-implementation.md` (N1, N2, N3) and `r2-design.md` (C1).

ALLOWED SCOPE (edit only these; ask before touching anything else):
- `apps/web/lib/sync.ts`
- `apps/web/lib/queries.ts` (`useSetPick` only)
- `apps/web/components/week/kpi-strip.tsx` (the `phoneSub` strings only)

REQUIREMENT. The rule behind A to C: the last choice he made for a game is the one the server ends up with, and no choice is dropped without him being told.

A. N1, P13: `flushPicks` sends `{G: A}`. While that request is in flight, a newer choice `{G: B}` is queued (he went offline or the server was marked unreachable, and tapped). When the request for A resolves, by success or by 404/409/422, remove G from the queue only if the queue still holds the value that was sent. B stays queued and goes out on the next flush. Do not count or report it as saved while B is still waiting.

B. N2, P14: a direct send from `useSetPick` and a flush must never have two requests for the same game in flight at once, and an older choice must never reach the server after a newer one. Today the mutation `scope` orders taps against each other but not against a flush. P14: the flush is sending the older queued pick (the test holds that request for 2 s); he taps the other team while online; the server must end on his tap and the queue must end empty. Smallest correct way that you can show is safe: one per-game ordering shared by both paths in `sync.ts` (for example a per-game promise chain that both `flushPicks` and `useSetPick` send through), with the direct send removing the game's older queue entry before it sends. Tap-to-clear follows the same rule. Keep the optimistic update and the existing rollback on error.

C. N3, P15: an error that is not a network error on one game (500, 403) keeps that game queued, warns once as today, and the flush goes on to the next game. Stop the whole flush only on a network error or a 401.

D. C1, L11: on the phone the Model cell says "No live picks" while every card shows a live model pick. Change the phone caption to "None graded" for the Model cell and the Me cell. Desktop text unchanged. L2 must stay green (no caption wraps past two lines at 320).

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-r2-findings.log` (4 failed, 25 passed).

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo4`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup.
- Do not edit any file under `apps/web/e2e/`, any seam (root `package.json`, lockfiles, `api-types.ts`, `index.ts`, backend, migrations, Dockerfile) or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- P4, P11 and P12 exercise the same code and must stay green: an unreachable server queues and later syncs; a direct send clears the older queued pick; a 500 is warned once, kept and retried by the 15 s timer.
- Match the surrounding style. No `console.log`. Immutable updates.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
