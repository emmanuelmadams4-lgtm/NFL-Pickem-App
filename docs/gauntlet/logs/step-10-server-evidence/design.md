# Step 10 server half: passkey sign-in — DESIGN (reviewed by Dwight 2026-10-13: PASS to build; R1-R5 folded in, see section 13)

Lane `passkey`, worktree `.claude/worktrees/lane-passkey`, branch `lane/passkey`, base main `b73038e`. Tier T3.
Owner decision D33: Face ID / Touch ID passkey; the app token stays as the backup way in; no email, no password.
One user, his own devices, app served over HTTPS on his tailnet name. Server only: no screen in this lane.

## 1. Library (one new dependency)

`webauthn==3.0.1` (py_webauthn, github.com/duo-labs/py_webauthn). BSD-3-Clause. "Production/Stable". Releases:
2.7.1 (2026-02-11), 2.8.0 (2026-06-13), 3.0.0 (2026-06-29), 3.0.1 (2026-09-25). Needs Python >= 3.10.
Pulls: `cryptography>=49` (already in `uv.lock` through pywebpush), `pyOpenSSL>=26.3`, `cbor2>=6.1.2`, `pyasn1>=0.6.2`,
`pyasn1-modules>=0.4.2`. We call only: `generate_registration_options`, `verify_registration_response`,
`generate_authentication_options`, `verify_authentication_response`, `options_to_json_dict`, `parse_client_data_json`,
`base64url_to_bytes`. No WebAuthn verification and no cryptography of our own. Stdlib only for the session:
`secrets.token_urlsafe`, `hashlib.sha256`.

## 2. Settings (config only, never the request)

`PASSKEY_RP_ID` (for example `mac.tailnet-name.ts.net`) and `PASSKEY_ORIGINS` (comma list, for example
`https://mac.tailnet-name.ts.net`). Add-only in `config.py` and `.env.example`. One helper returns `(rp_id, origins)` or
`None`. It returns `None` ("not configured") when either is empty, or when any origin is not `https://host[:port]`
(or `http://localhost[:port]` for a dev machine), or its host is not `rp_id` or a subdomain of it (exact equality or
`endswith("." + rp_id)` on a host parsed by `urlsplit`; the value comes from the server's own `.env`, never from a
caller). `Host`, `Origin` and `X-Forwarded-*` request headers are never read by this code.

Not configured: every passkey route answers `503 {"detail": "Passkey sign-in is not configured"}`, a session value is
refused by `require_token` with no database call, and nothing else changes. So clearing the two settings is the off
switch, and it also ends existing sessions.

## 3. Tables (migration 0008 on 0007; models appended at the end of `models.py`)

* `passkey_credentials`: `id` int PK; `credential_id` String(1400) base64url, UNIQUE; `public_key` LargeBinary;
  `sign_count` BigInteger; `label` String(64) nullable; `created_at`, `last_used_at` timestamptz. Cap: 10 rows.
* `passkey_challenges`: `id` int PK; `challenge_hash` String(64) UNIQUE (sha256 hex of the 64 random challenge bytes);
  `kind` String(8) (`register` | `signin`); `created_at`, `expires_at` timestamptz. Lifetime 5 minutes.
  The hash is of the RAW challenge bytes (64 random bytes from the library), never of the text as received (R3).
* `passkey_sessions`: `id` int PK; `token_hash` String(64) UNIQUE (sha256 hex); `credential_id` FK to
  `passkey_credentials.id` ON DELETE CASCADE; `created_at`, `expires_at` timestamptz.

## 4. Ceremonies

All four begin/finish handlers are sync `def` (FastAPI thread pool), except the capped body read (section 7).

**Register begin** `POST /api/passkey/register/begin` — needs the APP TOKEN (R1). A valid passkey session gets
`403 {"detail": "Adding a passkey needs the app token"}` (403, not 401, because the web app drops its stored sign-in on a 401);
no sign-in gets the usual 401. Library `generate_registration_options(rp_id, rp_name="NFL Pick'em", user_name="owner",
user_id=b"nflpi-owner", attestation=none, authenticator_selection(resident_key=REQUIRED,
user_verification=REQUIRED), exclude_credentials=<stored ids>)`. The library makes the challenge (64 random bytes from
`secrets`); we store its sha256 with kind `register` and reply the options JSON.

**Register finish** `POST /api/passkey/register/finish` — needs the APP TOKEN, as begin (R1). Body `{"credential": <PublicKeyCredential
JSON>, "label": "<=64 chars, optional"}`. Steps: read the challenge out of `clientDataJSON`
(`parse_client_data_json`), then ONE statement `DELETE FROM passkey_challenges WHERE challenge_hash = :h AND kind =
'register' AND expires_at > now() RETURNING id` (commit). No row: refuse. The challenge is burnt before verification,
so a failed finish cannot be retried on the same challenge. Then `verify_registration_response(credential,
expected_challenge, expected_rp_id, expected_origin=<list>, require_user_verification=True)`. Store the credential.
Refuse the 11th passkey (409). Reply 201 `{id, label, created_at}`.

