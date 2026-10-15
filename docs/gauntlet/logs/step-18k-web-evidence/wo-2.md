# CODEX WORK ORDER 2 — step 18k web: use the shared Notice, with space under it

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message.

FAILING EVIDENCE (`s18kw-red-2`): `e2e/check18k.spec.ts` C6 fails: the notice's class is
`min-w-0 break-words rounded-card border border-warn/40 bg-warn/10 p-3`, expected the shared `Notice` (`rounded-ctl`). C6
also requires at least 8 px between the notice and "No simulation for this game yet." (today 0: `mb-4` only when `sim`).
Design review: `reviews/design-1.md` items 1 and 2.

ALLOWED FILE: `apps/web/components/game/simulation.tsx` only.
REQUIRED: replace the hand-built notice `<div role="note" …>` with the shared `Notice` from `@/components/ui`:
`<Notice tone="warn" title={CHECK_HEADINGS[check.status]} className="mb-4 break-words">` whose children are the server
`note` (word for word) and, when `cause` is set, the "Cause: …" line (as now, on its own line with `mt-1`).
`mb-4` always, whether or not a simulation follows. Keep `CHECK_HEADINGS` and `CHECK_CAUSES` as they are. Nothing else.
PROOF: `npm run typecheck`; the coordinator reruns `e2e/check18k.spec.ts` and `e2e/sim18j.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail. No test edits. typecheck only. Do not commit. Send the hive report as soon as the edit is done.
