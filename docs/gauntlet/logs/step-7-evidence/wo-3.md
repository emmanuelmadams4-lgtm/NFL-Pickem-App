# CODEX WORK ORDER 3 — step 7, lane alerts: the phone side of alerts (keep the subscription alive, test alert button, reminder wording, tap opens the game)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).
Launch (prompt on stdin, never as an argument): `codex exec -m <model> -c 'model_reasoning_effort="<effort>"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red browser tests in `apps/web/e2e/alerts.spec.ts` (A1, A2, A3, A4, A5) pass without breaking any other browser test. A1b and A4b pass today and must stay green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-7.md` section 2 (criteria A1 to A5). The server side is done: `POST /api/push/test` exists and its types are generated (`PushTestOut`, `PushTestResult` in `packages/shared/src/api-types.ts`).

ALLOWED SCOPE (edit only these):
- `apps/web/lib/push.ts` (new; the one new file)
- `apps/web/components/settings/alerts.tsx`
- `apps/web/components/pwa.tsx` (one small component that keeps the subscription alive; nothing else in the file)
- `apps/web/components/app-shell.tsx` (only to mount that component beside `<PickSync />`)
- `apps/web/public/sw.js` (the `notificationclick` handler only)
- `packages/shared/src/client.ts` (one `pushTest` call and its exported type)

NOT ALLOWED: anything under `apps/web/e2e/`, `backend/`, `scripts/`, `packages/shared/openapi.json`, `packages/shared/src/api-types.ts`, any package or lock file.

REQUIREMENT

A. Shared client. `pushTest: () => call<PushTestOut>("/push/test", { method: "POST" })`, with `PushTestOut` exported the way `PushSubscriptionIn` is.

B. One home for the subscription code: `apps/web/lib/push.ts`. Move `urlBase64ToUint8Array` there (do not keep a copy in `alerts.tsx`) and add the function that keeps this device's subscription alive. Given the server's public key (`meta.push_public_key`) and the API client:
   - Do nothing when push is not supported, the key is empty, `Notification.permission` is not `"granted"`, there is no service worker registration, or the device has no subscription (alerts are off: A1b).
   - The device has a subscription made with the server's current key (compare `subscription.options.applicationServerKey` with the key, as bytes): send it to the server with `api.pushSubscribe(sub.toJSON())`. Every open, whether or not the server already has it (A1: the server's row is re-created when it was lost).
   - The device has a subscription made with a different key (A2): `unsubscribe()` it, subscribe again with the server's key (`userVisibleOnly: true`), send the new one with `pushSubscribe`, and tell the server to drop the old address with `pushUnsubscribe(oldEndpoint)`. A failure to drop the old address must not undo the new subscription.
   - It never asks for permission and never shows anything. A failure is swallowed silently here, on purpose: the next open tries again, and the Settings screen is where the owner sees the state. Say so in one comment.

C. Keep-alive component in `pwa.tsx`, mounted once in `app-shell.tsx` beside `<PickSync />`: runs B once per app open, when the meta query has data. It renders nothing. Use the existing meta query (`keys.meta`); do not add a second request for meta.

D. Settings, Alerts section (`alerts.tsx`):
   - `turnOn` uses the helper from B for the key conversion. Behaviour unchanged.
   - When alerts are on (`info.subscribed`), a "Send test alert" button sits beside "Turn off alerts". With alerts off there is no such button (A4b). While the call runs the button shows its loading state.
   - The result is one line with `role="status"`, inside the section, replaced by each new result:
     - every device took it: `Delivered to 1 device.` / `Delivered to 2 devices.`
     - `devices` is 0, or `configured` is false: `The server has no device to send to. Turn alerts off and on again.`
     - otherwise: `Not delivered.` or, when some took it, `Delivered to 1 of 2 devices.`, followed for each failed result by ` <host>: <error> (<status>)`; leave out ` (<status>)` when the status is null. Example: `Not delivered. fcm.googleapis.com: The push service refused the alert. (403)`.
   - The call itself fails (network, 401, 500): the existing `role="alert"` line reads `Could not send the test alert. <errorMessage(e)>`, and the status line is cleared.
   - After a result, refresh meta (`qc.invalidateQueries({ queryKey: keys.meta })`): the server may have dropped a device.
   - Reminder block: the label "Kickoff reminder" becomes `Game day reminder`; the help text becomes `One alert on each game day, before that day's first kickoff.`; the words "No pick yet" are gone from the section. The select keeps its label "Remind me" and the four choices (Off, 30 minutes before, 1 hour before, 3 hours before). `meta.reminder_minutes` is now always a number (60 until he changes it). Toasts: `Game day reminder is off.` / `Game day reminder set to 1 hour before.`
   - The section note becomes `Pick flips, big changes before kickoff, QB news, and a reminder on game days.`
   - Use the design tokens and components already in the file (`Button`, `Chip`, `Notice`, `text-subtle`, `text-bad`). No new colour, size or component. Touch targets stay at the size `Button` gives.

E. Service worker (`sw.js`, `notificationclick` only): tapping an alert must send the open app window to the alert's link even when the browser refuses to focus the window. Today a refused `focus()` rejects and the navigation never runs. Try to focus, ignore a refusal, then navigate as now; `openWindow` stays the path when no window is open. Nothing else in `sw.js` changes.

FAILING EVIDENCE: `docs/gauntlet/logs/step-7-evidence/red-wo3.log`. A1 no subscription sent on open; A2 the old key is kept; A3 the alert shows but the tap leaves the page on `/`; A4 "Game day reminder" not found; A5 no "Send test alert" button.

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo3`.

CONSTRAINTS:
- Smallest correct diff. No new dependency. One new file only (`apps/web/lib/push.ts`). No unrelated cleanup.
- Never put a subscription endpoint, a key or the token in a message on screen, in a toast or in the console. No `console.log`.
- Immutable updates; match the surrounding style; strict TypeScript, no `any`.
- No prediction or alert logic in the client: it shows what the API returns.
- If an existing test pins something that must change, stop and tell Jim which test.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