**Sign-in begin** `POST /api/passkey/signin/begin` — public. `generate_authentication_options(rp_id,
user_verification=REQUIRED)` with NO `allow_credentials` (discoverable passkeys), so the reply has the same shape
whether zero or five passkeys exist. Stores the challenge hash with kind `signin`.

**Sign-in finish** `POST /api/passkey/signin/finish` — public. Body is the PublicKeyCredential JSON. Steps: burn the
challenge exactly as above with kind `signin`; look the credential up by `id`; `verify_authentication_response(...,
credential_public_key, credential_current_sign_count, require_user_verification=True)`. EVERY failure (bad JSON, no
live challenge, unknown credential, wrong origin, wrong relying party, bad signature, no user verification, sign
count) gives the same `401 {"detail": "Passkey sign-in failed"}`.

**Sign count.** The library refuses when either count is above zero and the new one is not greater (a cloned
authenticator); we refuse the sign-in with the same 401, issue no session, leave the stored count alone, and log a
warning with our row id. Apple passkeys always send 0, which the library accepts. On success we store the new count.

**Kind binding.** A `register` challenge cannot finish a sign-in and the other way round (the `kind` in the DELETE).

## 5. Session

* Value: `"pks_" + secrets.token_urlsafe(32)` (256 random bits). Only `sha256(value)` hex is stored.
* Issued by sign-in finish: `200 {"session": "<value>", "expires_at": "<UTC>"}` with `Cache-Control: no-store`.
* Lifetime: FIXED 30 days from sign-in (no write on every request; a stolen value dies on a known date; signing in
  again is one Face ID). Expired rows are deleted at each sign-in finish.
* The client keeps it where it keeps the app token today and sends `Authorization: Bearer <value>`, the same header
  (`packages/shared/src/client.ts` already does this for the token). No cookie: a header is not sent by a
  cross-site form or link, so there is nothing to forge, and `require_token` keeps its one-argument shape, which
  `api/group.py` calls directly.
* Revoke: `POST /api/passkey/signout` deletes the row for the presented session (204; with the app token it is a
  204 no-op). Removing a passkey deletes its sessions (cascade).

## 6. The change to `require_token` (4 changed lines of the 10 allowed)

```python
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if secrets.compare_digest(supplied.encode(), expected.encode()):
        return
    if not passkey_api.sessions.accepts(supplied):
        raise HTTPException(401, "Missing or wrong access token")
```

`accepts(value)`: False at once unless the value starts with `pks_`, is at most 64 characters, and passkeys are
configured (so a wrong or missing app token costs no database call, as today); else one indexed lookup by
`token_hash` with `expires_at > now()` on its own short database session. A database error still refuses, but as
`503 {"detail": "Sign-in is temporarily unavailable"}` raised from `accepts` (R4), so the device keeps its session and
retries; a warning is logged without the value. The 503 for an unset `APP_ACCESS_TOKEN` and the 401 text are unchanged. Because the
check stays inside `require_token(authorization)`, all four mount styles get it with no edit: the `api` router,
`live`, `news` (include-time dependency) and `group` (its own `_token` that calls `require_token`). `main.py` gets one
import (`from nflpi.api import passkey as passkey_api`) and one `include_router(passkey_api.router)`.

SEAM noted, no edit: `api/group.py` carries its own `_token` wrapper. It delegates to `require_token`, so it accepts a
passkey session without a change.

## 7. Bounds on the public routes

* One in-process sliding window (stdlib `deque` + lock) over both public routes together: 30 calls per 60 s, then
  `429 {"detail": "Too many attempts, try again in a minute"}`. It is global, not per address: behind Tailscale Serve
  every caller arrives from the proxy, and we do not trust forwarded headers. Known ceiling: per process, resets on
  restart (the app runs one uvicorn process).
