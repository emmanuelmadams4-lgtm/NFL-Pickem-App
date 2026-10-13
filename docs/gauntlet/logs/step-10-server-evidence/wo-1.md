# WORK ORDER 1 — lane passkey, step 10 server half (builder: Sonnet, try 1 of 2)

GOAL: make `backend/tests/test_passkey.py` pass (42 tests, 60 cases) with the smallest correct code, breaking nothing.

WORKTREE (work ONLY here): `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-passkey`, branch
`lane/passkey`, baseline commit `d8937c8`. Do not commit, push, stash, rebase or switch branch.

READ FIRST (in this order): `docs/gauntlet/logs/step-10-server-evidence/design.md` (the design, section 13 wins where it
differs), `backend/tests/test_passkey.py` (the contract: exact paths, status codes and texts), 
`backend/tests/fixtures/passkey/authenticator.py`, `backend/nflpi/api/main.py` lines 1-50 and 375-388,
`backend/nflpi/api/group.py` (the pattern for a router with its own token dependency, lazy import of `require_token`,
capped streamed body read, `run_in_threadpool`), `backend/nflpi/notify/push.py` lines 46-105,
`backend/migrations/versions/0007_qb_observations.py`, the last 40 lines of `backend/nflpi/models.py`.

## ALLOWED SCOPE (anything else is out of lane: do not touch it)

Create:
* `backend/nflpi/auth/__init__.py` (one-line docstring), `throttle.py`, `sessions.py`, `passkeys.py`
* `backend/nflpi/api/passkey.py`
* `backend/migrations/versions/0008_passkeys.py` (revision `0008`, down_revision `0007`, with a working downgrade)

Edit, bounded:
* `backend/nflpi/models.py`: APPEND three classes at the very end (`PasskeyCredential`, `PasskeyChallenge`,
  `PasskeySession`). Change no existing line except adding names to the sqlalchemy import if needed.
* `backend/nflpi/config.py`: ADD `passkey_rp_id: str = ""` and `passkey_origins: str = ""` with a short comment. Nothing else.
* `.env.example` (repo root): ADD `PASSKEY_RP_ID=` and `PASSKEY_ORIGINS=` with a two-line comment. Nothing else.
* `backend/nflpi/api/main.py`: exactly ONE new import line (`from nflpi.api import passkey as passkey_api`), exactly ONE
  new line `app.include_router(passkey_api.router)` next to the other include_router lines, and `require_token`
  changed to exactly this body (keep the signature):
  ```python
      expected = get_settings().app_access_token
      if not expected:
          raise HTTPException(503, "Server has no APP_ACCESS_TOKEN set")
      supplied = (authorization or "").removeprefix("Bearer ").strip()
      if secrets.compare_digest(supplied.encode(), expected.encode()):
          return
      if not passkey_api.sessions.accepts(supplied):
          raise HTTPException(401, "Missing or wrong access token")
  ```
  So `api/passkey.py` must have `from nflpi.auth import passkeys, sessions, throttle` at module level and must NOT
  import `nflpi.api.main` at module level (lazy import inside the dependency, as `group.py` does).
* `backend/tests/test_hardening.py`: ONLY the migration-list line (about line 494): add `"0008"` at the end of the list.

NEVER touch: `backend/tests/test_passkey.py`, `backend/tests/fixtures/**`, any other test, `api/schemas.py`,
`api/views.py`, `api/group.py`, `api/live.py`, `api/news.py`, `jobs.py`, `notify/push.py`, `pyproject.toml`, `uv.lock`,
anything under `apps/` or `packages/`. Do not run `npm run gen:api` (the coordinator does). If a test looks wrong, STOP
and report it; do not change it and do not weaken the code to fit a guess.

## REQUIREMENT (details the tests and the security review fix; the design file has the reasons)

Library: `webauthn` 3.0.1 is installed. Use only `generate_registration_options`, `verify_registration_response`,
`generate_authentication_options`, `verify_authentication_response`, and from `webauthn.helpers`:
`options_to_json_dict`, `parse_client_data_json`, `base64url_to_bytes`, `bytes_to_base64url`; structs from
`webauthn.helpers.structs`. No cryptography or WebAuthn checks of your own. Do not parse authenticator data yourself.

