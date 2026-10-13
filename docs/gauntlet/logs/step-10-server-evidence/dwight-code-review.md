# Dwight: code review at d4bf199, step 10 server (2026-10-13 17:45 UTC)

VERDICT: PASS on security at d4bf199 (base b73038e). Nothing CRITICAL, nothing HIGH in my rating. One fix I would make before landing (C1). Both ecc agents ran on the commit through git only, and I read every changed source file myself. Nothing was executed: no tests, no database, no network.

R1-R5, all met in code:
- R1 met. api/passkey.py:40-45 _owner, used at :127 and :183. A session passes require_token, then fails the constant-time compare with the app token: 403.
- R2 met, with gap C1. _alert at :179 (add) and :265 (remove), after the commit; a failed alert does not undo the change.
- R3 met. auth/passkeys.py:82-96: sha256 of the decoded bytes, one atomic delete...returning bound to kind and expiry. Two concurrent verifies cannot both win. Burned before verify, so a failed verify needs a fresh challenge.
- R4 met. auth/sessions.py:43-50: any error in the check is a 503, exception class name only in the log.
- R5 met. auth/passkeys.py:66-71 counts per kind.

WHERE THE REVIEWERS DIFFER: the security reviewer found no CRITICAL or HIGH. The silent-failure reviewer rates the sign-in flood (C2) HIGH. I rate it MEDIUM: it is the cost the design and owner decision 8 already accept, the app token still works, and the caller must be on the tailnet. God can overrule.

FINDINGS
C1 MEDIUM (maps to R2). api/passkey.py:114-117: `sent = push._send(...)`, `if sent:` record. push._send returns 0 with no log when VAPID is unset or there is no subscription. Registration needs no push setup, so with a stolen app token a passkey can be added with no alert, no stored notification and no warning. Fix: store the Notification row whatever `sent` is, and log a warning when sent == 0 ("passkey added, nobody was alerted, id=..."). Add one test for the zero-subscription case.
C2 MEDIUM (R5, owner decision 8). auth/throttle.py:7-24: one global bucket of 30 a minute shared by signin/begin and signin/finish, no caller key. About 30 public calls a minute keeps passkey sign-in at 429 for as long as it runs. Not a bypass. No change required if decision 8 says this in those words; a cheap improvement is a separate bucket for signin/finish so a begin flood cannot also block a finish.
C3 MEDIUM. auth/sessions.py:41: a valid session gets a plain 401 when passkeys.config() is None, with no log. One typo in PASSKEY_ORIGINS signs every device out (the web app drops sign-in on any 401). Fail-closed is right; add a warning log for a pks_ value refused because config is None, and say it in the operator note.
C4 LOW. api/passkey.py:220-223: sign_count update has no guard; two sign-ins at once can store the lower count. Fix: `where id = :i and sign_count <= :n`. Synced passkeys always report 0, so the library does no clone detection for them; say so in the docs.
C5 LOW. api/passkey.py:220-224: a passkey removed during sign-in makes sessions.issue hit the foreign key: a bare 500 instead of the uniform 401. Catch IntegrityError as a refusal.
C6 LOW. api/passkey.py:154: the 10-passkey count is not atomic with the insert (11 possible, app token needed). passkeys.py:65-79: same for the challenge cap (small overshoot).
C7 LOW. Database errors in burn_challenge, _store_challenge, revoke, list and remove are bare 500s, not 503. None becomes a 401, so no sign-out.
C8 LOW. DELETE accepts a session (owner decision 12) and can remove the last passkey; the alert fires, subject to C1.
C9 LOW. passkeys.py:42-51 _origin_ok: rp_id is not checked for '*' or for having a dot (operator-set only). Refuse an rp_id with '*' or without a dot unless it is localhost.
C10 LOW. sessions.accepts: any caller sending a pks_ value of the right length costs one indexed query, with no limit. Clearing and then restoring the passkey settings revives sessions under 30 days old.
TESTS: test_p19_r4 fails the session factory, not the query (same try block, fine). No test for the push-unconfigured alert (C1), none for the races (C4-C6).

CHECKED AND FINE: require_token order (503 with no app token, then token compare, then session; group routes go through it too); session value 256-bit random, stored and looked up as sha256, fixed 30 days, removed on sign-out and by cascade on passkey delete; user verification required in options and both verifies; 64 KB body cap by header and by stream; RecursionError and non-dict bodies refused; uniform 401 text, logs carry ids and class names only; all SQL static with bound values; migration 0008 unique constraints, cascade, clean downgrade; .env.example adds two empty keys; uv.lock adds webauthn 3.0.1, cbor2 6.1.5, pyasn1 0.6.4, pyasn1-modules 0.4.2, pyopenssl 26.4.0, all from pypi.org with hashes.

NOT VERIFIED: lock-file hashes against PyPI and the release facts (no network); the webauthn library's own internals; how the web client stores the session (not in this commit); proxy and TLS in the deploy; the fixture authenticator beyond a secret scan.

If CLEANUP or the mutation pass changes code, send the delta commit on this thread; a small agreed delta gets my own read.