* Outstanding challenges: expired rows are deleted at every begin; 50 live rows OF THAT KIND -> 429 (R5: a flood of
  public sign-in challenges cannot block the owner's register begin).
* Order on a public route: rate limit, then the body read, then any database work (a 429 writes no row).
* Request body on both finish routes: stream read with a 64 KB cap (413), the same pattern as `api/group.py`
  import. No FastAPI body model on the public route, so a 422 never echoes input.
* Passkeys capped at 10. Label trimmed, control characters refused, at most 64 characters.

A stranger on the tailnet can make passkey sign-in answer 429 for as long as they keep flooding it (about ten calls a
minute keep the challenge table full). Adding a passkey and the app token still work. Accepted.

## 8. What a caller WITHOUT the app token or a session can reach

`GET /api/health` (as today), `POST /api/passkey/signin/begin`, `POST /api/passkey/signin/finish`. Nothing else.
They can learn: whether passkey sign-in is configured (503 or not). They cannot learn whether any passkey exists,
cannot add one (register needs sign-in), and cannot get a session without a signature from a stored passkey over a
live server challenge with the configured origin and relying party and user verification.

Known and accepted: an unknown credential id is answered a little faster than a bad signature (no signature check
runs). Credential ids are 16+ random bytes chosen by the authenticator, so this is not a usable oracle.

## 9. Other routes (all need sign-in)

`GET /api/passkey` -> `{"passkeys": [{id, label, created_at, last_used_at}]}` (never the credential id or key).
`DELETE /api/passkey/{id}` -> 204, unknown id 404; its sessions die; removing the last one leaves the app token working.
`POST /api/passkey/signout` -> 204.

## 10. Logging

Events only: registered (row id), sign-in ok (row id), sign-in refused (our own reason word: `challenge`, `unknown`,
`verify`, `count`, plus the exception CLASS name), removed (row id), misconfigured settings. Never: the app token, a
session value or its hash, a challenge, a credential id, a public key, a request body, or a library exception message.

## 11. Frozen clauses (each gets a test that fails when the clause is broken)

P1 not configured -> 503 on every passkey route, session refused, token routes unchanged. P2 register begin/finish
refuse a caller with no sign-in and create no challenge. P3 register happy path; replies carry no key or credential
id. P4 sign-in happy path; the session opens a route on each of the four mount styles. P5 challenge single use
(replayed finish fails, register and sign-in). P6 challenge expires. P7 origin checked. P8 relying-party id checked.
P9 tampered finish fails (signature byte, authenticator data), and kind binding. P10 sign count backwards refused, no
session, count unchanged; forward count stored. P11 user verification required. P12 session: only the hash stored;
expired refused; signed-out refused. P13 remove: sessions die; last passkey removed, app token still works; unknown
404. P14 uniform errors (unknown credential and bad signature answer the same; begin reply same shape with zero and
one passkey). P15 nothing secret in logs or replies. P16 bounds: 429 window, challenge cap, 413 body, 409 at 10.
P17 existing suite green, no test edited (one granted migration-list line). P18 migration up, check, down, up.
P19 app token unchanged: 503 unset, same 401 text, a non-`pks_` bearer makes no database call. P20 settings never
from the request (a forged Host/Origin header changes nothing in the options).

## 12. Decisions for the owner (two-way unless marked)

1. Session lasts 30 days from sign-in, fixed, not extended by use.
2. The session is sent in the same header as the app token and kept in the same place on the device.
3. Up to 10 passkeys (one per device).
4. Removing a passkey signs that device out at once.
5. Clearing the passkey settings turns passkey sign-in off at once, sessions included; the app token is untouched.
6. Face ID / Touch ID (user verification) is required on every sign-in.
7. A passkey is tied to the host name in `PASSKEY_RP_ID`; a new host name means registering again (D33 note).
8. Someone on the tailnet can make passkey sign-in refuse for as long as they keep flooding it; the token still works.
9. Adding a passkey needs the app token, never a passkey session (a stolen session must not become permanent).
10. Adding or removing a passkey sends a push alert to the owner's devices.
11. After changing the app token, or restoring a backup, open the passkey list and remove any you do not know.
12. A passkey session may remove a passkey (that only takes access away).

## 13. Changes after Dwight's design review (docs/gauntlet/logs/step-10-server-evidence/dwight-design-review.md)

Verdict: PASS to build, no CRITICAL, no HIGH. Library agreed. Required (MEDIUM), each now a frozen clause with a test:

* **R1** register begin and finish take the app token only; a session gets 403 and creates nothing.
* **R2** every registration and every removal sends a push alert through the existing sender (`nflpi.notify.push`),
  titles `Passkey added` / `Passkey removed`, and one `notifications` row of kind `passkey` when it reached a device.
  A failed alert never undoes the change. Operator note: decision 11.
* **R3** the challenge is matched by the sha256 of its raw bytes; a padded spelling finds and burns the same row.
* **R4** a database error in the session check answers 503 with a fixed text, not 401.
* **R5** the challenge cap counts per kind; decision 8 says the true cost.

Advice taken: L2 every time comes from the database clock (`now()`), in the same statement that writes or checks it;
L4 order on public routes; L6 sign-out answers 204 for the app token; L7 a label with any Unicode control or format
character (category C) is refused. L5: DELETE keeps accepting a session (decision 12). L1: restore note (decision 11).
T1-T4 are covered by the P1, P13, P4, P16 tests and the gate's gen:api check.

SEAM for the integrator (no edit made): `nflpi/notify/push.py` has no public "send one alert" function; this lane
calls its `_send` and `_record`. A public wrapper there would be cleaner.
