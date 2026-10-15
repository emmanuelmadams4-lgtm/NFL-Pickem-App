# CODEX WORK ORDER 1 — step 18k web: the run-check notice in the Score simulator section

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message.

GOAL: show `PredictionOut.simulation_check` inside the existing Score simulator section. Spec C1-C5 is in
`docs/gauntlet/logs/step-18k-web.md` §2, and the tests are in `apps/web/e2e/check18k.spec.ts` (read both). The type
`SimulationCheckOut` already exists in `packages/shared/src/api-types.ts`.

ALLOWED FILE: `apps/web/components/game/simulation.tsx` only.

REQUIRED BEHAVIOUR:
- Read `const check = game.prediction?.simulation_check;`. When it is falsy (null or absent), render nothing new.
- When present, render a small notice as the first child inside `<Section id="simulator">`, before the
  "No simulation…" line or the numbers. Show it in both the simulation and the no-simulation branches.
  - A heading line (`text-sm font-medium text-text`): failed = "Run check failed", no_verdict = "Run check gave no
    verdict", not_checked = "Not checked".
  - The server's `note`, word for word (`text-sm text-text-2`).
  - When `cause` is set: "Cause: " plus the plain words. cap = "the daily check limit was reached", provider = "Claude
    could not be reached", unparsed = "the check's answer could not be read", error = "the check hit an error". For any
    other code, show the code itself.
  - Style: a bordered box in the app's warning tone, like other notices in `components/ui.tsx` or nearby sections; pick
    the existing tokens (`border border-warn/40 bg-warn/10`, as `ui.tsx:324` and `pick-buttons.tsx:68` use), with `rounded-card p-3`. Add
    `mb-4` when numbers follow.
- Everything else in the section stays as it is.

PROOF: `npm run typecheck`. The coordinator reruns `e2e/check18k.spec.ts` and `e2e/sim18j.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail: two small lookup objects or a switch, no new component file, no dependency. No test edits.
typecheck only. Do not commit. Send the hive report as soon as the edit is done.
