# Security review 2 — Dwight, delta 363bb7f..5f82d94 (M1 + M2)

Received 2026-10-14T15:31:34.208Z (hive message 2026-10-14T15-31-34-208Z-a23d17). Verbatim:

PASS on the delta 363bb7f..5f82d94 (apps/web). Nothing CRITICAL, HIGH or MEDIUM open from my side. Own read of the five changed files; the two ecc agents were not rerun for a delta this size, the new tests were not read, nothing was executed.

- K1 fixed. lib/api.tsx endStoredPasskeySession ends a pks_ session through /api/passkey/signout and reports whether it worked. signOut still clears locally either way and, when the call failed, shows 'Signed out on this device, but the server could not end the passkey sign-in. Remove that passkey in Settings to end it now.' Settings 'change token' now ends the old pks_ session before storing the token and shows the same text as a toast when it could not.
- K2 fixed. browser.ts wraps the browser step: cancel (NotAllowedError/AbortError) and 'unsupported' pass through, InvalidStateError passes through on create only, anything else becomes PasskeyBrowserError 'Your browser refused the passkey.'; sign-in.tsx and passkeys-section.tsx show that text before the API branches, so a browser refusal is no longer reported as 'could not reach the API'. Server errors still come from fetch and keep their own messages.
- Still true: the session value is only in the Authorization header and the nflpi_token store; the failure notice carries no value.

LOW, advice: when signOut is called with its own message (the 401 paths), the 'server could not end' notice is not shown. That is right for a 401 (the session is already dead on the server); if any other caller passes a message, the failure would be hidden. The carried LOWs (K3-K7) stand as logged.

## Coordinator triage

PASS, nothing CRITICAL/HIGH/MEDIUM open. The LOW note (a caller passing its own message hides the server-failure notice) is correct for today's only callers, the 401 paths; carried with the other LOWs.
