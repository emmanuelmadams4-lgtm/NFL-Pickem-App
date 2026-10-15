# CODEX WORK ORDER 2 — step 8g web: design fixes

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message.

FAILING EVIDENCE (`s8g-red-2`): `e2e/news8g.spec.ts` N1 fails: the link class is
`block break-words text-sm font-medium text-text underline underline-offset-2`; expected `text-accent-text`. The same test
now also requires the accessible name "Starting quarterback limited in practice (opens in new tab)" and a "·" between the
source and the age. Design review: `reviews/design-1.md` (items 1, 2 and 5).

ALLOWED FILE: `apps/web/components/game/news.tsx` only.
REQUIRED:
1. The link title uses `text-accent-text` instead of `text-text` (keep `block break-words text-sm font-medium underline underline-offset-2`).
2. Inside the link, after the title: `<span className="sr-only"> (opens in new tab)</span>`.
3. In the meta row, when the age is shown, an `<span aria-hidden>·</span>` between the source and the age.
Nothing else.
PROOF: `npm run typecheck`; the coordinator reruns `e2e/news8g.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail. No test edits. typecheck only. Do not commit. Send the hive report as soon as the edit is done.
