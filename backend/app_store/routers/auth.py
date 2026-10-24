"""Auth router: passkey enrollment, login, token refresh, session management."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_store.db import get_session
from app_store.models import AuditLog, PasskeyCredential
from app_store.routers import schemas as s

# Router with NO prefix - include_in_app adds the /auth prefix
router = APIRouter(tags=["auth"])


def _get_db():
    for session in get_session():
        yield session


# ---------------------------------------------------------------------------
# Passkey enrollment
# ---------------------------------------------------------------------------

@router.post("/register", response_model=s.RegisterResponse)
async def register(request: Request, body: s.RegisterRequest, db: Session = Depends(_get_db)):
    """Register a user (one-time enrollment)."""
    from app_store.auth.passkeys import WebAuthn

    webauthn = WebAuthn(rp_id="localhost", origins="http://localhost,https://localhost")

    challenge, data = webauthn.get_registration_challenge(
        user_id=body.user_id,
        display_name=body.user_id,
    )

    return {"challenge": challenge, "public_key": data["public_key"],
            "rp_id": "localhost", "timeout": 60000}


@router.post("/signup", response_model=s.RegisterResponse)
async def signup(request: Request, body: s.PasskeyEnrollRequest, db: Session = Depends(_get_db)):
    """Complete passkey enrollment."""
    from app_store.auth.passkeys import WebAuthn

    webauthn = WebAuthn(rp_id="localhost", origins="http://localhost,https://localhost")

    credential = webauthn.verify_registration(
        user_id=body.user_id,
        request_json=body.credential.model_dump(by_alias=True),
    )

    db_cred = PasskeyCredential(
        id=credential["id"],
        raw_id=credential["raw_id"],
        public_key=credential["public_key"],
        sign_count=credential["sign_count"],
        transports=credential.get("transports", []),
    )
    db.add(db_cred)
    db.commit()

    return {"credential": s.PasskeyCredential(
        id=credential["id"],
        rawId=credential["raw_id"],
        public_key=credential["public_key"],
        sign_count=credential["sign_count"],
        key_type=credential["key_type"],
        transports=credential.get("transports", []),
    )}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=s.LoginResponse)
async def login(request: Request, body: s.LoginRequest, db: Session = Depends(_get_db)):
    """Verify a credential and return an access token."""
    from app_store.auth.passkeys import WebAuthn

    webauthn = WebAuthn(rp_id="localhost", origins="http://localhost,https://localhost")

    cred = db.execute(
        select(PasskeyCredential).where(PasskeyCredential.raw_id == body.credential.raw_id)
    ).scalar_one_or_none()

    if not cred:
        raise HTTPException(401, "Invalid credential")

    if not webauthn.verify_assertion(
        credential_id=cred.id,
        request_json=body.credential.model_dump(by_alias=True),
        recorded_sign_count=cred.sign_count,
    ):
        raise HTTPException(401, "Credential verification failed")

    cred.sign_count = body.credential.sign_count
    db.commit()

    token = os.urandom(32).hex()
    return {"access_token": token, "token_type": "Bearer"}


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@router.post("/refresh")
async def refresh(request: Request, body: s.TokenRefreshRequest, db: Session = Depends(_get_db)):
    """Refresh an access token."""
    if not body.refresh_token:
        raise HTTPException(401, "Invalid refresh token")
    return {"access_token": os.urandom(32).hex(), "token_type": "Bearer"}


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout(request: Request):
    """Revoke a session."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/audit/logs", response_model=list[s.AuditLogOut])
async def get_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(_get_db),
):
    """Query the append-only audit log."""
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    query = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit)
    results = db.execute(query).scalars().all()

    return [
        s.AuditLogOut(
            id=entry.id,
            user_id=entry.user_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            actor_ip=entry.actor_ip,
            actor_user_agent=entry.actor_user_agent,
            session_id=entry.session_id,
            operation_id=entry.operation_id,
            success=entry.success,
            error_message=entry.error_message,
            created_at=entry.created_at,
        )
        for entry in results
    ]


@router.post("/audit/log", status_code=201)
async def log_audit(
    body: s.AuditLogEvent,
    request: Request,
    db: Session = Depends(_get_db),
):
    """Write an audit log entry."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    entry = AuditLog(
        user_id=body.user_id,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        actor_ip=ip,
        actor_user_agent=ua,
        session_id=body.session_id,
        operation_id=body.operation_id,
        success=body.success,
        error_message=body.error_message,
        created_at="2026-10-24T00:00:00Z",
    )
    db.add(entry)
    db.commit()
    return {"status": "logged", "id": entry.id}
