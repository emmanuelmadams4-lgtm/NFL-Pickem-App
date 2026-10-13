# CODEX WORK ORDER 8 — step 7, lane alerts: a refused queue write keeps the other games' stored picks (critic B3)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: test P23b in `apps/web/e2e/pwa.spec.ts` goes green, and P23 (both tests of that name) stays green. No test changes.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

ALLOWED SCOPE: `apps/web/lib/sync.ts`, function `writeQueue` (and a small helper beside it if it reads better). Nothing else.

THE DEFECT: when the phone refuses to store the new queue, `writeQueue` removes the stored queue and tries once more. If that is refused too, waiting picks for OTHER games that were safely stored now live only in memory: close the app and they are gone. Before work order 1 they survived. Work order 1 removed the stored copy for a good reason, which must still hold: an older stored pick for the SAME game must never be sent over a newer one (P23).

REQUIRED BEHAVIOUR when the first write is refused:
1. Read what is stored. Build the fallback: the stored queue without every game whose value in the new queue differs from the stored one (changed, added or removed in the new queue). That drops stale copies and keeps the other games' waiting picks.
2. If the fallback equals what is stored, leave storage alone. Otherwise write the fallback (it is never longer than what is stored).
3. Only if that write is refused as well and storage still holds a stale copy of a changed game: remove the stored queue, as today. Losing the other picks is then the lesser harm than sending a wrong pick.
4. As today: the in-memory queue (`volatileQueue`) carries the new queue until a later write succeeds, listeners are told, and the function answers whether the NEW queue was stored.

PROOF (the coordinator reruns it; you cannot bind ports, so say so): `npm run typecheck`.

CONSTRAINTS: smallest diff (Ponytail); immutable updates; no new dependency; no test edits; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the changed lines, the proof command with its exit code, any blocker.
