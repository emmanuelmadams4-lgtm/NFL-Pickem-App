"""Passkey sessions: a random bearer value, stored only as its sha256, valid for a fixed 30 days."""

import hashlib
import logging
import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from nflpi.auth import passkeys
from nflpi.db import session_factory

log = logging.getLogger(__name__)
PREFIX = "pks_"
VALUE_LENGTH = len(PREFIX) + 43  # token_urlsafe(32) is 43 characters


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue(session: Session, credential_pk: int) -> tuple[str, datetime]:
    """Clear expired rows, store a new session and return (value, stored expiry)."""
    value = PREFIX + secrets.token_urlsafe(32)
    session.execute(text("delete from passkey_sessions where expires_at <= now()"))
    expires_at = session.execute(
        text(
            "insert into passkey_sessions (token_hash, credential_id, created_at, expires_at) "
            "values (:h, :c, now(), now() + interval '30 days') returning expires_at"
        ),
        {"h": _hash(value), "c": credential_pk},
    ).scalar_one()
    session.commit()
    return value, expires_at


def accepts(value: str) -> bool:
    """True for a live session value. No database call unless the value looks like one and passkeys are on."""
    if not value.startswith(PREFIX) or len(value) != VALUE_LENGTH or passkeys.config() is None:
        return False
    try:
        with session_factory()() as s:
            row = s.execute(
                text("select 1 from passkey_sessions where token_hash = :h and expires_at > now()"), {"h": _hash(value)}
            ).first()
    except Exception as exc:  # noqa: BLE001 - fail closed, but as a retryable 503
        log.warning("passkey session check failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Sign-in is temporarily unavailable") from None
    return row is not None


def revoke(session: Session, value: str) -> None:
    session.execute(text("delete from passkey_sessions where token_hash = :h"), {"h": _hash(value)})
    session.commit()
