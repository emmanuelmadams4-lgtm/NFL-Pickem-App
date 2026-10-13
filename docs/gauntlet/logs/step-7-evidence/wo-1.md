# CODEX WORK ORDER 1 — step 7, lane alerts: the two step 6 follow-ups (pick queue after a refused write; offline banner time)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).
Launch (prompt on stdin, never as an argument): `codex exec -m <model> -c 'model_reasoning_effort="<effort>"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red tests `apps/web/e2e/pwa.spec.ts` P23 and P24 pass without breaking any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-6-evidence/reviews/security-dwight-3.md` (R7) and `reviews/critic-angela-2.md` (F6).

ALLOWED SCOPE (edit only these):
- `apps/web/lib/sync.ts`
- `apps/web/lib/fmt.ts` (only to add a small storage helper beside `safeSet`, if you need one)
- `apps/web/components/pwa.tsx` (`OfflineBanner` only)

REQUIREMENT

A. Pick queue (P23). `writeQueue` keeps the queue in memory when `safeSet` fails, but the older queue stays in storage. If the app is closed before a write succeeds, the next open reads the older queue and sends an older pick over a newer one.
   When the write of the queue fails: remove the stored queue key, then try the write once more. If the second write succeeds, storage is current and the in-memory fallback is cleared, as after any good write. If it still fails, the in-memory queue stays the whole queue (work order 8 of step 6), and storage holds no queue rather than an older one. Removing must never throw. `writeQueue` still returns whether the queue is stored.
   Keep everything else: the toast "Could not save this pick on the phone. Keep the app open until it syncs." when a waiting pick is not stored (P19), the `storage` listener, the shape check, the per-game send order.

B. Offline banner (P24). `OfflineBanner` shows "showing data from <time>". Today the time is `lastNetworkSync()`: the last good reply of any kind, the health check included. A week saved five hours ago and opened offline can read "just now".
   The time must be the age of the data on screen: the oldest `dataUpdatedAt` among the queries that are being shown (queries with at least one observer and with data). No such query: "an earlier session", as today. The banner must be right after an offline reload, when the saved queries arrive a moment after the banner first renders, so it has to follow the query cache while it is shown, not read it once.
   The words before it stay: "Offline" or "Can't reach the server. Is Tailscale on?", then " · showing data from ".
   If nothing else uses `lastNetworkSync` and `markNetworkSync` afterwards, delete them and the `nflpi_last_sync` write; do not leave dead code.

FAILING EVIDENCE: `docs/gauntlet/logs/step-7-evidence/red-wo1.log` — P23 fails at "the older stored pick was not sent on reopening"; P24 fails at "showing data from 5h ago".

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo1`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup.
- Do not edit any file under `apps/web/e2e/` or `backend/`, any seam, or anything outside ALLOWED SCOPE. `backend/tests/test_alerts.py` is red on purpose (work order 2); leave it. If an existing test pins something that must change, stop and tell Jim which test.
- P3, P4 and P11 to P22 exercise the queue and the banner and must stay green.
- Match the surrounding style. No `console.log`. Immutable updates: never edit in place an object returned by `currentQueue()` or `readQueue()`.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
