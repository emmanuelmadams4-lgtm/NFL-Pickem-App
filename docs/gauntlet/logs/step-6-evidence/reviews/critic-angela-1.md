# Review and fresh-critic gate by Angela (`angela-mv5ml1a8`) on `893acb9` — VERDICT: FAIL

Hive message `2026-10-12T22-51-21-924Z-2c298b`, copied word for word.

VERDICT: FAIL (one blocker in the gate, two blockers from the review; all 31 step 6 tests P1-P17 and L1-L11 passed in both runs).



HEAD tested: 893acb9 (you named efd3625; two docs-only commits to design.md came after). Tree clean at start. Lane guard: OK. Sandbox was off for the gate (uv cache needs it).



GATE, fresh critic, logs in step-6-evidence/critic-angela-*.log and critic-angela-run2-*.log (untracked, yours to keep or delete):

Run 1: pytest 115 passed | ruff clean | gen:api no drift | typecheck 0 | e2e 77 passed, 1 FAILED, 2 skipped (shots.spec.ts, screenshot-only). Failed: e2e/sheet.spec.ts:134 (U3, Yahoo rank), 'Rank saved' never appeared.

Run 2: all five PASS; pytest 115; e2e 78 passed, 0 failed, 2 skipped. retries: 0, no .only/fixme. Machine load was 9 to 13.

A red run is a FAIL by rule, and your criterion G asks for e2e green twice in a row.



CHECKPOINTS: PLANNING, SPECIFICATION (red-first confirmed by commit times and red logs), IMPLEMENTATION (no new dependency; the package.json change is the build script calling stamp-sw.mjs), Design Gauntlet (brief, 12 before and 14 after shots, critics, blind A/B) and CLEANUP: PASS. VERIFICATION: FAIL, step-6.md has no VERIFICATION section and never mentions round 5 or the final gate. Owner iPhone check is correctly PENDING.

TESTS WEAKENED: no. P13 ruling: at least as strict on the outcome (newer pick must win), looser on ordering; the 'Expected LV, Received MIA' proof on old code is not saved in any log.

DEFERRED LIST: none must block.



FINDINGS (id | severity | file:line | issue | fix)

BLOCKING

A1 | High | apps/web/e2e/sheet.spec.ts:134-144 + apps/web/components/performance/scorecard.tsx:29-34 | Effect on [q.data, selectedWeek] resets the rank field when the scorecard arrives; the test (and a fast owner) types before that, the field is wiped, required blocks submit, no request is sent. Not touched by step 6, also failed in baseline-e2e.log, but it makes the gate red. scorecard.tsx is under apps/web, so the lane owns it. | Stop the effect overwriting a field already typed in (or make U3 wait for the scorecard), then two green gate runs in a row. Maps to: criterion G, gate rule.

B1 | Medium | apps/web/lib/fmt.ts:48-54 + apps/web/lib/sync.ts:100-104 | safeSet swallows a storage write failure (quota, blocked storage), so writeQueue keeps the pick only in memory while the UI says 'waiting'; a reload or iOS eviction drops it with no message. I read the code and confirm it. | Have the queue write report failure and show a toast ('could not save offline, keep the app open'). Failing test first (make localStorage.setItem throw for nflpi_pick_queue). Maps to: owner rule 3, never trim error handling that prevents data loss.

B2 | Medium | apps/web/lib/sync.ts:87-104 | Queue is a per-tab snapshot never re-read from storage, and writeQueue rewrites the whole object. Home Screen app plus a Safari tab: one overwrites the other's queued picks, lost silently; a stale tab can replay an old pick over a newer one. No 'storage' listener exists (confirmed by grep). | Re-read storage inside writeQueue before merging and reset the snapshot on the storage event for QUEUE_KEY. Failing test first with two pages in one context. Maps to: owner rule 3.



ADVISORY (tests)

T1 | High | apps/web/lib/sync.ts:188-189 | No test for a replay the server refuses (409/422/404, the locked-at-kickoff path); suite only uses 500. | Seed a queued pick, fulfil PUT /api/picks/* with 409, assert entry removed, toast shown, no retry. I would do this one now: it is the 'picks lock at kickoff' rule on the new replay path.

T2 | High | apps/web/lib/sync.ts:195 | No test that a 401 during replay keeps the pick and does not loop. | Fulfil with 401; assert queue intact, request count bounded.

T3 | Medium | apps/web/components/providers.tsx:51-54 | No test that sign-out clears nflpi_cache; the pick queue is not cleared on sign-out (fine for one user; decide and assert). | One sign-out test.

T4 | Medium | apps/web/public/sw.js:96-104 | Offline game page checked for one game only; ignoreSearch could serve the wrong game. | Cache two games, go offline, assert each shows its own matchup.

T5 | Medium | apps/web/e2e/pwa.spec.ts:249-250,294 | P13/P14 use fixed 3-4 s sleeps as the negative check; a slow replay passes vacuously. | Wait on request count or queue == {} plus a response.

T6 | Medium | apps/web/e2e/pwa.spec.ts:92-97,198-201 | 'Unreachable' mocks hold 30 s; timers outlive unrouteAll. | Abort at once.

ADVISORY (code)

C1 | Medium | apps/web/public/sw.js:97-116 | networkFirst has no timeout on page fetches; with Tailscale off the app can hang at launch before the cached shell shows. | AbortSignal.timeout(~4000) on navigations. Worth watching in the owner's real iPhone test.

C2 | Medium | apps/web/public/sw.js:143-146 | Any cross-origin image cached as opaque, cap 150; can exhaust quota and feed B1. | Limit to the logo hosts, cap ~40.

C3 | Medium | apps/web/lib/persist.ts:9,18 | Cache version is a hand-set constant; old-shape data can show as current after an API change. | Use the build id.

C4 | Low | apps/web/lib/sync.ts:188-189,207 | 404/422 reported as 'locked at kickoff'; 'N saved' toast skipped when any were locked. | Separate counts, show both.

C5 | Low | apps/web/lib/sync.ts:93 | Stored 'null' or a non-object makes readQueue()[id] throw. | Object check after parse.

C6 | Low | apps/web/public/sw.js:92,102,124 | cache.put/trim without catch. | .catch(() => {}).

C7 | Low | apps/web/components/toast.tsx:41-52 | aria-live container plus role=status children: double announcement. | Drop one.

C8 | Low | apps/web/lib/sync.ts:62-67 + pwa.tsx banner | 'showing data from' uses the last successful reply of any kind (incl. health check), not the age of the data shown. | Use the query's dataUpdatedAt.

A2 | Medium | docs/gauntlet/logs/step-6.md | No VERIFICATION section. | Write it.

A3 | Low | commit bf952aa | P13 rewrite bundled with its fix; red proof not saved. | Save the log next time.



Checked and fine: pick ordering during replay, /api never intercepted or cached by the worker, cache names versioned by build, listeners cleaned up, no reload loop, no secret or prediction logic in the client.

Not covered: L1-L11 ran and passed, but the test-quality reviewer judged them from titles only.

Note: reviews/security-dwight.md is untracked in your worktree (Dwight's, not mine).



After the fixes, name the new commit and I will run a new critic. If you think B1 or B2 should be deferred, that is an owner rule, so ask god.
