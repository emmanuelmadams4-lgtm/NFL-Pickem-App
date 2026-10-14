# CODEX WORK ORDER 3 — step 10 web half: design critic fixes

Try 1 of 2. Baseline: worktree lane-web, branch `lane/web`, the commit named in the hive message (after work order 2).
Source: `reviews/design-1.md` (PASS WITH FIXES); the coordinator accepted findings 1, 3, 6, 7 (2 is work order 2).

ALLOWED FILES: `apps/web/components/passkey/passkeys-section.tsx`, `apps/web/components/sign-in.tsx`.

REQUIRED (failing tests: `e2e/passkey.spec.ts` the two "K12" tests, red run `s10-red-3`)
1. Remove (finding 1, MAJOR): when a row is armed it shows "Confirm remove" and a "Cancel" button (ghost style); Cancel returns the row to "Remove" and removes nothing. Only one row can be armed at a time (arming another disarms the first). No timer.
2. Sign-in card (finding 3): a passkey error shows directly under the "Sign in with a passkey" button, in its own `role="alert"` element; the token field's `aria-invalid` and its error line are for token errors only. Keep one alert on the card at a time (clear the other kind when a new attempt starts).
3. Empty list (finding 6): with passkeys on and no rows: "No passkeys yet. Add one below and it will appear here."; with passkeys off and no rows: "Passkey sign-in is switched off on the server."
4. Date (finding 7): "Added" shows an unambiguous date, e.g. "Added Oct 14, 2026" (`toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })`).
Not taken (do nothing): the intro line, button heights (an app-wide 40 px gap, carried), a name hint.

PROOF (the coordinator reruns): `npm run typecheck`; `e2e/passkey.spec.ts`.
CONSTRAINTS: /ponytail; existing components and tokens only; no test edits; typecheck only; no commit. Report per item.
