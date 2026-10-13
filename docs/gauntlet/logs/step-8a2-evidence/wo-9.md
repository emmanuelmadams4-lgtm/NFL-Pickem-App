# WORK ORDER 9 — step 8a2, lane web: two wording fixes on the card's stars line (design critic 2, findings 2 and 3)

Builder: a Claude Sonnet subagent (Codex is out of credits; god's rule of 2026-10-13). Try 1 of 2.

GOAL: make `apps/web/e2e/stars.spec.ts` ST2 green again (it now expects "MIA: no star list" and a middle dot before the age) without changing any test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the dispatch.

ALLOWED SCOPE: `apps/web/components/week/game-card.tsx`. Nothing else.

REQUIRED BEHAVIOUR (inside the `role="group"` named "Stars out"; everything else stays as it is)
1. The missing-list note reads `{club}: no star list` (was `{club}: no list`). Still its own element, exact text, never shrinks.
2. Directly before the age element, a separate element holding only a middle dot `·`, `aria-hidden="true"`, `shrink-0 text-subtle`; rendered only when the age is rendered. The age element's own text stays exactly `ago(observed_at)`.

PROOF (the coordinator reruns it): `npm run typecheck`; browser `e2e/stars.spec.ts` and `e2e/phone-layout.spec.ts` with a build; then the full gate.

CONSTRAINTS: /ponytail: the smallest diff. No test edits. Run only `npm run typecheck`. No build, server, browser, pytest or loops. Do not commit or touch git state; report the diff.
