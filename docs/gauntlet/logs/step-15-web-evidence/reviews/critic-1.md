# Critic 1, step 15 web

VERDICT: PASS (with LOW findings only)

HEAD checked: c121a03 (lane/web). Base: main.

## Browser run
`e2e15.sh critic1 --build e2e/live.spec.ts`: build exit 0; run exit 1 because Playwright reported "Timed out waiting 180000ms from config.webServer" (load 23 to 48). The test server never started, so no test ran: 0 passed, 0 failed. This is the machine, not the product or the test. Not rerun, per the coordinator. Judged from the diff and the earlier green runs g5/g6 (205 passed each on 1e2cbad; code unchanged since apart from a test-only fix and docs).

## Typecheck
`npm run typecheck` (tsc --noEmit): no errors printed. The exit code was not captured (shell quirk), clean output only.

## Findings
| Severity | Where | What | Smallest fix |
|---|---|---|---|
| LOW | apps/web/lib/queries.ts (heldPosts) | Module-level Map is not reactive and survives sign-out within a session. It is marked `ponytail:` and only holds ended rows. | None needed; clear it on sign-out if wanted. |
| LOW | components/live/state.ts:94-123 | Any row state other than post/lost falls into S4/S5. If the route can return a state such as "pre" for a started game, the card says "Live" with no score. I could not confirm the route's state list (schema grep returned nothing). | Confirm against `LiveGameOut`; map unknown states to S6 if any exist. |
| LOW | game-view.tsx | `Checked` uses `live.checkedAt`; if it is 0 (no good reply) S5 cannot occur, so safe. Noted only. | None. |

Checked and fine: the live query is `enabled` only when a started game is on screen (L1); 30 s poll, 120 s when all ended, no background polling (L2); `persist.ts` excludes the `live` key from the saved cache; no write to week/game data or picks (the diff touches no pick/prediction code; the pregame pick keeps its own words); 401 is left to the app-wide handler (`retry: false`, no local catch); the feed's `clock` is rendered as React text, no `dangerouslySetInnerHTML`, club codes come from the game; `api-types.ts` is not hand-edited (only `client.ts` aliases added); backend change is an import-style nit only. `/api/live` is unchanged.

## Checkpoints
- PLANNING: evidenced (section 1, pre-flight, assumptions, design brief). OK.
- SPECIFICATION: evidenced. Frozen spec with UX review (ux-spec-1.md); failing tests commit eeb77d4 and red-1.txt (46 failed, 0 passed) come before the first production commit eee2cac. Later red files (red-3, red-4) also precede their fixes. OK.
- IMPLEMENTATION: evidenced. Work orders wo-1..wo-4 with proofs, spec corrections recorded openly, critics' reviews. OK.
- CLEANUP: an explicit refactor pass exists as its own commit 68b22f1 and wo-5.md (LiveLabel, dim flag, helper, named constants), not only review fixes. OK.
- VERIFICATION: evidenced. Section 5 gate table, g5/g6 green, security review PASS, ruling D71 recorded, lane-guard OK. The full gate is deferred to the PR's CI by D71; my own run could not execute (see above). OK.
