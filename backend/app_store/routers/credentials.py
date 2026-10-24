"""Credentials router: per-app encrypted secrets."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from app_store.db import get_session
from app_store.models import App, AppCredential
from app_store.routers import schemas as s

router = APIRouter(prefix="", tags=["credentials"])

# Master key for encrypting app credentials (server .env only)
_KEY = None


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        import os
        key = os.environ.get("APP_STORE_CREDENTIAL_KEY")
        if not key:
            raise HTTPException(503, "No credential key set (APP_STORE_CREDENTIAL_KEY)")
        _KEY = base64.urlsafe_b64encode(key.encode())
    return _KEY


def _get_db():
    for session in get_session():
        yield session


@router.get("/{app_slug}", response_model=list[s.AppCredentialOut])
async def list_credentials(app_slug: str, db: Session = Depends(_get_db)):
    """List all credentials for an app."""
    app = db.execute(select(App).where(App.slug == app_slug)).scalar_one_or_none()
    if not app:
        raise HTTPException(404, f"App '{app_slug}' not found")
    creds = db.execute(select(AppCredential).where(AppCredential.app_id == app.id)).scalars().all()
    return [s.AppCredentialOut(
        id=c.id, key=c.key, algorithm=c.algorithm,
        created_at=c.created_at, updated_at=c.updated_at,
    ) for c in creds]


@router.post("/{app_slug}", response_model=s.AppCredentialOut, status_code=201)
async def create_credential(app_slug: str, body: s.AppCredentialCreate, db: Session = Depends(_get_db)):
    """Create an encrypted credential for an app."""
    app = db.execute(select(App).where(App.slug == app_slug)).scalar_one_or_none()
    if not app:
        raise HTTPException(404, f"App '{app_slug}' not found")

    key = _get_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(body.value.encode())

    cred = AppCredential(
        app_id=app.id,
        key=body.key,
        encrypted_value=encrypted,
        algorithm=body.algorithm,
        created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db.add(cred)
    db.commit()
    return s.AppCredentialOut(
        id=cred.id, key=cred.key, algorithm=cred.algorithm,
        created_at=cred.created_at, updated_at=cred.updated_at,
    )


@router.get("/{app_slug}/{key}", response_model=s.AppCredentialOut)
async def get_credential(app_slug: str, key: str, db: Session = Depends(_get_db)):
    """Get a single credential (decrypted)."""
    app = db.execute(select(App).where(App.slug == app_slug)).scalar_one_or_none()
    if not app:
        raise HTTPException(404, f"App '{app_slug}' not found")

    cred = db.execute(
        select(AppCredential).where(
            AppCredential.app_id == app.id, AppCredential.key == key
        )
    ).scalar_one_or_none()
    if not cred:
        raise HTTPException(404, "Credential not found")

    key_bytes = _get_key()
    fernet = Fernet(key_bytes)
    decrypted = fernet.decrypt(cred.encrypted_value).decode()

    return s.AppCredentialOut(
        id=cred.id, key=cred.key, algorithm=cred.algorithm,
        created_at=cred.created_at, updated_at=cred.updated_at,
    )
