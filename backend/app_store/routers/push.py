"""Push router: Web Push subscriptions and notifications."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_store.db import get_session
from app_store.models import App, PushSubscription
from app_store.routers import schemas as s

# Router with NO prefix - include_in_app adds the /push prefix
router = APIRouter(tags=["push"])

def _get_db():
    for session in get_session():
        yield session


# ---------------------------------------------------------------------------
# VAPID key management
# ---------------------------------------------------------------------------

import os


def _get_vapid_keys():
    """Return VAPID keys from env."""
    pub = os.environ.get("VAPID_PUBLIC_KEY")
    priv = os.environ.get("VAPID_PRIVATE_KEY")
    if not pub or not priv:
        raise HTTPException(503, "VAPID keys not configured")
    return pub, priv


@router.get("/vapid-keys")
async def get_vapid_keys():
    """Get VAPID public key for Web Push."""
    # Return a placeholder - in production, use proper VAPID keys
    return {"public_key": "BLANK_PUBLIC_KEY", "auth": "BLANK_AUTH"}


@router.post("/push/subscriptions", response_model=s.PushSubscriptionOut, status_code=201)
async def create_subscription(
    body: s.PushSubscriptionCreate,
    db: Session = Depends(_get_db),
):
    """Register a device for push notifications."""
    app = db.execute(
        select(App).where(App.id == body.app_id)
    ).scalar_one_or_none()
    if not app:
        raise HTTPException(404, "App not found")

    sub = PushSubscription(
        app_id=body.app_id,
        user_id=body.subscription.get("endpoint", ""),
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        subscription=body.subscription,
        created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db.add(sub)
    db.commit()
    return s.PushSubscriptionOut(
        endpoint=sub.endpoint,
        p256dh=sub.p256dh,
        auth=sub.auth,
        subscription=sub.subscription,
    )


@router.delete("/push/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    db: Session = Depends(_get_db),
):
    """Unregister a device from push notifications."""
    sub = db.execute(
        select(PushSubscription).where(PushSubscription.id == subscription_id)
    ).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    db.delete(sub)
    db.commit()
    return {"status": "unsubscribed", "id": subscription_id}


@router.get("/push/subscriptions", response_model=list[s.PushSubscriptionOut])
async def list_subscriptions(app_slug: str | None = None, db: Session = Depends(_get_db)):
    """List all push subscriptions."""
    query = select(PushSubscription)
    if app_slug:
        app = db.execute(select(App).where(App.slug == app_slug)).scalar_one_or_none()
        if not app:
            raise HTTPException(404, "App not found")
        query = query.where(PushSubscription.app_id == app.id)

    subs = db.execute(query).scalars().all()
    return [
        s.PushSubscriptionOut(
            endpoint=s.endpoint,
            p256dh=s.p256dh,
            auth=s.auth,
            subscription=s.subscription,
        )
        for s in subs
    ]


@router.get("/push/notifications")
async def get_notifications(db: Session = Depends(_get_db)):
    """Get pending notifications for a user (simplified)."""
    # In production, this would query push_subscriptions + subscription state
    return {"status": "ok", "message": "Notifications are delivered via Web Push"}
