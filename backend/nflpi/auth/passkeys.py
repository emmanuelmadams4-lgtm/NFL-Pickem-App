"""Passkey (WebAuthn) ceremonies. All verification is done by the webauthn library; this adds storage and bounds."""

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict, parse_client_data_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from nflpi.config import get_settings

MAX_PASSKEYS = 10
MAX_LIVE_CHALLENGES = 50
CHALLENGE_TTL = timedelta(minutes=5)
RP_NAME = "NFL Pick'em"


@dataclass(frozen=True)
class PasskeyConfig:
    rp_id: str
    origins: tuple[str, ...]


class TooManyChallenges(Exception):
    """Too many live challenges of one kind."""


def _origin_ok(origin: str, rp_id: str) -> bool:
    parts = urlsplit(origin)
    try:
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError:
        return False
    host = parts.hostname or ""
    scheme_ok = parts.scheme == "https" or (parts.scheme == "http" and rp_id == "localhost")
    plain = origin == f"{parts.scheme}://{parts.netloc}"  # no path, query or fragment
    return scheme_ok and plain and "@" not in parts.netloc and (host == rp_id or host.endswith("." + rp_id))


def config() -> PasskeyConfig | None:
    """The relying party and allowed origins from settings, or None when unset or unsafe."""
    s = get_settings()
    rp_id = s.passkey_rp_id.strip()
    origins = tuple(o.strip() for o in s.passkey_origins.split(",") if o.strip())
    if not rp_id or "*" in rp_id or (rp_id != "localhost" and "." not in rp_id):
        return None
    if not origins or not all(_origin_ok(o, rp_id) for o in origins):
        return None
    return PasskeyConfig(rp_id, origins)


def _store_challenge(session: Session, kind: str, challenge: bytes) -> None:
    session.execute(text("delete from passkey_challenges where expires_at <= now()"))
    live = session.execute(
        text("select count(*) from passkey_challenges where kind = :k"), {"k": kind}
    ).scalar_one()
    if live >= MAX_LIVE_CHALLENGES:
        session.rollback()
        raise TooManyChallenges
    session.execute(
        text(
            "insert into passkey_challenges (challenge_hash, kind, created_at, expires_at) "
            "values (:h, :k, now(), now() + make_interval(secs => :ttl))"
        ),
        {"h": hashlib.sha256(challenge).hexdigest(), "k": kind, "ttl": CHALLENGE_TTL.total_seconds()},
    )
    session.commit()


def burn_challenge(session: Session, kind: str, client_data_json: str) -> bytes | None:
    """Delete the live challenge named in clientDataJSON and return its bytes; None if absent, expired or unparsable."""
    try:
        challenge = parse_client_data_json(base64url_to_bytes(client_data_json)).challenge
        digest = hashlib.sha256(challenge).hexdigest()
    except Exception:  # noqa: BLE001 - every parse failure is a refusal
        return None
    row = session.execute(
        text(
            "delete from passkey_challenges where challenge_hash = :h and kind = :k and expires_at > now() returning id"
        ),
        {"h": digest, "k": kind},
    ).first()
    session.commit()
    return challenge if row is not None else None


def credential_count(session: Session) -> int:
    return session.execute(text("select count(*) from passkey_credentials")).scalar_one()


def registration_options(session: Session, cfg: PasskeyConfig) -> dict[str, Any]:
    stored = session.execute(text("select credential_id from passkey_credentials")).scalars().all()
    options = generate_registration_options(
        rp_id=cfg.rp_id,
        rp_name=RP_NAME,
        user_name="owner",
        user_id=b"nflpi-owner",
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c)) for c in stored],
    )
    _store_challenge(session, "register", options.challenge)
    return options_to_json_dict(options)


def signin_options(session: Session, cfg: PasskeyConfig) -> dict[str, Any]:
    options = generate_authentication_options(rp_id=cfg.rp_id, user_verification=UserVerificationRequirement.REQUIRED)
    _store_challenge(session, "signin", options.challenge)
    return options_to_json_dict(options)


def verify_registration(cfg: PasskeyConfig, credential: dict[str, Any], challenge: bytes) -> tuple[str, bytes, int]:
    """Return (credential id as base64url, public key, sign count); raises on any failure."""
    verified = verify_registration_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=cfg.rp_id,
        expected_origin=list(cfg.origins),
        require_user_verification=True,
    )
    return bytes_to_base64url(verified.credential_id), verified.credential_public_key, verified.sign_count


def verify_signin(
    cfg: PasskeyConfig, credential: dict[str, Any], challenge: bytes, public_key: bytes, sign_count: int
) -> int:
    """Return the new sign count; raises on any failure."""
    return verify_authentication_response(
        credential=credential,
        expected_challenge=challenge,
        expected_rp_id=cfg.rp_id,
        expected_origin=list(cfg.origins),
        credential_public_key=public_key,
        credential_current_sign_count=sign_count,
        require_user_verification=True,
    ).new_sign_count
