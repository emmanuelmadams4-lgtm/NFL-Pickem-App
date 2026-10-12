# CODEX WORK ORDER 9 — step 6, lane pwa: a rank saved before the scorecard has loaded shows the answer from before the save

BUILD_RUNG: gpt-6-sol, effort medium (try 1 of 2). JEV model:pwa:wo-9 → sol (0.98), effort medium (0.92), route follow.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="medium"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the red test `apps/web/e2e/sheet.spec.ts` U3c pass without breaking any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, the commit that adds this file. Never work in any other checkout.

SOURCE: `docs/gauntlet/logs/step-6-evidence/reviews/critic-angela-3.md` (F-1, High, blocking: her second gate run failed on U3).

ALLOWED SCOPE (edit only this): `apps/web/components/performance/scorecard.tsx`, the `save` function only.

REQUIREMENT

`save` sends the rank, then calls `qc.invalidateQueries({ queryKey: keys.scorecard(season) })`. If the page's first scorecard request is still in flight (the query has no data yet), TanStack Query 5.104.2 reuses that in-flight request instead of starting a new one. Its answer was produced before the save, so the page shows "Rank saved" beside a scorecard without the new rank (or "No finished games on your sheet yet.").

After a successful save, the scorecard shown must come from a request made after the save. Cancel the in-flight scorecard query before invalidating (`await qc.cancelQueries({ queryKey: keys.scorecard(season) })`), or an equivalent that guarantees a new request. "Rank saved" still appears only after that request settles, as today. A failed save still shows the error and changes nothing else.

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-critic3.log` — U3c fails at "the scorecard shows what was just saved, not the answer from before the save": expected "Leader 55 points", the row shows "Leader 61 points". U3 and U3b pass in the same run.

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo9`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup. Do not touch the `edited` ref or the effect above `save`.
- Do not edit any file under `apps/web/e2e/`, any seam, or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- U3 and U3b must stay green.
- Match the surrounding style. No `console.log`.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
