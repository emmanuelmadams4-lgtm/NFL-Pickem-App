# Fresh critic 4 (Angela), HEAD cede804

Hive message `2026-10-13T00-02-54-011Z-3cf341`, 2026-10-13T00:02:54.012Z. Verbatim.

**Step 6 gate round 4: VERDICT PASS at cede804 (gate green three times in a row)**

VERDICT: PASS. New fresh critic, no history, HEAD cede804 (no extra commits, tree clean at start, 32 commits on 3d87fa0). Lane guard: OK. I asked for three runs instead of two because U3 had gone red once in two on two rounds.



GATE (sandbox off for the uv cache; logs critic4-angela-{a,b,c}-*.log, untracked in step-6-evidence, yours to keep or delete)

Run a (load 4.1): pytest 115 passed | ruff clean | gen:api no drift | typecheck 0 | e2e 89 passed, 0 failed, 2 skipped.

Run b (load 6.1): same, e2e 89 passed, 0 failed, 2 skipped.

Run c (load 7.1, 13.2 by the end): same, e2e 89 passed, 0 failed, 2 skipped.

Identical per-test results in all three. U3, U3b, U3c passed in all three. Skips are shots.spec.ts only. retries 0, workers 1, no .only/fixme/expect.soft/test.fail.



THE FIX (7a90207): closes the path. Checked against installed @tanstack/query-core 5.104.2: without it, a refetch on a query with no data returns the in-flight promise (query.ts:714); with it, cancelQueries reverts the query to idle and the cancelled fetch's late answer is dropped (retryer.ts:190), so invalidateQueries starts a new request. cancelQueries never rejects, so a successful save cannot show as failed. keys.scorecard has no other reader. Offline the PUT fails first, so nothing changes. red-critic3.log shows U3c failing on the old code at the intended assertion; 5ea3b2f is the parent of 7a90207; the fix commit touches only scorecard.tsx. Server logs for U3c show GET, PUT 204, GET in all three runs. U3 read line by line: no third cause found.

TESTS WEAKENED: no. 31 lines added (U3c), none removed; U3 and U3b unchanged.

CRITERIA: P1 to P22, L1 to L11, U3, U3b, U3c and G all PASS in all three runs.

STEP LOG: stages 1 to 5 match their evidence; wo9 and final4 logs show pytest 115 and e2e 89 passed, run after the fix commit. Earlier verdicts reported accurately; the A1 line is corrected; no PASS claimed for cede804; owner iPhone check PENDING. Dwight: PASS for landing at 9670cdf, nothing Critical or High open. His review predates the one-line scorecard change; the critic read it and it touches no auth, input, storage or secret, so I do not ask for another security pass.

DEFERRED: none must block.



FINDINGS (all advisory; id | severity | file:line | issue | fix)

C4-1 | Low | apps/web/e2e/sheet.spec.ts:194-199 + docs/gauntlet/logs/step-6.md:339 | U3c releases the held answer when the test sees the PUT response, not when the app has started its refetch. It could pass without exercising the fix; it cannot go falsely red. | Release after a second scorecard request is seen; soften 'does not depend on timing' in the log.

C4-2 | Low | apps/web/e2e/sheet.spec.ts:171 | U3's last assertion is empty for the seed: the row is filtered on 'Week 4' then checked for '4'. Older than this step. | Assert 'Leader 61 points' or use a rank that is not the week number.

C4-3 | Low | apps/web/components/performance/scorecard.tsx:45-47 | If the refetch after a save fails, 'Rank saved' shows beside 'Could not load scorecard'. Honest, rank is saved. | None needed.

C4-4 | Low | docs/gauntlet/logs/step-6.md:4 | Header still names base main@9d41cb0; the lane sits on 3d87fa0. | Update the line.

Still open from earlier rounds, in this order: F6 (banner 'showing data from' time is the last server reply of any kind; schedule first), F-2 (two open copies, one with a refused write, can drop the other's queued pick), F-3 / Dwight R7 (older stored pick sent on next open after refused writes).



What this PASS covers: cede804 on base 3d87fa0, docs-only commits after it (section 6 LANDING) included. Any code change after cede804, or a move onto a newer main that touches lane files, needs a new critic. Lock res:e2e released; nothing on 8123; live app not touched. The worktree is yours.
