# CODEX WORK ORDER 7 — step 6, lane pwa: findings from the security review and the fresh-critic gate

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-7 → sol (0.98), effort high (0.98), route follow.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red tests pass (`apps/web/e2e/pwa.spec.ts` P18 for `null` and `7`, P19, P20; `apps/web/e2e/sheet.spec.ts` U3b) without breaking any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-6-evidence/reviews/security-dwight.md` (D1, D2, D8) and `reviews/critic-angela-1.md` (A1, B1, B2, C5).

ALLOWED SCOPE (edit only these):
- `apps/web/lib/sync.ts`
- `apps/web/lib/fmt.ts` (`safeSet` only)
- `apps/web/lib/queries.ts` (`useSetPick` only)
- `apps/web/components/pwa.tsx` (`PickSync` only)
- `apps/web/components/performance/scorecard.tsx`

REQUIREMENT

A. Damaged stored queue (D1, C5), P18. `readQueue` trusts whatever `JSON.parse` returns. A stored `null` or `7` makes the app throw on every load until the key is deleted by hand. After parsing, accept only a plain object (not null, not an array) and keep only entries whose value is a string or null; anything else reads as an empty queue. Never throw from reading the queue.

B. The phone cannot store the queue (D2, B1), P19. `safeSet` swallows a failed write, so a waiting pick is shown as waiting but lives only in memory and is lost on reload. Make the queue write report failure (for example `safeSet` returns a boolean; other callers may ignore it). When a pick is left waiting (offline, server unreachable, or a network error on the send) and its write to the phone failed, show one toast, tone warn: "Could not save this pick on the phone. Keep the app open until it syncs." Not on a tap that is sent and saved at once. The pick stays in the in-memory queue and is still sent as today.

C. Two open copies of the app (B2, D8), P20. The queue is a per-page snapshot written back whole, so the Home Screen app and a Safari tab overwrite each other's waiting picks.
   1. Every queue change (`queuePick`, `unqueue`, `unqueueIfCurrent`) starts from what is in storage now, not from the page's older snapshot, and changes only its own game.
   2. Listen for the `storage` event for the queue key: drop the snapshot and notify the listeners, so the other copy shows the pick at once (its button reads as picked, waiting). Add the listener once, in the browser only.
   3. Keep `useSyncExternalStore` stable: `readQueue` must return the same object until the queue really changes.
   P20: two pages, offline; a pick for one game in the first, a pick for another game in the second; storage must hold both, the first page must show the second page's pick, and after going online both reach the server.

D. Rank form (A1), U3b. In `scorecard.tsx` the effect on `[q.data, selectedWeek]` overwrites the rank and leader fields whenever the scorecard arrives, wiping what he has already typed; the save is then blocked by the empty required field. Fill the fields from the scorecard only when he has not typed in them for the selected week. Choosing another week still loads that week's saved values. After a successful save the fields keep what he saved. Smallest change that does this; no new state library.

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-verification-findings.log` (5 failed: P18 `null`, P18 `7`, P19, P20, U3b; 30 passed). P20 in that log hit the 30 s limit; rerun alone with a 90 s limit it fails at "both picks are still waiting" (the first page's pick is missing from storage).

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo7`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup.
- Do not edit any file under `apps/web/e2e/`, any seam, or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- P4 and P11 to P17 and P21 exercise the queue and must stay green; U3 exercises the rank form and must stay green.
- Match the surrounding style. No `console.log`. Immutable updates.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
