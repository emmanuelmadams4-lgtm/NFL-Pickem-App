# CODEX WORK ORDER 2 — step 6, lane pwa: phone layout (L1 to L7)

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-2 → sol (0.97, follow), effort high (0.71, route advisor); ADVISOR sonnet → high.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the seven red tests in `apps/web/e2e/phone-layout.spec.ts` (L1 to L7) pass without breaking any other browser test (`pwa.spec.ts`, `restyle.spec.ts`, `sheet.spec.ts`, `step2.spec.ts`).

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, commit `__WO1_SHA__` (work order 1 landed). Never work in any other checkout.

ALLOWED SCOPE (edit only these; ask before touching anything else):
- `apps/web/components/week/week-board.tsx`, `game-card.tsx`, `kpi-strip.tsx`, `points-control.tsx`
- `apps/web/components/ui.tsx`, `apps/web/components/pickers.tsx`, `apps/web/components/pick-buttons.tsx`, `apps/web/components/team.tsx`
- `apps/web/components/game/game-view.tsx` (the section-tab row), `recommendation.tsx` (the "What changed" line), `ai-research.tsx`, `ask.tsx` (disabled buttons)
- `apps/web/app/globals.css`
- `packages/shared/src/format.ts` (one small formatter, if you want it shared by the card and the game page)

REQUIREMENT (phone only: below the `lg` breakpoint. Desktop at 1440 must look the same as today.)

L1 Density at 393x852. Today the first game card starts at y 534 and cards are 494 to 534px tall, so the first pick buttons end at y 1011, under the fold.
- On load, the first card's "Your pick" buttons end above the floating tab bar (top at y 778) with no scrolling.
- No game card is taller than 400px on the seeded week.
- Remove nothing the card says today (teams, records, kickoff, model pick and win chance with its bar, the label line, uncertainty, market, chips, QB alerts, "What changed", points, pick buttons, final marks). Compact, do not delete: for example one row for both teams (logo, abbreviation, record) instead of the stacked block; tighter padding and gaps; the label, uncertainty and market lines sharing rows.
- Above the cards, save height the same way: for example the season and week pickers on the title row, the "Yahoo sheet" link inside the scrolling chip row, a shorter summary strip. Order stays: page head, filter chips, then summary (design.md § 0).
- Touch targets stay at least 44px for pick buttons, chips, pickers and links.

L2 At 320x568 no caption in the week summary strip wraps past two lines (today "No graded picks yet" and "No live picks graded" take three), and nothing scrolls sideways.

L3 The game page's section-tab row fades out at its right edge while more tabs are off screen: a CSS `mask-image` linear gradient on the scrolling `<ul>` (the test reads its computed `mask-image`). No JavaScript, no extra element.

L4 The ", next kickoff" note on the highlighted card is not lime (`#c6f135`). Lime means mine. Use the text color that is readable on that card's header.

L5 No disabled button on the game page keeps the lime fill: a disabled primary button and a disabled selected segment use the neutral disabled look (`bg-elevated`, `text-text-2`, the existing reduced opacity). Enabled buttons do not change.

L6 A changed pick reads "What changed:" once. The engine's note already starts with "Changed: "; strip that leading prefix where the note is shown, on the card and on the game page. Do not change the API or the backend.

L7 With Shift+Tab at 393x852, a focused pick button is never hidden under the sticky top bar. Add top scroll padding for the phone. Warning from step 3: a plain `scroll-padding-top` stacked with the sections' `scroll-mt-32` and broke `restyle.spec.ts` F6 (section jumps landing below the sticky nav). Keep F6 green: for example drop `scroll-mt-32` in favor of one shared value, or scope the padding so it is not counted twice.

DESIGN (source: `design.md` § 0 and § 15; rules inlined because Codex cannot load design skills)
REGISTER: product (dense consumer product).   USER GOAL / PRIMARY ACTION: open the week, read each game's recommendation, tap a pick.
REUSE: `components/ui.tsx` (Chip, PageHead, SelectField, Button, Segmented), `components/team.tsx`, `components/pick-buttons.tsx`; tokens only from `apps/web/app/globals.css`; no new UI or animation dependency.
STATES: loading (skeletons keep their new heights so nothing jumps) · empty · error · locked · final · picked · differs from model · focus-visible · disabled.
A11Y: semantic HTML, accessible names unchanged (tests find `Open matchup: …`, `Your pick: …`, `Pick <team>`, `data-testid="game-card"`), visible focus, targets at least 44px on touch, reduced motion respected.
MOTION: none added.
DON'T: nested cards · gradients, glow or glass · side-stripe borders · new pills or badges · uppercase letter-spaced labels · one-off hex or px values where a token or Tailwind scale step exists · lime on anything that is not mine, selected or interactive · color as the only signal.
CHANGES, in order: hierarchy and layout of the page head and card (L1), then captions (L2), then the tab fade (L3), then color (L4, L5), then copy (L6), then scroll padding (L7).

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-phone-layout.log` (7 failed); before screenshots `docs/gauntlet/logs/step-6-evidence/shots/before-*.png`; measurements in `docs/gauntlet/logs/step-6.md` section 2.

PROOF (the coordinator reruns all of it; your run is information, not proof):
- `npm run typecheck && npm run web:build` from the worktree root.
- If you can bind ports: `bash docs/gauntlet/logs/step-6-evidence/gate.sh wo2` (the lane's own database on 127.0.0.1:15436). If you cannot, say so; do not claim the browser tests passed.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no new abstraction with one user, no unrelated cleanup.
- Do not edit any file under `apps/web/e2e/`, any seam (root `package.json`, lockfiles, `packages/shared/src/api-types.ts`, `index.ts`, backend, migrations, Dockerfile) or anything outside ALLOWED SCOPE. If an existing test pins something L1 to L7 must change, stop and tell Jim which test and why; do not edit the test.
- Match the surrounding style (Tailwind classes, `cx`, lines under 160 characters). No `console.log`.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
