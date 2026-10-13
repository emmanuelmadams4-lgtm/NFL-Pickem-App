# ruff: noqa: E501
"""Mutation pass for step 10 server: break each security rule once and show a passkey test catches it.

Usage: python mutation.py <copy-of-backend-dir> [--dry] [--only=<part of a mutant's name>]
Run it on a throwaway copy (git archive), never on the worktree. --dry only checks every mutation still applies.
Each mutant: (name, clause, file, [(old, new), ...]). A replacement replaces every occurrence of `old`.
A mutant is run against the tests of its own clause only (-k), so 'caught' means that clause's test caught it.
"""

import pathlib
import subprocess
import sys

S, P, A, M = "nflpi/auth/sessions.py", "nflpi/auth/passkeys.py", "nflpi/api/passkey.py", "nflpi/api/main.py"
MUTANTS = [
    ("session expiry not checked", "P12", S, [("where token_hash = :h and expires_at > now()", "where token_hash = :h")]),
    ("session stored in the clear", "P12", S, [('{"h": _hash(value), "c": credential_pk}', '{"h": value, "c": credential_pk}')]),
    ("session lasts 300 days", "P4", S, [("interval '30 days'", "interval '300 days'")]),
    ("expired sessions never cleared", "P12", S, [('session.execute(text("delete from passkey_sessions where expires_at <= now()"))', "pass")]),
    ("any value reaches the database", "P19", S, [("if not value.startswith(PREFIX) or len(value) != VALUE_LENGTH:", "if False:")]),
    ("off switch ignored by sessions", "P1", S, [("    if passkeys.config() is None:\n        log.warning(", "    if False:\n        log.warning(")]),
    ("refusal for unset settings not logged", "C3", S, [('log.warning("passkey session refused: passkey sign-in is not configured")', "pass")]),
    ("wildcard relying party allowed", "C9", P, [('"*" in rp_id or ', "")]),
    ("dotless relying party allowed", "C9", P, [(' or (rp_id != "localhost" and "." not in rp_id)', "")]),
    ("a silent add leaves no record", "C1", A, [('push._record(session, "passkey", None, key, {"title": title, "body": body})', "pass")]),
    ("a silent add is not warned", "C1", A, [('log.warning("passkey %s, nobody was alerted, id=%s", event, row_id)', "pass")]),
    ("database error looks like a wrong session", "R4", S, [('raise HTTPException(503, "Sign-in is temporarily unavailable") from None', "return False")]),
    ("sign-out revokes nothing", "P12", A, [("sessions.revoke(session, supplied)", "pass")]),
    ("any pks_ value is a session", "P2/P12", M, [("if not passkey_api.sessions.accepts(supplied):", 'if not supplied.startswith("pks_"):')]),
    ("http origin allowed", "P1", P, [('scheme_ok = parts.scheme == "https" or (parts.scheme == "http" and rp_id == "localhost")', "scheme_ok = True")]),
    ("origin host suffix without a dot", "P1", P, [('host.endswith("." + rp_id)', "host.endswith(rp_id)")]),
    ("origin with a path allowed", "P1", P, [("return scheme_ok and plain and", "return scheme_ok and")]),
    ("challenge cap counts every kind", "R5", P, [('"select count(*) from passkey_challenges where kind = :k"), {"k": kind}', '"select count(*) from passkey_challenges"), {}')]),
    ("no challenge cap", "P16", P, [("if live >= MAX_LIVE_CHALLENGES:", "if False:")]),
    ("expired challenges never cleared", "P16", P, [('session.execute(text("delete from passkey_challenges where expires_at <= now()"))', "pass")]),
    ("challenge lives 50 minutes", "P6", P, [("CHALLENGE_TTL = timedelta(minutes=5)", "CHALLENGE_TTL = timedelta(minutes=50)")]),
    ("expired challenge accepted", "P6", P, [("and kind = :k and expires_at > now() returning id", "and kind = :k returning id")]),
    ("challenge kind not bound", "P9", P, [("where challenge_hash = :h and kind = :k and", "where challenge_hash = :h and :k = :k and")]),
    ("challenge not single use", "P5", P, [('"delete from passkey_challenges where challenge_hash = :h and kind = :k and expires_at > now() returning id"', '"select id from passkey_challenges where challenge_hash = :h and kind = :k and expires_at > now()"')]),
    ("challenge matched by spelling", "R3", P, [
        ('{"h": hashlib.sha256(challenge).hexdigest(), "k": kind,', '{"h": hashlib.sha256(bytes_to_base64url(challenge).encode()).hexdigest(), "k": kind,'),
        ("digest = hashlib.sha256(challenge).hexdigest()", 'digest = hashlib.sha256(__import__("json").loads(base64url_to_bytes(client_data_json))["challenge"].encode()).hexdigest()'),
    ]),
    ("extra origins accepted", "P7", P, [("expected_origin=list(cfg.origins),", 'expected_origin=[*cfg.origins, "https://evil.example", f"http://{cfg.rp_id}"],')]),
    ("user verification not required", "P11", P, [("require_user_verification=True,", "require_user_verification=False,")]),
    ("sign count not compared", "P10", P, [("credential_current_sign_count=sign_count,", "credential_current_sign_count=0,")]),
    ("sign-in options: verification preferred", "P14", P, [("generate_authentication_options(rp_id=cfg.rp_id, user_verification=UserVerificationRequirement.REQUIRED)", "generate_authentication_options(rp_id=cfg.rp_id)")]),
    ("register options: resident key preferred", "P3", P, [("resident_key=ResidentKeyRequirement.REQUIRED", "resident_key=ResidentKeyRequirement.PREFERRED")]),
    ("stored passkeys not excluded", "P3", P, [("exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c)) for c in stored],", "exclude_credentials=[],")]),
    ("a session may add a passkey", "R1", A, [('raise HTTPException(403, "Adding a passkey needs the app token")', "return")]),
    ("register begin is public", "P2", A, [('@router.post("/register/begin", dependencies=[Depends(_owner)])', '@router.post("/register/begin")')]),
    ("register finish is public", "P2", A, [("status_code=201, response_model=RegisteredOut, dependencies=[Depends(_owner)])", "status_code=201, response_model=RegisteredOut)")]),
    ("list is public", "P2", A, [('@router.get("", response_model=PasskeyListOut, dependencies=[Depends(_signed_in)])', '@router.get("", response_model=PasskeyListOut)')]),
    ("no rate limit", "P16", A, [("if not throttle.allow():", "if False:")]),
    ("content-length cap off", "P16", A, [("too_big = int(content_length) > MAX_BODY", "too_big = False")]),
    ("stream cap off", "P16", A, [("if len(data) + len(chunk) > MAX_BODY:", "if False:")]),
    ("no passkey cap", "P16", A, [(">= passkeys.MAX_PASSKEYS:", ">= 10**9:")]),
    ("unknown passkey answers differently", "P14", A, [('raise _Refused("unknown")', 'raise HTTPException(404, "Unknown passkey")')]),
    ("credential id shape not checked", "P14", A, [("if not CREDENTIAL_ID.fullmatch(credential_id):", "if False:")]),
    ("deep nesting crashes the parser", "P14", A, [("except (ValueError, KeyError, TypeError, RecursionError):", "except (ValueError, KeyError, TypeError):")]),
    ("new sign count not stored", "P10", A, [("set sign_count = :n, last_used_at = now()", "set sign_count = sign_count + 0 * :n, last_used_at = now()")]),
    ("sessions survive passkey removal", "P13", "nflpi/models.py", [('ForeignKey("passkey_credentials.id", ondelete="CASCADE")', 'ForeignKey("passkey_credentials.id")')]),
    ("session value logged", "P15", A, [('log.info("passkey sign-in ok id=%s", row.id)', 'log.info("passkey sign-in ok id=%s %s", row.id, value)')]),
    ("credential id logged", "P15", A, [('raise _Refused("unknown")', 'raise _Refused("unknown", credential_id)')]),
    ("no alert when a passkey is added", "R2", A, [('_alert(session, "added", label, row.id)', "pass")]),
    ("no alert when a passkey is removed", "R2", A, [('_alert(session, "removed", row.label, passkey_id)', "pass")]),
    ("sign-in reply may be cached", "P4", A, [('response.headers["Cache-Control"] = "no-store"', "pass")]),
    ("control characters allowed in a label", "P3", A, [('not any(unicodedata.category(c).startswith("C") for c in label)', "True")]),
    ("throttle window never fills", "P16", "nflpi/auth/throttle.py", [("if len(_calls) >= LIMIT:", "if False:")]),
    ("throttle window never slides", "P16", "nflpi/auth/throttle.py", [("while _calls and now - _calls[0] >= WINDOW_S:", "while False:")]),
    ("throttle window is an hour", "P16", "nflpi/auth/throttle.py", [("WINDOW_S = 60.0", "WINDOW_S = 3600.0")]),
    ("registration challenge never checked or burnt", "P5", A, [
        ('challenge = passkeys.burn_challenge(session, "register", client_data)', "challenge = passkeys.parse_client_data_json(passkeys.base64url_to_bytes(client_data)).challenge"),
    ]),
    ("list answers 503 while passkeys are off", "P1", A, [("def list_passkeys(session: DB)", "def list_passkeys(session: DB, cfg: Cfg)")]),
    ("remove answers 503 while passkeys are off", "P1", A, [("session: DB) -> Response:\n    row = session.execute(", "session: DB, cfg: Cfg) -> Response:\n    row = session.execute(")]),
]


