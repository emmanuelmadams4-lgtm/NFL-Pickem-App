# Security review by Dwight (`dwight-mv5mkpow`) on `efd3625` — VERDICT: PASS

Hive message `2026-10-12T22-43-09-017Z-d41989`, copied word for word.

VERDICT: PASS for security at efd3625. No CRITICAL, no HIGH. Nothing blocks landing on security grounds. Seven MEDIUM findings concern picks being lost or mislabelled; they map to owner rules, so please turn D1 to D5 into tests and work orders before or right after landing (your call with god).

HOW: read-only review of git diff 3d87fa0..efd3625 (apps/web, packages/shared/src/client.ts, apps/web/scripts) with ecc:security-reviewer and ecc:silent-failure-hunter plus my own full read of sw.js, stamp-sw.mjs, sync.ts, persist.ts, pwa.tsx, client.ts and the queries, toast, settings and providers hunks. I did not run the gate or any test, started nothing, touched no port. The worktree HEAD is now 893acb9 (design.md only, 3 lines); this verdict covers efd3625. Not verified in a running browser. Severities are mine: I lowered some of the silent-failure reviewer's HIGHs because the app is single-user on one phone and the server enforces the kickoff lock.

FINDINGS: id | severity | file:line | issue | fix

D1 | MEDIUM | apps/web/lib/sync.ts:90-97 | The queue is read with JSON.parse and no shape check. A stored null, number or array passes the parse; `gameId in pending` (sync.ts:161) and Object.keys (sync.ts:144, called from the 15 s timer in pwa.tsx:126) then throw on every load until the key is deleted by hand. A parse failure resets the queue to {} and the next write erases the picks with no notice. Maps to ECC 'never trust file or stored content' and CLAUDE.md 'never silently swallow'. | After parse, require a plain object and keep only entries whose value is a string or null; otherwise use {}, keep the raw text under a second key and toast once that waiting picks could not be read.

D2 | MEDIUM | apps/web/lib/sync.ts:100-104 and apps/web/lib/fmt.ts:48-54 | safeSet swallows a storage error and returns nothing; writeQueue still notifies, so the pick shows as waiting but exists only in memory and is lost on reload or app kill. Likelihood rises because persist.ts:10 lets nflpi_cache take 3.5M characters of the same quota. Maps to Ponytail 'never trim error handling that prevents data loss'. | Make the queue write report failure (return a boolean or read the key back) and toast 'Pick is held only while the app stays open'. Lower MAX_CHARS so the cache cannot starve the queue.

D3 | MEDIUM | packages/shared/src/client.ts:79-81, apps/web/lib/queries.ts:80-82, apps/web/lib/sync.ts:182-184 | Any 200 counts as success: a non-JSON 200 (proxy or sign-in page) returns text typed as T, the pick is unqueued and 'saved' is toasted, and a string can be cached as a Week. The health probe (pwa.tsx:115) has the same weakness. Tailscale HTTPS makes it unlikely, not impossible. | In call(), throw ApiError(502, 'unexpected response') when a JSON route answers with a non-JSON type. For setPick, check the returned team equals the one sent before unqueueing.

D4 | MEDIUM | apps/web/lib/sync.ts:187-196 with pwa.tsx:112-127 | A 401 during a flush never reaches the QueryCache or MutationCache onError handlers (providers.tsx:30-39), so it does not sign out; /api/health passes without a token, so the flush retries every 15 s for as long as a pick waits. 403 and 5xx take the same endless path. warnedGameId holds one id, so two failing games re-toast in turn. | On a flush 401 call the same sign-out handler. Treat 403 as final and tell the user. Back off on 5xx. Make warnedGameId a Set.

D5 | MEDIUM | apps/web/lib/sync.ts:188-190, 206-207 | 409, 422 and 404 are all reported as 'locked at kickoff', which is false for 422 and 404, and no game is named. When some picks saved and some were dropped, the `else if` hides the saved count. A write that timed out but landed, then retried after kickoff, is reported as 'not saved' although it is saved (client.ts:58-60). Maps to 'never invent data' and the owner rule that the user must know what was saved. | Separate counters and messages, show both toasts, and on a flush 409 refetch the week and count the pick as saved if the server's pick equals the queued team.

D6 | MEDIUM | apps/web/components/providers.tsx:51-54 | Sign-out clears the token and nflpi_cache but not nflpi_pick_queue, nflpi_last_sync or the in-memory snapshot, so waiting picks are sent under whatever token signs in next. Single user, so low harm, but it is state that outlives the session. | Clear the queue and snapshot in onSignOut, or say on the sign-in screen that N picks are still waiting.

