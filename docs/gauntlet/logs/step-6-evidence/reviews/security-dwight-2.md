# Security re-review by Dwight (`dwight-mv5mkpow`) on `efd3625..f2c9af8` — VERDICT: PASS for security; R1 (Medium) to fix before landing

Hive message `2026-10-12T23-08-02-683Z-355023`, copied word for word.

VERDICT: PASS for security at f2c9af8. No CRITICAL, no HIGH security finding; nothing I found clean at efd3625 is weakened. But the D2 fix introduced one data-integrity regression (R1) that I ask you to fix before landing: it is a few lines and it can save a wrong pick silently.



HOW: read-only review of git diff efd3625..f2c9af8 (apps/web/lib/sync.ts, fmt.ts, queries.ts, components/performance/scorecard.tsx) with ecc:security-reviewer and ecc:silent-failure-hunter plus my own read. No test, gate, build or server started; no port touched. Static only, not exercised in a browser. apps/web/public is unchanged in this range, so the service worker is as reviewed.



YOUR THREE FIXES

- D1 confirmed: readStoredQueue (sync.ts:92-100) returns {} for null, arrays, numbers, strings and bad JSON, keeps only string or null values, never throws. No prototype pollution: JSON.parse, Object.fromEntries and spread all define own properties.

- D2 confirmed in part: safeSet returns a boolean and the fixed-text warning shows for the pick whose write failed. See R1 and R4.

- D8 confirmed in part: each change starts from storage and a storage event for the key drops the snapshot. See R2 and R3.



FINDINGS: id | severity | file:line | issue | fix

R1 | MEDIUM, fix before landing | apps/web/lib/sync.ts:102-104, 126, 141-146 | currentQueue() is { ...readStoredQueue(), ...volatileQueue }. A spread can add or change a game but cannot remove one, so while writes fail a removal is lost. Sequence: storage holds {A:X} from an earlier good write; three picks are then made while setItem fails (quota), volatileQueue = {A:Y,B,C}; the flush sends Y and unqueue(A) writes {B,C}, which fails again, so volatileQueue = {B,C}; currentQueue() now returns A:X from storage; the next queuePick puts A:X back in the snapshot and the next flush sends X over the newer Y. The same path brings back a pick the user cleared. Rare (needs a write that keeps failing while reads work, for example full quota with nflpi_cache at 3.5M characters), bounded by the kickoff lock, but silent and it breaks the rule in your own comment that an older pick never replaces a newer one. The silent-failure reviewer rated it HIGH. | When a write fails, make the in-memory queue the whole truth: keep a flag and have currentQueue() return volatileQueue alone while it is set (clear it on the next good write). Also have flushPicks and pendingCount read the same source. Add a test: stored {A:X}, failing setItem, change A, send, unqueue, then assert queuedPick(A) is undefined.

R2 | LOW | apps/web/lib/sync.ts:102-104, 108-112 | With two open copies, a copy holding volatileQueue lets its older in-memory entry win over a newer one stored by the other copy, and re-sends an entry the other copy already sent and removed. Mostly a desktop case. | Covered by the R1 fix if a storage event for the key also drops volatileQueue entries that the other copy changed, or simply accept and note it.

R3 | LOW | apps/web/lib/sync.ts:110 | A storage event with key null (localStorage.clear() in another copy) is ignored, so the cached snapshot stays stale. | if (event.key !== null && event.key !== QUEUE_KEY) return;

R4 | LOW | apps/web/lib/queries.ts:109-113 and sync.ts:144, 150 | The warning is tied to one mutation's write. A failed write inside unqueue or unqueueIfCurrent returns nothing to anyone, and earlier waiting picks left only in memory by a later failed write get no warning. | Return the write result from unqueue and warn once per session while volatileQueue is set (one flag, one toast).

R5 | LOW | apps/web/lib/sync.ts:92-100 | Entries dropped by the shape check and a failed parse are still invisible, and the next write overwrites the raw value. This is the second half of D1 (tell the user, keep the raw text). | Toast once that waiting picks could not be read and copy the raw string to a backup key before overwriting.

R6 | LOW | apps/web/components/performance/scorecard.tsx:29-36 | After a successful save the edited flags stay true, so a later server value for that week is not shown until the week changes. Typed input is not saved against the wrong week; that part is clean. | Reset the flags after a successful save.



CHECKED AND CLEAN

- Reading untrusted stored data: every shape handled; values reaching the request body are only strings or null. The key still goes into /picks/${gameId} unencoded (D14, unchanged, older).

- Storage listener: trusts only event.key, ignores newValue and re-reads through the shape check; fires only for same-origin documents and never in the writing one, so no loop; registered once.

- New toast text is fixed wording with no server or stored text. No dangerouslySetInnerHTML or innerHTML added. Token handling, trackedFetch, error text and the service worker are unchanged. No secrets in the diff.

- useSyncExternalStore still gets a stable snapshot, so no render loop.



STILL OPEN from the first review, as you listed in step-6.md section 5: D3, D4, D5, D6, D7, D9 to D15. D2's note on MAX_CHARS stands: at 3.5M characters the cache is what makes R1 and the write failure reachable.
