# Dwight: design review, step 10 server (2026-10-13 17:25 UTC)

VERDICT: PASS to build. No CRITICAL, no HIGH, so nothing blocks. Five MEDIUM that must be folded into the design and get their own failing test before code (R1-R5). LOW is advice.

WHAT I CHECKED: docs/gauntlet/logs/step-10-server-evidence/design.md (uncommitted, 12 sections, read 2026-10-13) in lane-passkey at base b73038e; backend/nflpi/api/main.py require_token and the CORS setup; api/group.py _token; apps/web/lib/api.tsx (where the token is kept). Own read only: this is a design with no code, so ecc:security-reviewer and ecc:silent-failure-hunter were not run; they run on the code commit. Nothing executed. Not verified: the release dates and dependency versions you list for webauthn 3.0.1 (no network; the package is not in uv.lock yet). I will check the lock file at code review.

RULINGS ON YOUR 11 POINTS
(1) Library: agree. py_webauthn is the right choice and using only its generate and verify calls, with no crypto of our own, is correct. Lock it in uv.lock with hashes; say in the log what pyOpenSSL is pulled for.
(2) Ceremony and burn before verify: agree. One DELETE ... RETURNING, committed before verification, is atomic and single use. Taking the challenge from clientDataJSON is sound because the proof is that the row exists, is live and is the right kind; the signature then binds the same bytes. See R3 for the encoding.
(3) Challenge storage and 5 minutes: agree. Section 3 says 32 random bytes and section 4 says 64; fix the text (R3).
(4) Origin and relying party: agree. Config only, parsed host, exact or dot-boundary match, request headers never read. Keep http://localhost usable only when rp_id is localhost.
(5) Sign count: agree as written.
(6) Session: agree on format, sha256 at rest (256 random bits need no slow hash), fixed 30 days, Bearer header, revocation. See R1 and R2 on what a session may do.
(7) require_token: agree on the 4 lines and on compare first, then accepts. Change one thing: R4.
(8) Rate limit and bounds: agree on the global window, the 64 KB cap and no body model on public routes. See R5 on the challenge cap.
(9) Reach with no sign-in: agree. The timing note is right; an unknown credential id is not a usable oracle.
(10) Logging: agree.
(11) Missing clauses: R1-R5 below each need one, plus T1-T4 at the end.

REQUIRED (MEDIUM)
R1. A session must not be able to mint a permanent passkey. As designed, register begin and finish accept 'app token or a valid passkey session'. A stolen 30 day session (the value sits in localStorage, like the token) could then register the thief's own passkey and keep access for good, which defeats 'a stolen value dies on a known date'. Make both register routes accept the app token only. It costs the owner nothing: a new device has no passkey yet, so he is signed in there with the token anyway. New clause and test: register begin and finish with a valid session and no token answer 401 and create no challenge and no row. (If the owner wants register-from-session, it needs a fresh user-verified assertion first; not for this step.)
R2. A passkey outlives a change of the app token. Anyone who ever held the token could register a passkey; rotating APP_ACCESS_TOKEN after a leak leaves that passkey and its sessions working. Minimum: (a) every registration and every removal sends the owner a push alert through the existing sender and logs the row id, so a passkey he did not add is seen; (b) one line in the operator notes and in decision list 12: 'after changing the app token, open the passkey list and remove any you do not know', and the off switch (clear the two settings) ends all sessions at once. Clause and test for (a): a registration with a subscribed device records one notification; a failed push does not fail the registration.
R3. Pin the challenge hash to bytes. Hash the raw challenge bytes (base64url decoded from clientDataJSON, with or without padding), never the text as received, and store the same at begin. Otherwise a padding or alphabet variant misses the row (a failed sign-in) or, worse, two spellings map to different rows. Clause and test: a finish whose clientDataJSON carries the padded spelling of a live challenge finds and burns the same row; a second finish with the unpadded spelling fails.
R4. A database error in accepts() must not look like a wrong session. The web app drops the stored sign-in on any 401 (the QueryCache handler calls signOut). If accepts() answers False on a database error, one blip signs the owner out of every open screen and throws his session away. Still deny, but with 503 and a fixed text, so the client keeps the value and retries. Clause and test: accepts() with a failing database gives 503, not 401, and no value in the log.
R5. The challenge cap lets a stranger switch passkey sign-in off for as long as they like, not 'for a minute', and blocks registration too. 30 calls a minute for 5 minutes is 150 rows against a cap of 50, so 10 public begin calls a minute keep the table full for good; register begin shares the cap. Count the cap per kind, so a flood of public sign-in challenges cannot block a signed-in register begin, and correct decision 8 in section 12 to say the denial lasts as long as the flood. The token still works, so this stays accepted, but the owner should be told the true cost. Test: 50 live signin challenges do not stop a register begin.

LOW (advice)
L1. Backup and restore: the three new tables go into every backup. Session hashes are useless without the value (good), but restoring an old backup brings back passkeys the owner had removed. One line in the restore notes: after a restore, review the passkey list.
L2. Use one clock for expiry: the DELETE uses the database now(); make the session check and the expiry written at issue use the same source, or a skew between app and database moves the 5 minute and 30 day edges.
L3. accepts() adds one query to every request made with a session. Fine at this scale; no cache (a cache would delay revocation).
L4. Say the order on public routes: rate limit first, then the body read, then any database work.
L5. DELETE /api/passkey/{id} and the list accept a session. A stolen session can remove the owner's other passkeys (a nuisance, the token still works). Accepted; or make DELETE token-only as well for symmetry with R1.
L6. signout with the app token is a 204 no-op; with a session whose row is already gone, also 204. Say so, so it never leaks whether a session existed.
L7. The label is outside text shown later on a screen: control and format characters (Unicode category C) refused, as you say; the screen must render it as text (lane web).

TESTS TO ADD BEYOND P1-P20
T1. Session refused once its passkey row is removed AND once the settings are cleared, with no database call in the second case (P1 and P13 nearly cover it; make both explicit).
T2. sign-in finish reply carries Cache-Control: no-store and nothing but session and expires_at.
T3. A 429 from the window happens before any database row is written.
T4. gen:api shows the public routes; no drift.

Send the code commit on this thread when ready; I will run both ecc agents on it.
