# CODEX WORK ORDER 6 — step 8a2, lane web: polish (five class changes)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: the four polish findings (`reviews/polish-critic-1.md`) and the blind judge's remark 1 (`reviews/ab-judge-1.md`). No behaviour, text or test changes.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE: `apps/web/components/week/game-card.tsx` and `apps/web/components/game/star-players.tsx` only.

REQUIRED CHANGES
1. `game-card.tsx`, the stars line: the wrapper that holds the players goes from `gap-x-2` to `gap-x-3` (the inner `gap-x-1` stays). [J1]
2. `game-card.tsx`: a star's position and status sit together in one `<span className="inline-flex gap-x-1 whitespace-nowrap">`, so the status never wraps alone. [J4]
3. `game-card.tsx`: the note ("No star list yet for ..." / "Injury report not in yet") uses `text-text-2`, not `text-subtle`. [judge 1]
4. `star-players.tsx`: the plain-text status span ("Not on injury report", the en dash, other statuses) gets `leading-5`. [J2]
5. `star-players.tsx`: "No injury report yet this week" and "No star list yet" use `text-text-2`, not `text-subtle`. [J3]

PROOF (the coordinator reruns it): `npm run typecheck`; browser `e2e/stars.spec.ts` (ST7 checks contrast).

CONSTRAINTS: /ponytail: class names only. Existing tokens only. Do not build the web app, do not start a server or a browser. Do not commit; report the diff.
