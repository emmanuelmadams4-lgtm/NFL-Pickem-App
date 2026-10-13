"""Passkey (WebAuthn) sign-in routes: register (app token only), sign in (public), list, remove, sign out."""

import json
import logging
import re
import secrets
import unicodedata
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from nflpi.auth import passkeys, sessions, throttle
from nflpi.config import get_settings
from nflpi.db import get_session, session_factory
from nflpi.models import PasskeyCredential
from nflpi.notify import push

log = logging.getLogger(__name__)
MAX_BODY = 64 * 1024
NOT_CONFIGURED = "Passkey sign-in is not configured"
SIGNIN_FAILED = "Passkey sign-in failed"
REGISTER_FAILED = "Passkey registration failed"
TOO_MANY = "Too many attempts, try again in a minute"
LABEL_ERROR = "Label must be 1 to 64 printable characters"
CREDENTIAL_ID = re.compile(r"[A-Za-z0-9_-]{1,1400}")


def _signed_in(authorization: Annotated[str | None, Header()] = None) -> None:
    from nflpi.api.main import require_token

    require_token(authorization)


def _owner(authorization: Annotated[str | None, Header()] = None) -> None:
    """Sign-in with the app token itself; a passkey session must not be able to add a permanent passkey."""
    _signed_in(authorization)
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied.encode(), get_settings().app_access_token.encode()):
        raise HTTPException(403, "Adding a passkey needs the app token")


def _config() -> passkeys.PasskeyConfig:
    cfg = passkeys.config()
    if cfg is None:
        raise HTTPException(503, NOT_CONFIGURED)
    return cfg


router = APIRouter(prefix="/api/passkey")
Cfg = Annotated[passkeys.PasskeyConfig, Depends(_config)]
DB = Annotated[Session, Depends(get_session)]


class RegisteredOut(BaseModel):
    id: int
    label: str | None
    created_at: datetime


class PasskeyOut(RegisteredOut):
    last_used_at: datetime | None


class PasskeyListOut(BaseModel):
    passkeys: list[PasskeyOut]


class SessionOut(BaseModel):
    session: str
    expires_at: datetime


class _Refused(Exception):
    def __init__(self, reason: str, error: str = "-") -> None:
        self.reason = reason
        self.error = error


async def _read_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            too_big = int(content_length) > MAX_BODY
        except ValueError:
            raise HTTPException(400, "bad content-length") from None
        if too_big:
            raise HTTPException(413, "body is too large")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY:
            raise HTTPException(413, "body is too large")
        data.extend(chunk)
    return bytes(data)


def _begin(
    make_options: Callable[[Session, passkeys.PasskeyConfig], dict[str, Any]],
    session: Session,
    cfg: passkeys.PasskeyConfig,
) -> dict[str, Any]:
    try:
        return make_options(session, cfg)
    except passkeys.TooManyChallenges:
        raise HTTPException(429, TOO_MANY) from None


def _alert(session: Session, event: str, label: str | None, row_id: int) -> None:
    """Tell the owner's devices a passkey was added or removed. Never fails the request."""
    title = f"Passkey {event}"
    body = f"{label or 'no name'}. Not you? Remove it in Settings and change the app token."
    try:
        sent = push._send(session, title, body, "/settings/")
        key = f"passkey:{event}:{row_id}:{secrets.token_hex(8)}"
        push._record(session, "passkey", None, key, {"title": title, "body": body})
        session.commit()
        if not sent:
            log.warning("passkey %s, nobody was alerted, id=%s", event, row_id)
    except Exception as exc:  # noqa: BLE001 - an alert must not undo the change
        log.warning("passkey alert failed (%s)", type(exc).__name__)
        session.rollback()


# --- register -------------------------------------------------------------------------------------------------------


@router.post("/register/begin", dependencies=[Depends(_owner)])
def register_begin(session: DB, cfg: Cfg) -> dict[str, Any]:
    return _begin(passkeys.registration_options, session, cfg)


def _clean_label(label: Any) -> str | None:
    if label is None:
        return None
    if isinstance(label, str):
        label = label.strip()
        if 1 <= len(label) <= 64 and not any(unicodedata.category(c).startswith("C") for c in label):
            return label
    raise HTTPException(422, LABEL_ERROR)


def _register_finish(raw: bytes, cfg: passkeys.PasskeyConfig) -> RegisteredOut:
    try:
        body = json.loads(raw)
        credential = body["credential"]
        client_data = credential["response"]["clientDataJSON"]
        if not isinstance(credential, dict) or not isinstance(client_data, str):
            raise TypeError
    except (ValueError, KeyError, TypeError, RecursionError):
        log.warning("passkey registration refused (body, -)")
        raise HTTPException(400, REGISTER_FAILED) from None
    label = _clean_label(body.get("label"))
    with session_factory()() as session:
        # Check-then-insert: fine, only the owner (app token) can call this.
        if passkeys.credential_count(session) >= passkeys.MAX_PASSKEYS:
            raise HTTPException(409, f"Passkey limit reached ({passkeys.MAX_PASSKEYS}). Remove one first.")
        challenge = passkeys.burn_challenge(session, "register", client_data)
        if challenge is None:
            log.warning("passkey registration refused (challenge, -)")
            raise HTTPException(400, REGISTER_FAILED)
        try:
            credential_id, public_key, sign_count = passkeys.verify_registration(cfg, credential, challenge)
        except Exception as exc:  # noqa: BLE001 - the library raises many types; all are one refusal
            log.warning("passkey registration refused (verify, %s)", type(exc).__name__)
            raise HTTPException(400, REGISTER_FAILED) from None
        try:
            row = session.execute(
                text(
                    "insert into passkey_credentials (credential_id, public_key, sign_count, label, created_at) "
                    "values (:c, :k, :n, :l, now()) returning id, created_at"
                ),
                {"c": credential_id, "k": public_key, "n": sign_count, "l": label},
            ).one()
            session.commit()
        except IntegrityError:
            session.rollback()
            log.warning("passkey registration refused (duplicate, -)")
            raise HTTPException(400, REGISTER_FAILED) from None
        log.info("passkey registered id=%s", row.id)
        _alert(session, "added", label, row.id)
        return RegisteredOut(id=row.id, label=label, created_at=row.created_at)


