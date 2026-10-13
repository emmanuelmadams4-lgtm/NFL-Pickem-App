# Fresh critic 2 (Angela), HEAD f2c9af8

Hive message `2026-10-12T23-16-26-400Z-6dfc9f`, 2026-10-12T23:16:26.401Z. Verbatim.

**Step 6 gate round 2: VERDICT PASS at f2c9af8 (gate green twice; one follow-up to schedule first)**

VERDICT: PASS. New fresh critic, no history, on HEAD f2c9af8 (no extra commits, tree clean at start). Lane guard: OK.



GATE (sandbox off for the uv cache; logs critic2-angela-a-*.log and critic2-angela-b-*.log, untracked in step-6-evidence, yours to keep or delete)

Run a: pytest 115 passed | ruff clean | gen:api no drift | typecheck 0 | e2e 87 passed, 0 failed, 2 skipped.

Run b: pytest 115 passed | ruff clean | gen:api no drift | typecheck 0 | e2e 87 passed, 0 failed, 2 skipped.

Same 87 tests both times. The 2 skips are shots.spec.ts (screenshot only, no assertions). retries 0, workers 1, no .only/fixme/expect.soft.



CRITERIA: P1 to P21, L1 to L11, U3b and G all PASS, each test ran and passed in both runs and the production code was read against the criterion.

YOUR FIXES: A1 rank form fixed (U3b fails on revert). B1 fixed (P19 fails on revert). B2 fixed (P20 fails on revert). Damaged queue fixed (P18 fails on revert for null and 7; the other three values are guards). T1/P21: behaviour confirmed, but P21 is a guard, not red-first, as your log says. Red log matches: 5 failed, 30 passed; ccede75 precedes 3f5f6ff; the fix commit touches no test.

CHECKPOINTS: PLANNING, SPECIFICATION, IMPLEMENTATION, Design Gauntlet and review rounds, CLEANUP, VERIFICATION all PASS. Section 5 does not overstate. Dwight's review: PASS, no Critical or High open. Owner iPhone check correctly PENDING.

TESTS WEAKENED: no. 119 lines added to the specs, none removed; original U3 untouched.

DEFERRED (T2 to T6, C1 to C4, C6 to C8): none must block.



FINDINGS (all advisory; id | severity | file:line | issue | fix)

F1 | Medium (code reviewer) / Low (critic) | apps/web/lib/sync.ts:102-104,141-146 | New in 3f5f6ff. The in-memory fallback is laid over storage, so it cannot record a removal. If storage still holds an older pick for a game and a later write is refused, the older pick comes back as waiting after the newer one is sent, and the next flush sends it over the newer one: the server ends with the pick he changed away from, no message. I read the code and confirm the path. It needs a refused write while an older entry for the same game is still stored, which a real quota error rarely produces (the replacement is the same size), and blocked storage holds nothing. That is why it does not block. | While the in-memory queue exists, treat it as the whole queue and do not read storage under it. One failing test first: stored {g:A}, make setItem throw, pick B, let it send, assert no second PUT with A. Please make this the first follow-up; it is the same owner rule as B1.

F6 | Medium | apps/web/lib/sync.ts:62-67 + apps/web/components/pwa.tsx:92-97 | 'showing data from' is the time of the last good reply of any kind, health check included, not the age of what is on screen. A matchup saved Saturday and opened offline Sunday can read 'from 2 minutes ago'. Closest of the deferred items to the never-invent-data rule (same as C8, D12). | Use the shown query's dataUpdatedAt, or word it 'last reached the server'. Schedule early.

F4 | Low | apps/web/lib/queries.ts:109-114 + apps/web/components/pick-buttons.tsx:68 | The 'could not save on the phone' warning is a 5 s toast; afterwards the chip reads 'Waiting to sync' as if stored. | Chip says 'Not saved on phone' while the fallback holds that game.

F2 | Low | apps/web/lib/sync.ts:126 | After a refused write the in-memory copy holds the other open copy's picks and can re-send an old value. Two copies plus failing storage. | Keep only this page's own unsaved entries in memory (the F1 fix covers most of it).

F5 | Low | apps/web/lib/sync.ts:155-166,193-203 | Send ordering and the flushing flag are per page; a stale copy can send before its storage event arrives. Flush reads the cached snapshot, removal reads storage. | Use currentQueue() at the flush checks; navigator.locks around the flush if it ever matters.

F7 | Low | apps/web/lib/sync.ts:110 | storage event with key null (storage cleared) is ignored. | Treat a null key as a queue change.

F3 | Low | apps/web/components/performance/scorecard.tsx:29-36 | Typing before /api/meta arrives is replaced when the week jumps to the current one; the edited flags are never reset after a save, so the form does not refresh from the server afterwards. | Disable the fields until meta loads; reset the flags after a successful save.

F8 | Low | apps/web/e2e/pwa.spec.ts:374-395 | P19 leaves its pick in page memory and goes back online in finally; it could reach the server before the page closes. No failure seen. | Close the page before going online.

S4 | Low | apps/web/lib/sync.ts:92-99 | An empty-string team passes the stored-queue filter and is replayed as a clear. | Reject ''.

Note | step-6.md section 5 | The e2e counts leave out '2 skipped'; the wo7 logs are from the tree just before commit 3f5f6ff. Not a contradiction.



For the owner's iPhone check: watch app launch with Tailscale off (C1, no timeout on the worker's page fetch).

Lock res:e2e released; nothing listening on 8123; live app not touched. The worktree is yours again.
