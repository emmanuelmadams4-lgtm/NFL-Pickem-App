# CODEX WORK ORDER 8b — step 7, lane alerts: say so when the stored queue had to be dropped (integrator's condition on work order 8)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: test P23c in `apps/web/e2e/pwa.spec.ts` goes green; P22, P23 (both), P23b stay green. No test changes.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message (work order 8 is in it).

ALLOWED SCOPE: `apps/web/lib/sync.ts` (`writeQueue` and one small exported reader), `apps/web/lib/queries.ts` (the `onSettled` branch of the pick mutation that already shows "Could not save this pick on the phone…"). Nothing else.

THE RULING (integrator, 2026-10-13): work order 8's last resort stands: when storage refuses every write and still holds an older pick for the same game, the stored queue is removed. Condition: he sees a clear error on screen that his waiting picks could not be stored.

REQUIRED BEHAVIOUR
1. `writeQueue` remembers whether its last call had to remove the stored queue (the last resort branch), and `sync.ts` exports one small function to read that.
2. In the pick mutation's `onSettled`, where a queued pick was not stored (`ctx.persisted === false`): if the stored queue had to be removed, show this toast, tone "bad", exactly: `Waiting picks could not be stored on this phone. Keep the app open until they sync, or enter them again when you are online.` Otherwise the existing toast, unchanged.
3. Nothing else changes: the in-memory queue still carries every waiting pick while the app stays open.

PROOF (the coordinator reruns it; you cannot bind ports, so say so): `npm run typecheck`.

CONSTRAINTS: smallest diff (Ponytail); no new dependency; no test edits; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the changed lines, the proof command with its exit code, any blocker.
