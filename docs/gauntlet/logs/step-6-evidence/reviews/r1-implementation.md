# Implementation reviewer, round 1 (on `7611d89`) — VERDICT: FAIL

Fresh subagent, read-only, given the diff, CLAUDE.md, design.md, the step log and both work orders.

| id | sev | file:line | what is wrong | fix |
|---|---|---|---|---|
| F1 | High | `apps/web/components/pwa.tsx:118-120`, `apps/web/lib/queries.ts:75-81` | The 15 s timer only flushes while `serverReachable` is false. Any ordinary query success flips it to true through `trackedFetch` without flushing, so queued picks sit until the next `online` or `visibilitychange` event and can hit 409 at kickoff. The direct send path never unqueues, so with A queued, tapping B sends B, the card still shows A as waiting, and a later flush overwrites B with A. | Flush when reachability turns true or `pendingCount() > 0`; unqueue the game on a direct success. |
| F2 | High | `apps/web/components/week/game-card.tsx:87` | ", next kickoff" is `text-accent-ink/75` (#0a0a0a) but sits in the card body on `bg-surface` (#151515), not the lime band. Invisible in the dark theme. | Use `text-text-2` or `text-text`. |
| F3 | High | `apps/web/components/pickers.tsx:44,54`, `apps/web/components/ui.tsx:203-205` | `hidden` loses to the Button base `inline-flex` in the built CSS. The previous/next week buttons still show on the phone at 36x36, down from 44x40. | Use `max-lg:hidden`, or restore the 44px phone sizes. |
| F4 | Medium | `apps/web/components/game/game-view.tsx:82` | The mask is fixed to the scroll container with no end padding, so at scroll end the last tab is still faded across the right 15%. | Add end padding to the list, or drop the mask at scroll end. |
| F5 | Medium | `apps/web/components/pwa.tsx:32-47` | The `statechange` listener is attached only inside `updatefound`. A worker already in `reg.installing` when `ready` resolves is never watched, so no toast that session. Frequency not verified. | After `ready`, also attach to `reg.installing`. |
| F6 | Medium | `apps/web/components/pwa.tsx:111`, `apps/web/lib/sync.ts:162-163` | `flushPicks` rethrows 401/403/500 and the bare `.catch(() => {})` swallows it. The pick stays "waiting" with no toast and no timer retry. | Toast on non-network errors. |
| F7 | Medium | `packages/shared/src/client.ts:58`, `apps/web/components/ui.tsx:11-15` | The 5 s timeout also covers `importPicks`, `refresh` and `setPoints`. A slow response marks the server unreachable and shows a false banner, and `errorMessage` prints the raw "signal timed out". | Exempt or lengthen slow writes; map `TimeoutError` to the "could not reach" text. |
| F8 | Low | `apps/web/components/toast.tsx:30-31`, `apps/web/components/pwa.tsx:21` | Action toasts cannot be dismissed and are not deduplicated; two deploys stack two "New version ready." toasts. If another tab already activated the worker, Reload does nothing. | Dedupe by message, add a dismiss, fall back to `location.reload()`. |
| F9 | Low | `packages/shared/src/client.ts:58` | A caller-supplied signal replaces the timeout. No caller passes one today. | `AbortSignal.any([...])`. |
| F10 | Low | `apps/web/components/week/week-board.tsx:152` | The phone "Updated" copy drops the ", refreshing" suffix. | Reuse one element. |
| F11 | Low | `apps/web/app/globals.css:148` | One-off `12px` in `scroll-padding-top`. | Use a spacing token. |

Checked and clean: the worker leaves `/api/` alone, cache names use `BUILD_ID`, `skipWaiting` only with no active worker, old caches removed on activate, no reload loop and no first-install reload; `stamp-sw.mjs` exits 1 on failure; `PickSync` mounts only when signed in and clears its timer; health checks cannot pile up; `flushing` blocks a double flush; no unhandled rejections; `persist()` asked once and safe in prerender; hidden duplicate copies are `display:none`; `scroll-mt-16` plus `scroll-padding-top` clears the sticky section nav; the toast action is a real button in the live region.

**Largest problem:** F1. Queued picks can sit unsynced while the server is reachable, and a stale queued pick can overwrite a newer one.
