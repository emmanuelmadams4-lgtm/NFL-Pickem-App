# CODEX WORK ORDER 3 — step 6, lane pwa: findings from review round 1

BUILD_RUNG: gpt-6-sol, effort high (try 1 of 2). JEV model:pwa:wo-3 → sol (0.98), effort high (0.89), route follow.
Launch (prompt on stdin, never as an argument): `codex exec -m gpt-6-sol -c 'model_reasoning_effort="high"' -s workspace-write -C <worktree> -o <last.md> - < <prompt.md> > <codex.log> 2>&1`

GOAL: make the eight red tests pass (`apps/web/e2e/pwa.spec.ts` P11, P12; `apps/web/e2e/phone-layout.spec.ts` L4, L8 at 393 and 320, L9 at 393 and 320, L10) without breaking the 17 that pass in those two files or any other browser test.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa`, branch `lane/pwa`, commit `__R1_SHA__`. Never work in any other checkout.

SOURCE: three fresh reviews of `7611d89`, in `docs/gauntlet/logs/step-6-evidence/reviews/r1-ux.md`, `r1-visual.md`, `r1-implementation.md`. Finding ids below refer to them.

ALLOWED SCOPE (edit only these; ask before touching anything else):
- `apps/web/lib/sync.ts`, `apps/web/lib/queries.ts` (`useSetPick` only), `apps/web/components/pwa.tsx`, `apps/web/components/toast.tsx`
- `apps/web/components/week/week-board.tsx`, `game-card.tsx`, `apps/web/components/pickers.tsx`, `apps/web/components/ui.tsx`
- `apps/web/components/game/game-view.tsx` (the section-tab row)
- `apps/web/app/globals.css`
- `packages/shared/src/client.ts`

REQUIREMENT

A. Pick queue (F1, F6, U4). Never lose or revert a pick.
1. P11: when a pick or a clear is sent directly and succeeds, remove that game from the queue (an older queued choice for the same game must not be sent later). Export what you need from `sync.ts`.
2. Flush whenever the queue is not empty and the phone is online: the 15 s timer runs the same check-then-flush while `pendingCount() > 0`, not only while the server is marked unreachable.
3. P12: when a flush stops on an error that is not a network error (500, 401, 403), keep the pick queued, show one toast "Pick not saved yet. Will retry." (tone warn), and let the timer in 2 retry. Do not show the toast again on every retry of the same failure. 404, 409 and 422 keep today's behaviour (dropped and reported).
4. Sync messages say "waiting", not "offline" (U9): "1 waiting pick saved." / "N waiting picks saved." and "1 waiting pick was not saved: locked at kickoff." (plural likewise). The phone may never have been offline.

B. "next kickoff" (F2, V1, U1), L4: the note sits on the dark card body beside the date. Give it no color of its own, so it inherits the date's ink (`text-text-2`).

C. Week arrows (F3, V2, U2), L8: below `lg` the Previous week and Next week buttons are real controls again: at least 44 by 44, with a visible border (`border-border`, `bg-elevated`), as before work order 2. They stay beside the week picker. `hidden` does not win over the Button's `inline-flex`; do not rely on it.

D. First screen (V3, U3), L9 and still L1: at 393 and at 320 wide, on load, with no scrolling in any direction, exactly one visible "Yahoo sheet" link and one visible "Updated …" text are inside the viewport and above the tab bar. Take both out of the sideways chip row. Suggested: "Updated …" on the subtitle line ("2023 season, 4 games · Updated just now"), the Yahoo sheet link on the picker row or the title row. Keep ", refreshing" on the phone copy too (F10). L1 must stay green: the first card's pick buttons end above the tab bar at 393x852 (today there is about 35px of slack) and no card is taller than 400px. Render each of the two once if you can, instead of one copy per breakpoint.
   Also give the chip row a right-edge fade below `lg`, the same mask as the section tabs, with end padding so the last chip is clear of the fade when scrolled to the end.

E. Section tabs (F4), L10: when the row is scrolled to its end, the last tab is at least 40px clear of the row's right edge (end padding on the list), so the fade never covers it.

F. Card footer (V4): on the phone the "Counts as X, the model's pick, unless you tap a team." line and the "Model picked X for you" chip sit on their own full-width line above the Points and pick-buttons row, at 320 and at 393 alike. No empty block beside them. Desktop unchanged.

G. Timeouts (F7): `importPicks` and `refresh` are slow by nature; exempt them from the 5 s timeout like `report` and `ask`. In `errorMessage` (`components/ui.tsx`) a `DOMException` named `TimeoutError` or `AbortError` reads as the existing "Could not reach the API…" text, never the raw "signal timed out".

H. Update prompt (F5, F8): after `navigator.serviceWorker.ready`, also watch a worker that is already in `reg.installing`. Never show a second "New version ready." toast while one is on screen. If Reload is tapped and there is no waiting worker any more, just reload the page.

DESIGN (source: `design.md` § 0 and § 15)
REGISTER: product.   PRIMARY ACTION: tap a pick.
REUSE: `components/ui.tsx` (Button, Chip, SelectField, PageHead), tokens from `apps/web/app/globals.css`; no new dependency.
A11Y: accessible names and `data-testid` values unchanged; targets at least 44px on the phone; visible focus.
DON'T: new pills or badges · nested cards · one-off hex or px values · lime on anything that is not mine, selected or interactive · a second copy of the same control per breakpoint when one can serve both.

FAILING EVIDENCE: `docs/gauntlet/logs/step-6-evidence/red-r1-findings.log` (8 failed, 17 passed).

PROOF (the coordinator reruns all of it): `npm run typecheck` from the worktree root. You cannot bind ports, so say so; the coordinator runs `gate.sh wo3`.

CONSTRAINTS:
- Smallest correct diff. No new dependency, no new file, no unrelated cleanup.
- Do not edit any file under `apps/web/e2e/`, any seam (root `package.json`, lockfiles, `api-types.ts`, `index.ts`, backend, migrations, Dockerfile) or anything outside ALLOWED SCOPE. If an existing test pins something that must change, stop and tell Jim which test.
- Match the surrounding style. No `console.log`. Immutable updates.
- Never touch the live app (ports 8000 and 5432, containers `nfl-pickem-app-*`). Do not commit, push or deploy.

RETURN (reply to Jim, `jim-mv5mje0k`): changed files, a five-line summary, each proof command with its exit code, and any blocker.
