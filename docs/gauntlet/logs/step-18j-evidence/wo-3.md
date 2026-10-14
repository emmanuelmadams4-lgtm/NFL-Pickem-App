# CODEX WORK ORDER 3 — step 18j: pick-mode line to the foot of the week board

Try 1 of 2. Baseline: branch `lane/web`, `b4ba105` plus the spec amendment commit named in the hive message.

FAILING EVIDENCE (full run `s18j-full-1`): `e2e/phone-layout.spec.ts:44` L1 "first pick buttons end above the tab bar
without scrolling": Expected <= 778, Received 803. Cause: the `{data && <p className="text-xs text-subtle">{data.pick_mode.label}</p>}`
line after `PageHead` wraps to two lines at 393 px and pushes the first card down.

ALLOWED FILE: `apps/web/components/week/week-board.tsx` only.
REQUIRED: remove that line from under `PageHead`; render the same label, word for word, as
`<p className="text-xs text-subtle">{data.pick_mode.label}</p>` directly after the existing
"Select a game for the full matchup. Picks lock at kickoff." paragraph, inside the same `<section aria-label="Games">`.
Nothing else.
PROOF: `npm run typecheck`; the coordinator reruns `e2e/phone-layout.spec.ts` and `e2e/sim18j.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail. No test edits. typecheck only. Do not commit.
