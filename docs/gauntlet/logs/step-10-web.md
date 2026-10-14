# Step 10 web half: passkey screens — step log (lane web, card HAG-64)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web`, base main `b5ee53f` (2026-10-14). Coord task #33.

## 1. PLANNING

**Goal.** On the passkey API already on main (PR #25, `docs/gauntlet/logs/step-10-server.md`, design and the owner's 12
rules in `step-10-server-evidence/design.md`, decision D69): a "Sign in with a passkey" button on the sign-in screen,
shown only when the server says passkeys are on; a passkey list in Settings (add, optional name, last used, remove);
the session value kept and sent like the app token; sign-out calls `POST /api/passkey/signout`; browser tests with a
Chrome virtual authenticator. The app token stays the other way in.

**Done when.** The spec below holds in `apps/web/e2e/passkey.spec.ts`; full gate green (under ruling D71 the pull
request's CI is the full gate on the final head); Dwight no CRITICAL (front door: auth, user input); a fresh critic
PASS; lane-guard clean. The iPhone check and the two PC settings are the owner's and god's, after landing (PENDING).

**Tier T3** (security boundary, the front door). Owner decisions already made, not re-asked: D33, D69 and the 12
rules (session 30 days fixed; same header and same storage as the app token; up to 10 passkeys; removing a passkey
signs that device out; adding needs the app token; Face ID / Touch ID required).

**Pre-flight.** (1) Problem: the owner signs in on his iPhone by pasting a long token. (2) Why now: the server half
landed and runs switched off; without the screens it cannot be used. (3) Scope: one button on the sign-in card, one
Settings section, the sign-out call, the tests. Cut: passkey autofill (conditional mediation), renaming a passkey,
any server change except the seam below. (4) Success: the owner signs in with Face ID; the qualitative signal is the
iPhone check. (5) Reversibility: two-way (clearing the PC settings turns it off; the token still works).

**Assumptions.** validated: the four ceremony routes, statuses and texts (read in `api/passkey.py`); a 401 anywhere
drops the stored sign-in (`providers.tsx`); the session value starts `pks_`. assumed: the browser's own JSON helpers
(`PublicKeyCredential.parseCreationOptionsFromJSON`, `parseRequestOptionsFromJSON`, `credential.toJSON()`) exist on
the owner's iPhone (Safari 18.4 and later) and in the test Chromium; no new dependency. If a browser lacks them the
button says so and the token form stays. Checked on the iPhone after landing. unknown, sent as SEAM: no public route
says whether passkeys are configured (below).

**SEAM sent to god (2026-10-14 15:05 UTC).** The sign-in card is shown before any sign-in, so it can only reach
`/api/health` and the two public ceremony routes. Probing `signin/begin` would write a challenge row and spend the
shared 30-per-minute window. Proposed: `passkeys: bool` on `HealthOut` from the existing configured-settings helper
(design section 8 already lets a stranger learn this from a 503). `api/schemas.py` is lane wire18h's now. Until it
lands the browser tests set the flag by rewriting `/api/health` (they do in every case anyway), so they do not
depend on it.

**Skills.** `/graft`, `/jevgrep`: N/A, the seams were pinned by direct reads of the named files (god's dispatch named
them). TDD: Playwright browser tests are the public seam (as in steps 6, 7, 15). `/ponytail` in every work order.
Design Gauntlet: applies (sign-in card, Settings section). `harness-engineering`: N/A (no runner or evaluator).

**Test server.** `scripts/e2e-server.sh` (lane web) gets `PASSKEY_RP_ID=localhost` and
`PASSKEY_ORIGINS=http://localhost:8123`; the passkey tests open `http://localhost:8123` (a relying-party id cannot be an
IP address). Never in a live `.env`.

## 2. SPECIFICATION (frozen before production code)

Sign-in card (`components/sign-in.tsx`, new `components/passkey/**`):
- K1 Passkeys off (health says false or has no flag): the card is as today, no passkey button.
- K2 Passkeys on: a "Sign in with a passkey" button under the token form; the token form stays. Pressing it runs
  `signin/begin` → the browser prompt → `signin/finish`; on 200 the session value is stored with the existing
  `signIn()` (same key as the token) and the app opens.
- K3 Refusals are shown in words on the card, never a crash: the prompt cancelled or no passkey on this device:
  "No passkey was used." 401: "Passkey sign-in failed." 429 and 503: the server's text. A browser without the JSON
  helpers: "This browser cannot use a passkey here. Use your access token." The token form keeps working after any.

Settings (`components/settings/**` plus `components/passkey/**`), a "Passkeys" section:
- K4 List from `GET /api/passkey`: each row shows the name (or "Unnamed passkey"), when added, and "Last used …" or
  "Never used". No credential id or key is shown (none is sent).
- K5 Add (only when passkeys are on): an optional name field (at most 64 characters, the input stops at 64), then
  "Add a passkey" → `register/begin` → prompt → `register/finish` with the name; the list shows the new row.
  Refusals in words: 403 "Adding a passkey needs the access token. Sign in with the token, then add it here." (a
  passkey session can never add one); 409 and 422: the server's text; prompt cancelled: "No passkey was added."
- K6 Remove: a two-step button (no browser dialog): "Remove", then "Confirm remove"; `DELETE /api/passkey/{id}`; the
  row goes. Removing the passkey this device signed in with ends its session: the next request is a 401 and the app
  returns to the sign-in card.
- K7 Passkeys off: the list still shows (so a passkey can be removed while switched off, design section 14) and
  there is no add control.

Session:
- K8 Sign-out with a passkey session first calls `POST /api/passkey/signout` (a failure does not stop the sign-out),
  then clears the stored value as today. With the app token, sign-out is as today (no call).
- K9 A 401 on a passkey session returns to the sign-in card with "Your passkey sign-in has ended. Sign in again."
  (the token wording stays for the token).
- K10 The stored value is sent as `Authorization: Bearer pks_…` on every request, exactly as the token is.

Quality:
- K11 No serious or critical axe finding on the sign-in card and the Settings section; no sideways scroll at 393 px
  and 320 px; every control reachable by keyboard; errors in a `role="alert"` region.

Gate: `docs/gauntlet/logs/step-10-web-evidence/gate.sh` (as step 15: pytest, ruff, `gen:api` no drift, typecheck,
whole browser suite); under D71 run only `e2e/passkey.spec.ts` (and touched specs) locally with a 15-minute limit;
the pull request's CI is the full gate.
