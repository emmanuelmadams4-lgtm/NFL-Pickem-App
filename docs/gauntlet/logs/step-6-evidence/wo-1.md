# CODEX WORK ORDER 1 — step 6, lane pwa: one offline layer, unreachable server, update prompt, storage status

BUILD_RUNG: gpt-6-sol, effort medium (try 1 of 2). JEV model:pwa:wo-1 → sol (0.79), effort high (0.67), route advisor; ADVISOR sonnet → sol, medium.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="medium"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the five red tests in `apps/web/e2e/pwa.spec.ts` (P2, P4, P6, P9 kept, P9 not kept) pass without breaking the six that pass today or any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, commit `__RED_SHA__` (the red spec). Never work in any other checkout.

ALLOWED SCOPE (edit only these; ask before touching anything else):
- `apps/web/public/sw.js`
- `apps/web/scripts/stamp-sw.mjs` (new)
- `apps/web/package.json` (the `build` script only; no dependency change)
- `apps/web/components/pwa.tsx`, `apps/web/components/toast.tsx`, `apps/web/components/providers.tsx`
- `apps/web/components/settings/settings-view.tsx` (the Offline section only)
- `apps/web/lib/sync.ts`, `apps/web/lib/persist.ts`, `apps/web/lib/queries.ts` (`useSetPick` only)
- `packages/shared/src/client.ts`

REQUIREMENT (the design is settled; do not add to it):

1. One offline layer (S17). `sw.js` no longer touches `/api/`: no API cache, no `respondWith` for `/api/*`, no `x-sw-cache` replay. API data offline comes only from the saved query cache (`lib/persist.ts`). Remove every use of `x-sw-cache` and the `nflpi-api-` cleanup that is then dead.

2. Build ID (B11). `public/sw.js` declares `const BUILD_ID = "__BUILD_ID__";` and every cache name is `nflpi-<kind>-${BUILD_ID}` (the `activate` cleanup of other `nflpi-` caches stays). `apps/web/scripts/stamp-sw.mjs` runs after `next build` (`"build": "next build && node scripts/stamp-sw.mjs"`), reads Next's build ID from `.next/BUILD_ID`, and replaces the placeholder in `out/sw.js`. It exits non-zero with a clear message if the ID file or the placeholder is missing. The stamped ID must match `^[A-Za-z0-9._-]{6,}$`.

3. Update flow (B11).
   - Worker: `skipWaiting()` on install only when there is no active worker yet (first install). An update waits. The existing `SKIP_WAITING` message still activates it.
   - Page (`pwa.tsx`): on `visibilitychange` to visible, call `reg.update()` (swallow its rejection). When a new worker is installed and waiting while a controller exists (also check `reg.waiting` at registration), show a prompt that does not time out: text "New version ready." and a button "Reload". The button posts `SKIP_WAITING` to the waiting worker and the page reloads once on `controllerchange`. A first install's `controllerchange` must not reload the page.
   - `toast.tsx`: give `toast` an optional action `{ label, onClick }`; a toast with an action stays until tapped. Button height at least 44px.

4. Precache. Add `/sheet/` to `PRECACHE_PAGES`. Every tab must open offline by tapping and by direct load with no chunk load error (P7); make the worker cache whatever route files that needs.

5. Unreachable server (B4).
   - `client.ts`: every call except `report` and `ask` (AI calls are slow by nature) gets `signal: AbortSignal.timeout(5000)` unless the caller passed a signal. Export the constant.
   - `sync.ts`: a small external store `serverReachable` (true at start). `trackedFetch` sets it true on any HTTP response and false when the fetch throws (network error, timeout); it still rethrows. `isNetworkError` also returns true for a `DOMException` named `TimeoutError` or `AbortError`. `markNetworkSync` only on `res.ok`.
   - Banner (`pwa.tsx`, the one existing `role="status"` banner, same style): offline → the existing "Offline · showing data from …"; online but unreachable → "Can't reach the server. Is Tailscale on? Showing data from …". Nothing when reachable.
   - While unreachable and the page is visible, re-check every 15 s with `api.health()`; when the server answers again, flush queued picks and invalidate queries.
   - `useSetPick`: when the phone is offline or the server is already known unreachable, queue the pick at once (no second 5 s wait). A timeout counts as a network error and queues.
   - `providers.tsx`, the "Cannot reach the API" card: add the line "Is Tailscale on?".

6. Storage (B5). After sign-in the app calls `navigator.storage.persist()` once per page load (guard for browsers without it). Settings › Offline gets a row labelled "Storage": granted → "Protected from automatic clearing."; not granted → "Not protected. The browser may clear saved data when the phone is low on space."; unsupported → "This browser does not say." Use the answer `persist()` returned.

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-pwa-spec.log` (red list in `docs/gauntlet/logs/step-6.md` section 2).

PROOF (the coordinator reruns all of it; your run is information, not proof):
- `npm run typecheck && npm run web:build` from the worktree root, and `grep -c '__BUILD_ID__' apps/web/out/sw.js` prints 0.
- If you can bind ports: `bash docs/gauntlet/logs/step-6-evidence/gate.sh wo1` (it uses the lane's own database on 127.0.0.1:15436). If you cannot, say so; do not claim e2e passed.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new abstraction with one user, no unrelated cleanup, no new files beyond the stamp script.
- Do not edit any file under `apps/web/e2e/`, any seam (`package.json` at the root, lockfiles, `packages/shared/src/api-types.ts`, `index.ts`, backend schemas/views, migrations, Dockerfile, conftest), or anything outside ALLOWED SCOPE.
- Match the surrounding style: `apps/web/components/pwa.tsx` is the reference; lines under 160 characters, one JSX attribute group per line as there. No `console.log`. Immutable updates.
- Keep error handling that prevents data loss: a queued pick is never dropped except on 404/409/422 as today.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
