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

K12 (added after the design critic, frozen before WO3; `reviews/design-1.md`): Remove arms one row with a Cancel
beside "Confirm remove"; passkey errors in their own alert under the passkey button, the token input marked invalid
only for token errors; empty list "No passkeys yet. Add one below and it will appear here." (on) or "Passkey sign-in
is switched off on the server." (off); dates as "Added Oct 14, 2026". K5 addition: a second passkey on the same
device is refused in plain words "This device already has a passkey for this app."

## 3. IMPLEMENTATION

Builder Ryan (Codex, default model), one work order at a time; the coordinator read every diff, kept it to the
allowed files, and reran the proof. Runs are under `~/.claude/plans/nfl-pickem-lanes/logs/step-15-web/` (`res:gate`
and `res:e2e` held for each browser run).

| Work order | Red evidence | Result | Commit |
|---|---|---|---|
| Red tests | `s10-red-1` (browser, all fail: no button, no section), `red-1-backend.txt` (health 7 fail) | spec + tests | `ad3dc37` |
| WO1 (`wo-1.md`) | as above | `s10-green-1`: 9 passed, 2 failed (K3 = coordinator's test defect, no passkey on the authenticator; K7 = real defect) | — |
| K3 test fix | — | test registers a passkey before the refusal cases | `6dc1051` |
| WO1b (`wo-1.md` §1b) | K7: health flag came from the saved offline cache | shared `usePasskeysEnabled` hook, fresh fetch on every open; `s10-green-2` 11/11; health 7/7 | `a67a065` |
| WO2 (`wo-2.md`) | `s10-red-2b`: raw browser text for a second passkey on one device; ruff E501 in `main.py` | plain words; line wrapped; ruff clean | `821db49` |
| WO3 (`wo-3.md`) | `s10-red-3`: both K12 tests fail for the intended reason | Cancel, split errors, texts, date; `s10-green-3` 13/14: its K12 test passed through Cancel and the date, then failed at line 266 on a real defect | `75c4060` |
| WO4 (`wo-4.md`) | `s10-green-3` line 266: a deleted passkey still listed after reopening Settings (saved cache + 60 s staleTime, no refetch; server log shows no `GET /api/passkey`) | list query refetches on every open; typecheck 0; browser proof in the run after WO5 | `158d7b1` |

Coordinator edits to production code: one `ruff check --fix` on `backend/nflpi/api/main.py` (import order only, after
WO1). `packages/shared/openapi.json` and `api-types.ts` regenerated with `npm run gen:api` (SEAM god 9f6599), never hand
edited. Design Gauntlet: before/after screenshots and the read-only design critic report `reviews/design-1.md`;
triage: accepted 1, 3, 6, 7 (WO3) and 2 (WO2, found by the screenshots); not taken 4 (optional intro line), 5 (the
40 px button gap is app wide, carried), 8 (name hint; the placeholder already says it).

After screenshots (`~/.claude/plans/nfl-pickem-lanes-logs/step-10-web/s10-after-*.png`, 393 and 1280, run
`s10-shots-after2`): card with the passkey button under the token form; Settings rows with "Added Oct 14, 2026 · Never
used", one armed row with "Confirm remove" + Cancel. The screenshot script now uses a second virtual authenticator for
the second passkey (one device holds one passkey for this app, which the app now refuses in plain words). Durable
`design.md` change: none (existing tokens and components only).

## 4. CLEANUP

Scope-locked `/refactor` pass on the touched code, done as work order 5 (`wo-5.md`, Ryan), commit `363bb7f`:
1. `browser.ts`: one exported `passkeyUnsupported` constant instead of a private constant plus an alias.
2. `browser.ts`: the repeated "no credential or no `toJSON` → refuse, else `toJSON()`" tail of `createPasskey` and
   `getPasskey` moved into one private `credentialJson`.
3. `sign-in.tsx`: the "Could not reach the API …" text built once (`unreachableApi`) for the token and passkey paths.
No change needed: `use-passkeys-enabled.ts` (15 lines, one job); `passkeys-section.tsx` (112 lines, one component;
the long `className` strings match the rest of Settings); `client.ts` (seven one-line calls in the file's own style);
`api.tsx` / `providers.tsx` (a few lines each). Texts and behaviour unchanged; typecheck 0.
Proof after cleanup: `s10-green-4` on `363bb7f`, fresh build: **14 passed, 0 failed** (`e2e/passkey.spec.ts`, which
also proves WO4: K12 line 266 now passes).

## 5. VERIFICATION

On HEAD (this commit, code as `363bb7f`):
- Browser: `s10-green-4` 14/14 (above). Backend: `tests/test_health_passkeys.py` 7/7 (on the test database, port
  15436); ruff clean (after WO2); typecheck 0. Under ruling D71 the full pytest and browser suite run in the pull
  request's CI on this head; not run locally.
- Security (Dwight, front door) on `363bb7f`: **PASS**, no CRITICAL, no HIGH; 2 MEDIUM (a failed server sign-out
  leaves the passkey session valid; browser errors shown as "Could not reach the API"), 5 LOW. Carried to god as
  follow-ups, not fixed here. `reviews/security-1.md`.
- Fresh critic (no transcript) on `9eae754`: **PASS**, no CRITICAL/HIGH. Its reruns: typecheck 0; health tests 7
  passed; ruff clean; `e2e/passkey.spec.ts` fresh build 14 passed, 0 failed (run `critic-1`). MEDIUM: the K8
  failed-sign-out path is untested; LOW: no timeout on the sign-out call during a 401, K4/K11/K5-422 not tested.
  `reviews/critic-1.md`.
- Jev Job 4 (review truly passed): Jev unavailable, route `advisor`; the call goes to god with the done message.
- lane-guard: below.
- lane-guard (`lane-guard.py check … web main`): 1 problem, `backend/nflpi/api/schemas.py: owned by lane wire18h`.
  This is the granted seam (god 9f6599, 2026-10-14): exactly one field `passkeys: bool` on `HealthOut`
  (`git diff b5ee53f -- backend/nflpi/api/schemas.py` is one line). Whoever lands second of web and wire18h reruns
  `npm run gen:api`. No other file outside the lane.

## 6. LANDING

God opens the pull request and lands it (D71: its CI is the full gate on this head). PENDING after landing: the
iPhone check and the two PC settings (`PASSKEY_RP_ID`, `PASSKEY_ORIGINS`), owner and god.

## Re-opened: M1 + M2 folded in (god 7b856b, 2026-10-14)

God's decision on Dwight's MEDIUM findings: fold in before landing, LOWs carried. Spec added (frozen before code):
- M1a A failed `POST /api/passkey/signout` still signs out on this device and says "Signed out on this device, but the
  server could not end the passkey sign-in. Remove that passkey in Settings to end it now." (the 401 path keeps its own
  words).
- M1b Changing from a passkey session to the token in Settings first ends the passkey session on the server.
- M2 Browser refusals (`SecurityError`, `NotSupportedError`, a `TypeError` from the options parser) say "Your browser
  refused the passkey." on the card and in Settings; a real network failure still says "Could not reach the API".
Red: `s10-red-4` (3 new tests, all fail for the intended reason). Work order 6: `wo-6.md`.
Carried LOWs (not fixed): Add shown to a passkey session (fails with the 403 words); add/remove 401 bypasses the
sign-out handler; no `pks_` check on the sign-in reply; a failed health check reads as "switched off"; two older 401
paths say "token rejected" for a passkey session; no timeout or guard on concurrent sign-out calls; K4 (no credential
id shown), K11 keyboard reach and the K5 422 words not tested.
WO6 (`wo-6.md`, Ryan, try 1): shared `endStoredPasskeySession` in `lib/api.tsx` (sign-out and the token change both use
it), the exact notice on failure unless the caller has its own words, a bad toast in Settings when the old session
could not be ended; `PasskeyBrowserError` marks non-cancel errors from the browser step only (fetch failures stay
outside it). Commit `5f82d94`. Proof: typecheck 0; `s10-green-5` fresh build **17 passed, 0 failed**.
Sync with main (god 7b856b): PR #38 (wire18h) merged as `400677b`; `origin/main` merged into `lane/web` as `73337a1`
(no conflicts, under `res:git-integrate`). `npm run gen:api` rerun: no change (the merged `openapi.json`/`api-types.ts`
already carry `HealthOut.passkeys`). On `73337a1`: typecheck 0; `test_health_passkeys.py` 7 passed (port 15436); ruff
clean; `s10-green-6` fresh build **17 passed, 0 failed**.
