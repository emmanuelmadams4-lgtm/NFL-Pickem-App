# CODEX WORK ORDER 1 — step 10 web half, lane web: passkey sign-in and the passkey list

Try 1 of 2. Baseline: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

GOAL: the browser tests in `apps/web/e2e/passkey.spec.ts` pass (K1-K11). The spec is section 2 of `docs/gauntlet/logs/step-10-web.md`; read it and the test file first. The server API is on main and must not change: `backend/nflpi/api/passkey.py`, design in `docs/gauntlet/logs/step-10-server-evidence/design.md` (sections 4, 5, 9: routes, bodies, statuses).

ALLOWED FILES (nothing else):
- new files under `apps/web/components/passkey/`
- `apps/web/components/sign-in.tsx` (the passkey button and its errors)
- `apps/web/components/settings/settings-view.tsx` (mount one `<PasskeysSection />` with `id="passkeys"`, near Access)
- `apps/web/lib/api.tsx` (sign-out calls `POST /api/passkey/signout` first when the stored value starts `pks_`)
- `apps/web/components/providers.tsx` (the 401 notice wording for a passkey session, K9)
- `packages/shared/src/client.ts` (typed calls for the seven passkey routes and `health`)
- `backend/nflpi/api/schemas.py`: ADD exactly one field `passkeys: bool` to `HealthOut`, nothing else in that file (granted seam, god 2026-10-14 14:47 UTC)
- `backend/nflpi/api/main.py`: the health route sets it from `nflpi.auth.passkeys.config() is not None` (read only, no edit to that module), on both the normal and the degraded reply

REQUIRED
1. Client (`client.ts`): `passkeyRegisterBegin()`, `passkeyRegisterFinish(credential, label)`, `passkeySigninBegin()`, `passkeySigninFinish(credential)` returning `{session, expires_at}`, `passkeys()`, `removePasskey(id)`, `passkeySignout()`. Use the generated types in `api-types.ts` where they exist (`PasskeyListOut`, `SessionOut`, `RegisteredOut`); do NOT edit `api-types.ts` or `openapi.json`. The begin replies are the library's options JSON. The sign-in calls run before any sign-in: they go through the same `call()` with an empty token (the route is public).
2. "Passkeys are on" = `GET /api/health` has `passkeys === true` (the new `HealthOut.passkeys`; the coordinator regenerates `api-types.ts` with `npm run gen:api` after your change, do not edit it). Backend proof: `backend/tests/test_health_passkeys.py` (7 tests, red now).
3. Browser side, no new dependency: `PublicKeyCredential.parseCreationOptionsFromJSON` / `parseRequestOptionsFromJSON`, `navigator.credentials.create/get`, then `credential.toJSON()` as the finish body. If a helper is missing, show "This browser cannot use a passkey here. Use your access token." (sign-in) and do not call the server.
4. Sign-in card: button "Sign in with a passkey" only when passkeys are on (K1, K2), under the token form, secondary style; while it runs, the button shows a busy state. On success call the existing `signIn(session)`. Messages in the card's existing `role="alert"` slot (K3): `NotAllowedError` / `AbortError` from the browser → "No passkey was used."; 401 → "Passkey sign-in failed."; any other API error → the server's `detail` text; a network failure → the card's existing "Could not reach the API" text. The token form keeps working after any of them.
5. Settings "Passkeys" section (K4-K7): a list (`<ul>`/`<li>`) from `GET /api/passkey`: name or "Unnamed passkey"; "Added <date>"; "Last used <ago>" or "Never used". An add form only when passkeys are on: input labelled "Passkey name (optional)", `maxLength={64}`, button "Add a passkey" → begin → create → finish with the trimmed name (or none) → refresh the list. Remove: per row a "Remove" button that turns into "Confirm remove" (no `window.confirm`); then `DELETE`, refresh the list. Errors in a `role="alert"` in the section: 403 → "Adding a passkey needs the access token. Sign in with the token, then add it here."; `NotAllowedError` / `AbortError` → "No passkey was added."; other API errors → `detail`. Use React Query for the list (a key in `keys`), and the existing `Section`, `Button`, `Notice` components and tokens; no new colour.
6. Sign-out (K8): in `signOut`, when the stored value starts `pks_`, first `POST /api/passkey/signout` with it (await it, ignore any failure), then clear as today. With the app token nothing new happens.
7. 401 wording (K9): when the rejected value starts `pks_`, the notice is "Your passkey sign-in has ended. Sign in again."; the token wording is unchanged.
8. Removing the passkey this device signed in with needs no extra code: the next request is a 401 and item 7 applies. Do not add a "this device" guess.
9. Never log, show or store anything from a credential except sending it to the server; never put the session value in a URL or an error text.

PROOF (the coordinator reruns it): `npm run typecheck`; then the browser file `e2e/passkey.spec.ts` against a fresh build.

CONSTRAINTS: /ponytail (smallest working diff, no speculative abstraction). No test edits; if a test looks wrong, say which and why in your reply. Run `npm run typecheck` only: no build, no server, no browser, no pytest (the machine is short of memory; the coordinator runs those). Do not commit. Report per item: done, or "no change needed" with the reason, and anything you would simplify but did not.

## Work order 1b (try 2 of 2) — after the coordinator's run `s10-green-1` (9 passed, 2 failed)

Same allowed files. Two items, nothing else:
1. Lint: `uvx ruff check nflpi tests` → `nflpi/api/main.py:60:121 E501 Line too long (140 > 120)` (the degraded `HealthOut(...)` line). Wrap it. (The coordinator already let ruff sort the new import line: `ruff check --fix`, import order only.)
2. K7 fails: with passkeys switched off, Settings still shows "Add a passkey". Cause: the `["health"]` query is restored from the saved offline cache (`lib/persist.ts` saves every successful query except `live`), so the last "on" answer is used without asking the server. Required: whether passkeys are on always comes from a fresh `GET /api/health` each time the sign-in card or the Passkeys section opens, never from the saved cache; while it is unknown the passkey controls are hidden. Use one small shared hook (for example in `components/passkey/`) for the card and the section, its key in `keys`. Do not change `persist.ts` beyond what this needs.
Failing evidence: `e2e/passkey.spec.ts:231` "K7 … offers no add": expected 0 "Add a passkey" buttons, received 1. (K3 at line 176 was the coordinator's test defect, fixed in the test.)
Proof: `npm run typecheck`; the coordinator reruns ruff and `e2e/passkey.spec.ts`.