`auth/throttle.py`: `LIMIT = 30`, `WINDOW_S = 60.0`, `allow() -> bool` (sliding window over `time.monotonic()`, a
`collections.deque` and a `threading.Lock`), `reset() -> None`. A `# ponytail:` comment naming the ceiling (per
process, resets on restart; move to the database if the app ever runs more than one process).

`auth/passkeys.py`:
* `MAX_PASSKEYS = 10`, `MAX_LIVE_CHALLENGES = 50`, `CHALLENGE_TTL = timedelta(minutes=5)`.
* `config()` returns a small frozen dataclass `(rp_id, origins)` or `None`. `None` when either setting is empty, or
  any origin is not exactly `https://host[:port]` with no path, query or fragment (`http://localhost[:port]` allowed
  ONLY when `rp_id == "localhost"`), or its `urlsplit().hostname` is neither `rp_id` nor ends with `"." + rp_id`.
  Read settings through `get_settings()`. Never read a request header.
* Challenges: at every begin, first delete expired rows; then if live rows OF THAT KIND >= 50 raise "too many";
  insert `challenge_hash = sha256(raw challenge bytes).hexdigest()`, `kind`, `created_at = now()`,
  `expires_at = now() + 5 minutes` with BOTH times from the database `now()` in the one INSERT.
* Burn: `challenge = parse_client_data_json(base64url_to_bytes(response.clientDataJSON)).challenge` (bytes), then ONE
  statement `DELETE ... WHERE challenge_hash = :h AND kind = :k AND expires_at > now() RETURNING id`, COMMIT, and only
  then verify. No row: refuse. Every parse failure: refuse.
* Register begin: `rp_name="NFL Pick'em"`, `user_name="owner"`, `user_id=b"nflpi-owner"`, attestation none,
  `AuthenticatorSelectionCriteria(resident_key=REQUIRED, user_verification=REQUIRED)`, `exclude_credentials` = stored ids.
  Reply = `options_to_json_dict(options)`.
* Register finish order: label check (422) -> passkey count >= 10 (409) -> burn -> `verify_registration_response(...,
  expected_origin=list(origins), require_user_verification=True)` -> insert (a duplicate credential id is a refusal).
  Label: optional; if present must be a `str`; strip it; 1 to 64 characters; refuse any character whose
  `unicodedata.category` starts with `"C"`. Bad label: 422 `{"detail": "Label must be 1 to 64 printable characters"}`.
