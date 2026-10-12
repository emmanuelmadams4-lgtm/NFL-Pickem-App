# Security confirmation 3 (Dwight), fix 9670cdf, HEAD 3de3036

Hive message `2026-10-12T23-31-21-266Z-0c2c0e`, 2026-10-12T23:31:21.266Z. Verbatim.

**Step 6: R1 fix at 9670cdf confirmed, PASS for landing on security (one older MEDIUM, R7, for the backlog)**

VERDICT: PASS for landing, on security grounds, at 9670cdf (HEAD 3de3036 adds only docs and evidence logs on top; no file under apps, packages, backend or scripts changed after 9670cdf). No CRITICAL, no HIGH security finding. R1 is closed within one app session.



HOW: read-only review of git diff f2c9af8 9670cdf -- apps/web with ecc:security-reviewer and ecc:silent-failure-hunter plus my own read of sync.ts lines 84-155 at 9670cdf. I started no test, gate or server. Static only. I read your red log docs/gauntlet/logs/step-6-evidence/red-r1-dwight.log: P22 failed before the fix with Expected LV, Received MIA, which settles the reviewer's doubt about whether P22 can fail without the fix. I did not re-run your green gate.



R1 CONFIRMED CLOSED

- currentQueue() is now volatileQueue ?? readStoredQueue() (sync.ts:102-104). While a write has failed, memory is the whole queue, so a removal holds. The empty object case holds too: ?? falls through only on null or undefined.

- unqueue copies before deleting (sync.ts:141-146). That copy is required: currentQueue() can now return the same object as snapshot, and without it the cached queue would be changed in place. No other caller mutates it; snapshot and volatileQueue are always replaced by a new object in writeQueue.

- A later good write stores the full queue and clears volatileQueue, so storage and memory match again.

- No security weakness added: the shape check still guards the only storage read; no prototype pollution; nothing new reaches the request path.



NEW FINDINGS: id | severity | file:line | issue | fix

R7 | MEDIUM, not blocking, older than this fix | apps/web/lib/sync.ts:122-129 | The same symptom survives an app restart. Sequence: storage holds {A:X}; writes fail; the user picks A:Y; Y is sent; the removal cannot be written, so the phone still holds {A:X}; the app is closed or reloaded; volatileQueue is gone, readStoredQueue() returns {A:X}; PickSync flushes on load and sends X over Y. It existed at efd3625 too (the stale value stayed on disk then as well), so it is not a regression, and it needs the same rare condition as R1 plus a restart before any good write. But it ends with an older pick saved after the user saw the newer one saved. | In writeQueue, when setItem fails: try localStorage.removeItem(QUEUE_KEY) in a try/catch, then setItem once more. Removing frees the key's own space, so a smaller queue then fits. Keep volatileQueue set unless the second setItem succeeds. Add a P22 step: reload after the failed writes and assert the server still has the newer pick (it would fail today). Please add it to the list for god with R2 to R6.

R8 | LOW | apps/web/e2e/pwa.spec.ts:451-481 | P22 never asserts that a queue write was attempted and failed, so if the mutation path changed it could pass without exercising the fix. | Count the throws inside the setItem stub and assert the count is above 0.



UNCHANGED AND STILL OPEN, as in your step log: R2 (while the phone cannot store the queue, a change from a second open copy is not seen until a write succeeds; this fix makes that explicit), R3, R4 (the result of the write inside unqueue is still ignored, so a failed removal warns nobody; R7 is its consequence), R5, R6, and D3 to D7, D9 to D15 from the first review.
