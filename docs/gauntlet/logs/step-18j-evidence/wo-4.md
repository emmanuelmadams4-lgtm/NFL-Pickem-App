# CODEX WORK ORDER 4 — step 18j: the board survives a cached week reply without pick_mode

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message.

FAILING EVIDENCE (run `s18j-red-3`): `e2e/sim18j.spec.ts` "S5b a saved week reply from before pick_mode existed still
shows the board" fails: no `game-card` in 15 s. Cause: `week-board.tsx:201` reads `data.pick_mode.label`; a week reply
from the phone's offline cache saved before 18h has no `pick_mode`, so render throws.

ALLOWED FILE: `apps/web/components/week/week-board.tsx` only.
REQUIRED: render that paragraph only when `data.pick_mode` is present:
`{data.pick_mode && <p className="text-xs text-subtle">{data.pick_mode.label}</p>}`. Nothing else.
PROOF: `npm run typecheck`; the coordinator reruns `e2e/sim18j.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail. No test edits. typecheck only. Do not commit.