@router.post("/register/finish", status_code=201, response_model=RegisteredOut, dependencies=[Depends(_owner)])
async def register_finish(request: Request, cfg: Cfg) -> RegisteredOut:
    raw = await _read_body(request)
    return await run_in_threadpool(_register_finish, raw, cfg)


# --- sign in --------------------------------------------------------------------------------------------------------


@router.post("/signin/begin")
def signin_begin(session: DB, cfg: Cfg) -> dict[str, Any]:
    if not throttle.allow():
        raise HTTPException(429, TOO_MANY)
    return _begin(passkeys.signin_options, session, cfg)


def _signin_finish(raw: bytes, cfg: passkeys.PasskeyConfig) -> tuple[str, datetime]:
    try:
        body = json.loads(raw)
        credential_id, client_data = body["id"], body["response"]["clientDataJSON"]
        if not isinstance(body, dict) or not isinstance(credential_id, str) or not isinstance(client_data, str):
            raise TypeError
    except (ValueError, KeyError, TypeError, RecursionError):
        raise _Refused("body") from None
    if not CREDENTIAL_ID.fullmatch(credential_id):
        raise _Refused("body")
    with session_factory()() as session:
        challenge = passkeys.burn_challenge(session, "signin", client_data)
        if challenge is None:
            raise _Refused("challenge")
        row = session.scalars(select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)).first()
        if row is None:
            raise _Refused("unknown")
        try:
            new_count = passkeys.verify_signin(cfg, body, challenge, row.public_key, row.sign_count)
        except Exception as exc:  # noqa: BLE001 - the library raises many types; all are one refusal
            raise _Refused("verify", type(exc).__name__) from None
        try:
            session.execute(
                text(
                    "update passkey_credentials set sign_count = :n, last_used_at = now() "
                    "where id = :i and sign_count <= :n"
                ),
                {"n": new_count, "i": row.id},
            )
            value, expires_at = sessions.issue(session, row.id)
        except IntegrityError:  # the passkey was removed while this sign-in was finishing
            session.rollback()
            raise _Refused("unknown") from None
        log.info("passkey sign-in ok id=%s", row.id)
        return value, expires_at


@router.post("/signin/finish", response_model=SessionOut)
async def signin_finish(request: Request, response: Response, cfg: Cfg) -> SessionOut:
    if not throttle.allow():
        raise HTTPException(429, TOO_MANY)
    raw = await _read_body(request)
    try:
        value, expires_at = await run_in_threadpool(_signin_finish, raw, cfg)
    except _Refused as refused:
        log.warning("passkey sign-in refused (%s, %s)", refused.reason, refused.error)
        raise HTTPException(401, SIGNIN_FAILED) from None
    response.headers["Cache-Control"] = "no-store"
    return SessionOut(session=value, expires_at=expires_at)


# --- manage ---------------------------------------------------------------------------------------------------------


@router.get("", response_model=PasskeyListOut, dependencies=[Depends(_signed_in)])
def list_passkeys(session: DB) -> PasskeyListOut:
    rows = session.scalars(select(PasskeyCredential).order_by(PasskeyCredential.created_at, PasskeyCredential.id))
    return PasskeyListOut(
        passkeys=[
            PasskeyOut(id=r.id, label=r.label, created_at=r.created_at, last_used_at=r.last_used_at) for r in rows
        ]
    )


@router.delete("/{passkey_id}", status_code=204, dependencies=[Depends(_signed_in)])
def remove_passkey(passkey_id: Annotated[int, Path(ge=1, le=2_147_483_647)], session: DB) -> Response:
    row = session.execute(
        text("delete from passkey_credentials where id = :i returning label"), {"i": passkey_id}
    ).first()
    session.commit()  # the sessions go with it (ON DELETE CASCADE)
    if row is None:
        raise HTTPException(404, "Passkey not found")
    log.info("passkey removed id=%s", passkey_id)
    _alert(session, "removed", row.label, passkey_id)
    return Response(status_code=204)


@router.post("/signout", status_code=204, dependencies=[Depends(_signed_in)])
def signout(session: DB, authorization: Annotated[str | None, Header()] = None) -> Response:
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if supplied.startswith(sessions.PREFIX):
        sessions.revoke(session, supplied)
    return Response(status_code=204)
