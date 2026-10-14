# CODEX WORK ORDER 6 — step 10 web half: M1 + M2 from the security review (god decision 7b856b)

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message. Red tests: the three `M1`/`M2` tests at
the end of `apps/web/e2e/passkey.spec.ts` (run `s10-red-4`: all three fail for the intended reason). Read them first.

ALLOWED FILES (nothing else): `apps/web/lib/api.tsx`, `apps/web/components/settings/settings-view.tsx`,
`apps/web/components/sign-in.tsx`, `apps/web/components/passkey/passkeys-section.tsx`,
`apps/web/components/passkey/browser.ts`.

REQUIRED
1. M1a, `lib/api.tsx` `signOut`: when the stored value starts `pks_` and `POST /api/passkey/signout` fails, still clear
   the local session (as today) and, when the caller gave no message of its own, set the notice to exactly:
   "Signed out on this device, but the server could not end the passkey sign-in. Remove that passkey in Settings to
   end it now." A caller's own message (the 401 path in `providers.tsx`: "Your passkey sign-in has ended. Sign in
   again.") wins, since there the session is already over. Success and the app-token path are unchanged.
2. M1b, Settings `AccessSection.change`: after the new token is checked (`meta()` succeeds) and before `signIn(next)`,
   when the current stored value starts `pks_`, call `POST /api/passkey/signout` with that old value (await it; a
   failure does not stop the change, and then show the same words as item 1 as an error toast or line). Reuse one
   helper rather than a second copy of the sign-out call, e.g. export a small function from `lib/api.tsx`.
3. M2: a browser-side refusal gets its own words: "Your browser refused the passkey." — on the sign-in card and in the
   Settings add. Browser-side = an error thrown by the browser step (`parse…FromJSON`, `navigator.credentials.create/get`,
   `toJSON`) that is not a cancel (`NotAllowedError`/`AbortError` keep "No passkey was used." / "No passkey was
   added."), not "this browser cannot use a passkey here", and not `InvalidStateError` on add (keeps its words). A
   network failure of our own API calls (a `fetch` `TypeError`) must still say "Could not reach the API…". Simplest:
   in `browser.ts`, catch around the browser step only and re-throw non-cancel errors as one marked error the two
   screens can recognise.

PROOF: `npm run typecheck`; the coordinator reruns `e2e/passkey.spec.ts` (all 17) on a fresh build.
CONSTRAINTS: /ponytail, smallest diff. No test edits; if a test looks wrong, say which and why. typecheck only: no
build, no server, no browser, no pytest. Do not commit. Report per item.
