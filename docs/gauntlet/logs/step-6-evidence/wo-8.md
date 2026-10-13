# CODEX WORK ORDER 8 — step 6, lane pwa: an older stored pick comes back while the phone cannot store the queue

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-8 → sol (1.0), effort high (1.0), route follow.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red test `apps/web/e2e/pwa.spec.ts` P22 pass without breaking any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-6-evidence/reviews/security-dwight-2.md` (R1, Medium, "fix before landing"). The second fresh critic found the same thing (F1).

ALLOWED SCOPE (edit only this): `apps/web/lib/sync.ts`, the "offline pick queue" part only.

REQUIREMENT

`currentQueue()` returns `{ ...readStoredQueue(), ...volatileQueue }`. A merge can add or change a game but cannot remove one. While writes to the phone keep failing, a game removed after its pick was sent is still in storage with its older value, so it comes back as waiting and the next flush sends the older pick over the newer one, with no message.

1. While a queue write has failed, the in-memory queue is the whole queue: do not read storage under it. It stops being the source on the next write that succeeds.
2. `queuePick`, `queuedPick`, `unqueue`, `unqueueIfCurrent`, `pendingCount`, `usePendingPicks` and every check in `flushPicks` must then agree on one source. A removed game stays removed for all of them.
3. Keep work order 7's behaviour: when writes succeed, every change starts from what is in storage now (two open copies, P20); the `storage` event still drops the snapshot; `readQueue` returns the same object until the queue really changes; a damaged stored queue reads as empty (P18).

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-r1-dwight.log` — P22 fails at "the older stored pick was not sent over the newer one": expected `LV`, received `MIA`. P19 and P20 pass in the same run.

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo8`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup. Do not fix the Low findings in the same report (R2 to R6); they are scheduled separately.
- Do not edit any file under `apps/web/e2e/`, any seam, or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- P4 and P11 to P21 exercise the queue and must stay green.
- Match the surrounding style. No `console.log`. Immutable updates.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