* Sign-in begin: `generate_authentication_options(rp_id=..., user_verification=REQUIRED)`, NO allow_credentials.
* Sign-in finish: burn (kind `signin`) -> look the credential up by the body's `id` -> `verify_authentication_response(
  ..., credential_public_key, credential_current_sign_count, require_user_verification=True)` -> store the new sign
  count and `last_used_at = now()` -> issue a session. ANY failure of any kind is the same refusal.
* Credential id stored as the base64url text (unpadded) in `credential_id`.

`auth/sessions.py`:
* `PREFIX = "pks_"`, value = `PREFIX + secrets.token_urlsafe(32)` (47 characters), 30 days.
* `issue(session, credential_pk) -> (value, expires_at)`: delete expired session rows, insert
  `token_hash = sha256(value).hexdigest()`, `created_at = now()`, `expires_at = now() + 30 days` (database clock),
  return the stored `expires_at`.
* `accepts(value: str) -> bool`: return False WITHOUT any database call unless the value starts with `pks_`, is
  exactly 47 characters long, and `passkeys.config()` is not None. Then one lookup by `token_hash` with
  `expires_at > now()` on its own session: `with session_factory()() as s:` where `session_factory` is imported into
  this module (`from nflpi.db import session_factory`; the tests replace `sessions.session_factory`). ANY exception
  from that block: `log.warning("passkey session check failed (%s)", type(exc).__name__)` and
  `raise HTTPException(503, "Sign-in is temporarily unavailable") from None`.
* `revoke(session, value)`: delete the row with that hash (no error if none).

`api/passkey.py`: `router = APIRouter(prefix="/api/passkey")`, `MAX_BODY = 64 * 1024`.

| Route | Who | Replies |
|---|---|---|
| `POST /register/begin` | app token only | 200 options; session -> 403 `Adding a passkey needs the app token`; nobody -> 401 |
| `POST /register/finish` body `{"credential": {...}, "label": "..."}` | app token only | 201 `{id, label, created_at}`; 400 `Passkey registration failed`; 409 `Passkey limit reached (10). Remove one first.`; 413; 422 label |
| `POST /signin/begin` | public | 200 options; 429 `Too many attempts, try again in a minute` |
| `POST /signin/finish` body = the credential JSON | public | 200 `{session, expires_at}` + `Cache-Control: no-store`; 401 `Passkey sign-in failed`; 413; 429 |
| `GET ""` (`/api/passkey`) | signed in (token or session) | 200 `{"passkeys": [{id, label, created_at, last_used_at}]}` oldest first |
| `DELETE /{passkey_id}` | signed in | 204; 404 `Passkey not found`; its sessions go (FK ON DELETE CASCADE, delete with a SQL DELETE) |
| `POST /signout` | signed in | 204; revokes the presented session; with the app token nothing to revoke |

* Every route: not configured -> 503 `Passkey sign-in is not configured`. For signed-in routes check sign-in first,
  then configuration. "App token only" = call `require_token` (so 401/503 stay as everywhere), then
  `secrets.compare_digest` against `get_settings().app_access_token`, else 403.
* Public routes, in this order: configured (503) -> `throttle.allow()` (429) -> capped body read (413; check
  `content-length` first, then cap the stream, as `group.py` does) -> database work in `run_in_threadpool`. A 429
  writes no row and reads no body. The "too many live challenges" case is also 429 with the same text.
* No FastAPI body model on any finish route (take `Request`). Bad JSON, a non-object, missing fields: sign-in -> the
  same 401; register -> 400.
* Alerts (R2), after the commit of a registration or a removal: `sent = push._send(session, title, body,
  "/settings/")`; if `sent`: `push._record(session, "passkey", None, f"passkey:{event}:{row_id}:{secrets.token_hex(8)}",
  {"title": title, "body": body})` and commit. Titles exactly `Passkey added` / `Passkey removed`; body names the label
  (or "no name") and says "Not you? Remove it in Settings and change the app token." Wrap the whole alert in
  `try/except Exception`: log `passkey alert failed (<ExceptionClassName>)`, roll back, never fail the request.
* Logging (`log = logging.getLogger(__name__)`), INFO for events, WARNING for refusals: `passkey registered id=%s`,
  `passkey sign-in ok id=%s`, `passkey sign-in refused (%s, %s)` with our reason word (`body`, `challenge`, `unknown`,
  `verify`) and the exception CLASS name or `-`, `passkey registration refused (%s, %s)`, `passkey removed id=%s`.
  NEVER log: a token, a session value or hash, a challenge, a credential id, a public key, a request body, `str(exc)`
  or `exc_info` of a library exception.
* Pydantic reply models live in `api/passkey.py` (not `schemas.py`).

Models / migration: tables and columns exactly as design section 3 (`sign_count` BigInteger; `credential_id`
String(1400) unique; `challenge_hash`, `token_hash` String(64) unique; `passkey_sessions.credential_id` FK to
`passkey_credentials.id` with `ondelete="CASCADE"`; all times `DateTime(timezone=True)`, not null except
`last_used_at`; `label` nullable). The model and the migration must match exactly (`alembic check` must report no
difference): mirror how `0004`/`0005` declare unique constraints for columns marked `unique=True`.

## CONSTRAINTS (ponytail)

Smallest correct diff. No new dependency. No abstraction with one user, no config for a value that never changes, no
extra files, no speculative features, no unrelated cleanup. Match the surrounding code (ruff, line 120, typed
signatures, short docstrings). Functions under 50 lines. Never trim validation, error handling or a security rule.

## PROOF (run these yourself; localhost needs the sandbox off)

```bash
cd /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-passkey/backend
DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15444/nflpi_test_passkey1 uv run pytest -q tests/test_passkey.py -p no:cacheprovider 2>&1 | tail -15
uvx ruff check nflpi tests migrations
```

Use ONLY that database name (never the default DATABASE_URL, never `nflpi_test`: another run owns it). Do NOT run the
full test suite (it needs a machine lock the coordinator holds); you may run one other single test file to check a
suspicion. Never paste a whole pytest log in your reply.

## RETURN

Changed files; a 10-line summary; the last line of the pytest run and of ruff; anything in the tests or design you
believe is wrong (with the line); any blocker.