OWN_TESTS = {"C1": "r2_", "C3": "p1_", "C9": "p1_"}  # clauses added by review live in these tests


def main() -> int:
    backend = pathlib.Path(sys.argv[1])
    dry = "--dry" in sys.argv
    survived = unapplied = 0
    wanted = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    for name, clause, rel, edits in MUTANTS:
        if wanted and not any(w in name for w in wanted):
            continue
        path = backend / rel
        original = path.read_text()
        mutated = original
        for old, new in edits:
            if old not in mutated:
                print(f"NOT APPLIED  {clause:7} {name}: {old[:50]!r}")
                unapplied += 1
            mutated = mutated.replace(old, new)
        if dry or mutated == original:
            continue
        # Only the tests named for the mutant's own clause run: the clause's own test must be the one that bites.
        only = " or ".join(OWN_TESTS.get(c, c.lower() + "_") for c in clause.split("/"))
        path.write_text(mutated)
        try:
            run = subprocess.run(
                ["uv", "run", "pytest", "-q", "-x", "tests/test_passkey.py", "-p", "no:cacheprovider", "--color=no", "-rfE", "-k", only],
                cwd=backend, capture_output=True, text=True, timeout=300,
            )  # fmt: skip
        finally:
            path.write_text(original)
        caught = [line.split("::")[1].split(" ")[0] for line in run.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))]
        if run.returncode == 0:
            survived += 1
            print(f"SURVIVED     {clause:7} {name}", flush=True)
        else:
            print(f"caught       {clause:7} {name}  <- {caught[0] if caught else 'exit ' + str(run.returncode)}", flush=True)
    print(f"MUTATION: {len(MUTANTS)} mutants, {survived} survived, {unapplied} not applied")
    return 1 if survived or unapplied else 0


if __name__ == "__main__":
    sys.exit(main())
