# Critic 2 - step 10 web half (HEAD 97819a9)

VERDICT: PASS

Gate (run fresh):
- npm run typecheck: exit 0 (web + shared)
- test_health_passkeys.py (port 15436): 7 passed; ruff: All checks passed
- npm run gen:api: no change to tracked files (git status shows only the untracked reviews/security-2.md)
- Browser, build + e2e/passkey.spec.ts only: 17 passed, 0 failed

Checks:
- M1a test stubs POST /api/passkey/signout to 500, asserts card visible, exact notice, stored session null. Real behaviour, not tautological.
- M1b test waits for the real POST signout (204), asserts stored value becomes the token, then proves the old pks_ value now gets 401 from /api/meta. Strong.
- M2 test: SecurityError, NotSupportedError and parser TypeError all give "Your browser refused the passkey."; a route abort of signin/begin still gives "Could not reach the API" (proves the split); same words in Settings add. Covers the requested case.
- 401 path: providers.tsx:71 message is passed to signOut(message), which takes precedence over the new notice (api.tsx `message ?? ...`); e2e line 158 still asserts it.
- PasskeyBrowserError (browser.ts) is thrown only inside createPasskey/getPasskey try blocks; cancel and unsupported errors pass through; fetch calls stay outside. InvalidStateError is kept for add only.
- No token/session in URLs, logs or error texts; notice and error strings are fixed.
- Diff stays in the allowed files plus docs/evidence. Lane-guard seam documented in log section 5.
- Log has evidence for all six work orders (wo-1..wo-6) and the re-opened section with red (edef322) and green runs.

Findings:
- LOW apps/web/components/settings/settings-view.tsx:50: if the token is changed while the passkey session end fails, the toast is "bad" with the sign-out notice wording ("Signed out on this device...") though the user is now signed in with the new token. Slightly misleading wording only; the server session remains and the notice tells them how to end it.
- LOW apps/web/components/passkey/browser.ts:27: for sign-in, InvalidStateError is mapped to the "refused" message (intentional, preserveInvalidState=false); untested. Carried LOWs listed in the log are acceptable.

No CRITICAL, HIGH or MEDIUM.
