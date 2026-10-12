# Fresh critic 3 (Angela), HEAD 3de3036

Hive message `2026-10-12T23-40-34-609Z-174ac3`, 2026-10-12T23:40:34.610Z. Verbatim.

**Step 6 gate round 3: VERDICT FAIL at 3de3036 (run b red on U3; the queue fix itself is correct)**

VERDICT: FAIL. New fresh critic, no history, HEAD 3de3036 (no extra commits, tree clean at start). Lane guard: OK. The gate was not green twice in a row. Your two-line fix is correct and every step 6 test (P1 to P22, L1 to L11, U3b) passed in both runs.



GATE (sandbox off for the uv cache; logs critic3-angela-a-*.log and critic3-angela-b-*.log, untracked in step-6-evidence)

Run a: pytest 115 passed | ruff clean | gen:api no drift | typecheck 0 | e2e 88 passed, 0 failed, 2 skipped.

Run b: pytest 115 passed | ruff clean | gen:api no drift | typecheck 0 | e2e 87 passed, 1 FAILED, 2 skipped.

Failed: e2e/sheet.spec.ts:151 U3 (Yahoo rank), at line 170: Scorecard column header 'Week' not found. P22 passed in both. Skips are shots.spec.ts only. retries 0, workers 1, no .only/fixme/expect.soft/test.fail. Load average about 10 in run b.



FINDINGS (id | severity | file:line | issue | fix)

BLOCKING

F-1 | High | apps/web/components/performance/scorecard.tsx:45-47 (seen through apps/web/e2e/sheet.spec.ts:151-172) | Second cause of the U3 flake, not the wiped input that work order 7 fixed. If Save is clicked while the page's first scorecard request is still in flight, invalidateQueries reuses that in-flight fetch (TanStack Query 5.104.2 does this when the query has no data yet), so the pre-save answer (weeks: []) becomes the result: the page shows 'Rank saved' beside 'No finished games on your sheet yet.' Server log for run b has no GET /api/scorecard/2023 after the PUT /api/ranks/2023/4; run a has one. The owner can hit this too by saving fast on a slow link. | After the PUT, cancel the in-flight scorecard query and then refetch (await qc.cancelQueries(...) before invalidateQueries). Red test first: hold the first scorecard response, save, expect the row. Then two green gate runs. Maps to: criterion G, and a red gate is a FAIL by rule.

ADVISORY

F-2 | Low | apps/web/lib/sync.ts:102-104,122-129 | New with 9670cdf. Two copies sharing storage: copy 1 has a refused write and holds the queue in memory; copy 2 stores a pick for another game; copy 1's next successful write overwrites storage without copy 2's pick and neither sends it. The old code sent it from copy 1. Found by simulation, not in a browser. Needs two copies, a write refused in one and accepted in the other, unsent picks in both. | On the storage event while the in-memory queue exists, take in games the other copy added that this copy has not touched; or keep only this copy's own unsaved entries in memory.

F-3 | Low | apps/web/lib/sync.ts:122-129 | Not new. A stale stored entry outlives a refused removal, so if the app closes before the newer pick syncs, the older stored pick is sent on next open. Needs storage that refuses every write while still readable; the user did get the 'Keep the app open' toast. | On a refused write try removeItem for the queue key, or mark the stored copy stale.

F-4 | Low | docs/gauntlet/logs/step-6.md:283 | Says A1 (U3 fails now and then) was fixed in work order 7; it still occurs. | Correct it when F-1 is fixed.



THE FIX (9670cdf): closes the path (old code sent g:B, g:A, h:X, g:A in a scratch harness; fixed code sent g:B, h:X). P22 exercises it and red-r1-dwight.log shows it failing on the old code at the right assertion (expected LV, received MIA). f5862f1 is the parent of 9670cdf; the fix commit touches only sync.ts. The { ...currentQueue() } copy is needed (otherwise unqueue mutates the React snapshot). P18 to P21 still mean what they say.

TESTS WEAKENED: no. 32 lines added (P22), nothing removed or changed.

STEP LOG: stages 1 to 5 match their evidence (wo8b and final3 logs show pytest 115, e2e 88 passed, 2 skipped, run after the fix commit). Dwight: PASS at efd3625 and f2c9af8, nothing Critical or High open; his confirmation of R1 is correctly pending. No PASS is claimed for 3de3036. Owner iPhone check PENDING. Section 6 LANDING not present: do not write it as a PASS on this commit.

DEFERRED: none must block. F6 from round 2 (banner 'showing data from' time) is still the one to schedule first.



Note on my round 2 PASS: U3 passed twice then by luck of timing; this is the same test my first critic saw red, with a second cause. Lock res:e2e released; nothing on 8123; live app not touched. Name the fix commit and I run another new critic.
