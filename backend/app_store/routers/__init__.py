"""App Store API routers: auth, apps, credentials, backups, audit, health, push.

Note: installer is imported separately (see main.py) to avoid circular imports.
"""

from fastapi import APIRouter

from app_store.routers import auth, apps, credentials, backups, audit, health, push

# Main API router for the App Store (v0.1)
router = APIRouter(prefix="/api/store")


def include_in_app(app):
    # Auth router routes are /auth/* (no prefix needed beyond /store)
    app.include_router(auth.router, prefix="/auth", tags=["auth"])

    # Apps router routes are / (list) and /{slug} (detail)
    # Prefix with /store/apps
    app.include_router(apps.router, prefix="/apps", tags=["apps"])

    # Credentials router routes are / (list) and /{app_slug} (detail)
    app.include_router(credentials.router, prefix="/credentials", tags=["credentials"])

    # Backups router routes are /backups (list), /backups (create), /backups/{id}/restore
    app.include_router(backups.router, prefix="/backups", tags=["backups"])

    # Audit router routes are /audit/logs, /audit/log
    app.include_router(audit.router, prefix="/audit", tags=["audit"])

    # Health router routes are /health, /dashboard
    app.include_router(health.router, prefix="/health", tags=["health"])

    # Push router routes
    app.include_router(push.router, prefix="/push", tags=["push"])
