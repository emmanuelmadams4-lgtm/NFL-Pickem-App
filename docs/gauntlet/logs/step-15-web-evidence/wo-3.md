# CODEX WORK ORDER 3 — step 15 web, lane web: the age of a live reply is measured on one clock

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

DEFECT (found by the coordinator in the browser run after work order 2). `useNow()` is server time (the device clock corrected by `/api/meta`), but `dataUpdatedAt` of the live query is device time. `cardLiveState` compares the two (`now - live.dataUpdatedAt > 120_000`) and the game screen prints "Checked …" from the same pair. A phone whose clock is two minutes or more behind the server shows "Not updating" for every live game, for ever; "Checked" shows the skew, not the age.

FAILING EVIDENCE: `apps/web/e2e/live.spec.ts`, "L4 a phone whose clock is five minutes behind the server still says Live" (both sizes). Red log: `step-15-web-evidence/red-3.txt`.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE: `apps/web/lib/queries.ts`, `apps/web/components/live/state.ts`, `apps/web/components/game/game-view.tsx`. Nothing else (`apps/web/lib/clock.ts` is not to be changed).

REQUIRED BEHAVIOUR
1. `useLive` returns `checkedAt`: the time of the last good live reply on the same clock as `useNow()` (the query's `dataUpdatedAt` plus the same correction `useNow()` applies: `Date.parse(meta.server_time) - meta.dataUpdatedAt` when `/api/meta` is in, else 0); 0 when there is no good reply yet.
2. `cardLiveState` and the "Checked" line use `checkedAt` and nothing else for the age of a reply. `LiveResult` carries `checkedAt` in place of `dataUpdatedAt`.
3. The screen-reader sentence for S4 says "1 minute ago", "1 hour ago" (singular) where the count is one; test "S4 one minute is singular".
4. No other behaviour changes: every other test in `live.spec.ts` stays green.

PROOF (the coordinator reruns it): `npm run typecheck`; browser `e2e/live.spec.ts`.

CONSTRAINTS: /ponytail, the smallest diff. No test edits. `npm run typecheck` only: no build, server, browser or pytest. Do not commit; report the diff and anything you had to decide.