D7 | MEDIUM | apps/web/components/toast.tsx:32-34 | Plain toasts vanish after 5 s and only the last two are kept, so 'Pick not saved' can be pushed out by a later 'saved' toast within seconds. | Keep bad and warn toasts until dismissed, or never evict them.

D8 | LOW | apps/web/lib/sync.ts:90-104 | The queue snapshot is cached per page and written back whole, and `flushing` is per page; a second open tab can overwrite a pick queued in the first. On the installed iPhone app there is one page, so this is mostly a desktop browser case. Older than this step. | Re-read storage inside each read-modify-write and listen to the storage event.

D9 | LOW | apps/web/public/sw.js:26-41 and pwa.tsx:70 | A failed precache or a failed worker registration is silent, so the app can look installed with no offline shell; with fallbackUrl '/' (sw.js:158) an offline visit to an uncached page gets the home page HTML. | Count precache failures and tell the page; show 'Offline not ready' in Settings.

D10 | LOW | apps/web/public/sw.js:85-95, 102, 124 | cache.put is awaited unguarded in cacheFirst, so a storage error fails a request whose fetch succeeded; trim() promises float. | try/catch around put and still return res; add .catch to the floating promises.

D11 | LOW | apps/web/lib/queries.ts:84-90 | A 502, 503 or 504 on a direct pick write drops the queue entry and rolls back (the user is told), while the flush keeps 5xx queued. Behind Tailscale Serve a stopped backend answers 502. | Treat 502, 503, 504 and 408 like a network error in both paths.

D12 | LOW | apps/web/lib/sync.ts:37, 62-72 and pwa.tsx:93 | serverReachable starts true and any HTTP reply sets it true; one slow GET over 5 s sets it false and the next pick is queued without a try. The banner's fallback age uses dataUpdatedAt, which an optimistic update sets to now. | Start as unknown; use lastNetworkSync only, else 'an earlier session'.

D13 | LOW | apps/web/components/pwa.tsx:26-31 | The Reload toast is removed on click; if the waiting worker never activates, nothing happens. | Reload after a short timeout as a fallback.

D14 | LOW (older than this step) | packages/shared/src/client.ts:89-94 | gameId goes into the URL path without encodeURIComponent, and it can now come from localStorage. Needs same-origin write access, which already exposes the token. | encodeURIComponent(gameId).

D15 | LOW (older, unchanged, not re-reviewed in depth) | apps/web/public/sw.js:182 | A push payload's url is resolved with new URL(url, origin), so an absolute URL opens another site. Only our own server can send pushes. | Open only same-origin targets.

CHECKED AND CLEAN

- Worker caching: GET only (sw.js:139); /api/ returns before any handler (sw.js:150), so no API body and no Authorization-bearing request is cached or answered. Cross-origin is cached only for a.espncdn.com or image requests. cacheFirst and networkFirst store only ok responses, so no error page is stored under an asset URL. The CACHE_URLS message accepts only same-origin /_next/static/ and /icons/ paths, checked after URL normalisation; cache.add sends no token and rejects non-ok.

- Scope and update: scope '/', sw.js served no-cache (backend api/main.py:363). skipWaiting at install only when no worker is active; later updates wait for the Reload tap; controllerchange listener is once, so no reload loop. Old nflpi- caches are removed on activate.

- stamp-sw.mjs: id from .next/BUILD_ID, checked against ^[A-Za-z0-9._-]{6,}$ before substitution, fixed paths, exit code 1 on failure. The Dockerfile builds with `npm run build -w apps/web` (Dockerfile:10), so the stamp runs in production.

- localStorage: nflpi_cache holds query data for at most 7 days with a version check and is cleared on sign-out; the token is still in nflpi_token, unchanged by this step.

- Queued picks: one entry per game (latest wins), sent in order per game, re-checked against the queue before sending. PUT and DELETE are safe to repeat. A pick after kickoff depends on the server's 409, which this step does not change. A 5 s abort leaves the pick queued and re-sent.

- Error text: server detail is shown as React text; no dangerouslySetInnerHTML or innerHTML in apps/web. The token is never rendered.

- Secrets: none in the diff or evidence logs. Only the fixture 'e2e-token' and the lane database login nflpi:nflpi on 127.0.0.1:15436 in gate.sh. No token in any URL.

- No backend, auth, schema or dependency change, as you said.
