# CODEX WORK ORDER 5 — step 15 web, lane web: CLEANUP (`/refactor`, scope-locked)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: simplify the code this step touched. No behaviour change, no visible change, no change to any text, class on a rendered element, or attribute that a test reads. Every test stays green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE: `apps/web/components/live/state.ts`, `apps/web/components/week/game-card.tsx`, `apps/web/components/game/game-header.tsx`, `apps/web/components/game/game-view.tsx`, `apps/web/lib/queries.ts`. One new file under `apps/web/components/live/` is allowed for item 1. Nothing else.

REQUIRED
1. The label is drawn by the same sliced-string JSX in two files (`game-card.tsx`, `game-header.tsx`: `label.slice("Not updating".length)`, `label.slice(4, 6)`). One small component `LiveLabel` (new file `apps/web/components/live/live-label.tsx`) renders the visible label and its `sr-only` sentence from the state; the pure function gives it the parts (`labelLead`: "Live" / "Not updating" / null, and the rest) so no string is sliced in JSX. The rendered DOM stays what it is now: one `aria-hidden` element with the visible words, the lead word in `text-text` (Live) or `text-warn` (Not updating), one `sr-only` sentence.
2. `kind === "S3" || kind === "S4"` is tested in four places for the secondary ink: one boolean on the state (`dim`).
3. `cardLiveState` is over 50 lines: move the building of the S5 chance lines into one helper in the same file. Keep the function pure and the file under 150 lines.
4. `CardLiveState` is also used by the game screen: no rename needed, but its doc comment says so.
5. `queries.ts`: one comment line on `refetchInterval` (it is rebuilt each tick; safe because the library compares the computed interval). Name the two intervals as constants (`LIVE_POLL_MS = 30_000`, `LIVE_ENDED_POLL_MS = 120_000`) and the 120 s age limit in `state.ts` (`NOT_UPDATING_AFTER_MS`).
6. Anything else you would simplify in these files: list it in your reply, do not do it.

PROOF (the coordinator reruns it): `npm run typecheck`; browser `e2e/live.spec.ts`, then the whole gate.

CONSTRAINTS: /ponytail. No test edits. `npm run typecheck` only: no build, server, browser or pytest. Do not commit; report each item, or "no change needed" with the reason.
