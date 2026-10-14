# Critic 1 - step 10 web half: passkey screens

HEAD 9eae754, base b5ee53f. Independent critic.

## VERDICT: PASS

## Gate (rerun by me)

- typecheck (`npm run typecheck`, web and shared): exit 0.
- pytest `tests/test_health_passkeys.py` on the test DB (port 15436): 7 passed.
- `uvx ruff check nflpi tests`: All checks passed.
- Browser `e2e/passkey.spec.ts`, fresh build: 14 passed, 0 failed (build exit 0, run exit 0, 16.7 s).
- Note: my first attempts inside the sandbox failed on sandbox denials (uv cache, log path, localhost DB port), with no tests executed. The numbers above are from runs outside the sandbox; the browser spec completed once.

## Findings

No CRITICAL, no HIGH.

MEDIUM
- apps/web/lib/api.tsx (signOut): K8 clause "a failed signout call does not stop the sign-out" is implemented (try/catch) but untested. e2e/passkey.spec.ts K2 only covers the 204 path, so a regression that let a failed call block sign-out would pass.

LOW
- apps/web/lib/api.tsx (signOut) and apps/web/components/providers.tsx:67-75: `await passkeySignout()` has no timeout, and every 401 on a passkey session now goes through it. On a hung connection the local session is cleared late, and concurrent 401s can fire several signout calls. Offline fetches fail fast, so edge case only.
- Spec gaps, not tested: K4 "no credential id shown", K11 keyboard reachability, K5 422 text (shares the 409 path).
- K1 passes in the red run (red-1-e2e.txt test 1) because no button existed; expected for an absence assertion and still meaningful in green.

## Checks asked for

- K1-K12 are each exercised by e2e/passkey.spec.ts with real ceremonies against the live test server and a Chrome virtual authenticator. Only the health flag and the 401/429/503/409 refusals are stubbed, which is the right layer. Own-session removal (K6/K9) and signout revocation (K8) assert the server state afterwards (401 on old value). Not tautological. Backend test checks the field and that nothing else leaks.
- Diff scope: only allowed files plus log/evidence. schemas.py is one line (`passkeys: bool`, the granted seam); main.py adds an import and the flag in both health returns. openapi.json / api-types.ts changes are small and match gen:api output.
- No token or session value in URLs, logs or error texts: the session goes only in the Authorization header and the existing storage key; error texts are fixed strings or server `detail`. No console logging added.
- Process evidence: PLANNING (section 1, SEAM), SPECIFICATION (K1-K12 frozen; red-1-e2e.txt 10 of 11 failing, red-1-backend.txt 7 of 7 failing, committed in ad3dc37 before the feature commit a67a065; K12 red `s10-red-3`), IMPLEMENTATION (WO1-WO4, real defects found: stale health cache, stale list), CLEANUP (WO5 explicit refactor pass with three listed changes and justified no-change items), VERIFICATION (green-4 14/14, matches my rerun). Security review pending, not blocking.
- Positive: usePasskeysEnabled waits for a post-mount fetch so a saved offline health answer cannot show add controls.
