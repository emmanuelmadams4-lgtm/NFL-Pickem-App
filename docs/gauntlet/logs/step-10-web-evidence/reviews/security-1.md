# Security review 1 — Dwight (front door), step 10 web at 363bb7f

Received 2026-10-14T15:21:12.804Z (hive message 2026-10-14T15-21-12-804Z-55c739). Verbatim:

VERDICT: PASS on security at 363bb7f (diff b5ee53f..363bb7f). Nothing CRITICAL, nothing HIGH in my rating. Both ecc agents ran on the commit through git only, and I read the whole production diff myself. Nothing was executed: no browser suite, no pytest.

YOUR FOUR POINTS
- Session value: met. lib/api.tsx signIn stores a pks_ value under the same nflpi_token key and client.ts sends it as the same Bearer header. Not in a URL, query key, console line, toast or error text (providers.tsx only tests the pks_ prefix to pick its notice). signOut calls /api/passkey/signout first, then clears local state even if that call fails.
- Credential: met. browser.ts uses the browser's own parseCreationOptionsFromJSON / parseRequestOptionsFromJSON and credential.toJSON(); no hand-made base64url, no eval; the challenge comes only from the server's begin reply; the result is posted only to our /api/passkey routes. Old browsers fail closed to the token form.
- Health flag: met. HealthOut.passkeys = passkeys.config() is not None in both the normal and degraded branches; a boolean only, no rp_id, origin or count, no new database call. usePasskeysEnabled needs a fresh fetch after mount, so a saved cache cannot switch the controls on.
- A passkey session cannot add a passkey: met on the server (403). The web maps 403 to its own text and never treats it as sign-out; only 401 signs out. Sign-in refusals run on a separate client outside React Query, so a refused finish cannot trigger the sign-out handler or leave a half state.
- No new dependency; e2e placeholders only (e2e-token; PASSKEY_RP_ID=localhost lives only in scripts/e2e-server.sh).

FINDINGS
K1 MEDIUM. lib/api.tsx signOut swallows a failed /api/passkey/signout (offline, 5xx, 5 s timeout) and clears the value locally, so the server session stays valid up to 30 days while the owner sees a normal sign-out, and nothing is left on the device to retry with. The silent-failure reviewer rates this HIGH; I rate it MEDIUM because the value is gone from this device, so only someone who already copied it could use it. Fix: on failure, still clear locally but show 'Signed out here; the server could not end the session. Remove the passkey in Settings to end it now.' Same gap in Settings 'change token' (AccessSection): replacing a pks_ session with the app token never calls signout, so that session also lives on; call signout there too.
K2 MEDIUM (honest messages). sign-in.tsx: any browser error other than cancel (SecurityError from a wrong RP ID or origin, NotSupportedError, a TypeError from the options parser) is shown as 'Could not reach the API', which sends the owner to the wrong cause. Map DOMException and TypeError-from-parse to 'Your browser refused the passkey'.
K3 LOW. passkeys-section.tsx: 'Add a passkey' is shown to a pks_ session and only fails with the 403 text; hide or disable it for pks_ sessions.
K4 LOW. add() and remove() call the API directly, outside React Query, so a 401 there shows an error instead of signing out until the next query (the known pattern: anything outside React Query bypasses the 401 handler).
K5 LOW. signIn(session.session) does not check the reply is a non-empty pks_ string; a malformed 200 leaves the app on the loading screen. One check before signIn.
K6 LOW. A failed /api/health hides the passkey button with no word and shows 'switched off on the server' in Settings when the list is empty; say 'could not check' instead.
K7 LOW. Two other 401 paths (group/data.ts, upload-panel.tsx) still say 'Your token was rejected' for a passkey session; put the prefix check inside signOut. Several 401s at once start several signout calls; a guard would do.

NOT VERIFIED: the browser suite and its claims; the service worker's handling of /api responses; behaviour on real browsers; the server side beyond what I reviewed in PR #25 (unchanged here).

## Coordinator triage

No CRITICAL, no HIGH: meets the done bar. Not fixed in this step (Ponytail scope; god decides whether to fold in): K1 MEDIUM (sign-out when the server signout call fails; change-token path skips signout), K2 MEDIUM (browser errors shown as 'Could not reach the API'). K3-K7 LOW carried. Sent to god as follow-up items with the done message.
