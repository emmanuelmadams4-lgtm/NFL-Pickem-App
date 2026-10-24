"""Apps router: catalog, CRUD, install state."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_store.db import get_session
from app_store.models import App, AppVersion
from app_store.routers import schemas as s

# Router with NO prefix - include_in_app adds the /apps prefix
router = APIRouter(tags=["apps"])


def _get_db():
    for session in get_session():
        yield session


@router.get("", response_model=list[s.AppOut])
async def list_apps(db: Session = Depends(_get_db)):
    """List all curated apps in the store."""
    results = db.execute(select(App)).scalars().all()
    return [
        s.AppOut(
            id=app.id,
            name=app.name,
            slug=app.slug,
            description=app.description,
            icon_url=app.icon_url,
            source=app.source,
            source_url=app.source_url,
            category=app.category,
            risk_level=app.risk_level,
            requires_vm=app.requires_vm,
            installed=app.installed,
            versions=[s.AppVersionOut(
                id=v.id,
                version=v.version,
                image_ref=v.image_ref,
                image_digest=v.image_digest,
                manifest=v.manifest,
                provenance=v.provenance,
                is_current=v.is_current,
            ) for v in app.versions],
            created_at=app.created_at,
        )
        for app in results
    ]


@router.get("/{slug}", response_model=s.AppOut)
async def get_app(slug: str, db: Session = Depends(_get_db)):
    """Get a single app by slug."""
    app = db.execute(select(App).where(App.slug == slug)).scalar_one_or_none()
    if not app:
        raise HTTPException(404, f"App '{slug}' not found")
    return s.AppOut(
        id=app.id,
        name=app.name,
        slug=app.slug,
        description=app.description,
        icon_url=app.icon_url,
        source=app.source,
        source_url=app.source_url,
        category=app.category,
        risk_level=app.risk_level,
        requires_vm=app.requires_vm,
        installed=app.installed,
        versions=[s.AppVersionOut(
            id=v.id,
            version=v.version,
            image_ref=v.image_ref,
            image_digest=v.image_digest,
            manifest=v.manifest,
            provenance=v.provenance,
            is_current=v.is_current,
        ) for v in app.versions],
        created_at=app.created_at,
    )


@router.post("", response_model=s.AppOut, status_code=201)
async def create_app(body: s.AppCreate, db: Session = Depends(_get_db)):
    """Create a curated app in the store."""
    from datetime import datetime
    app = App(
        owner_id="owner",
        name=body.name,
        slug=body.slug,
        description=body.description,
        icon_url=body.icon_url,
        source=body.source,
        source_url=body.source_url,
        source_image=body.source_image,
        source_repo=body.source_repo,
        source_tag=body.source_tag,
        source_manifest=body.source_manifest,
        source_hash=body.source_hash,
        category=body.category,
        risk_level=body.risk_level,
        requires_vm=body.requires_vm,
        network_policy=body.network_policy,
        resource_limits=body.resource_limits,
        capabilities=body.capabilities,
        installed=False,
        created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return s.AppOut(
        id=app.id,
        name=app.name,
        slug=app.slug,
        description=app.description,
        icon_url=app.icon_url,
        source=app.source,
        source_url=app.source_url,
        category=app.category,
        risk_level=app.risk_level,
        requires_vm=app.requires_vm,
        installed=app.installed,
        versions=[],
        created_at=app.created_at,
    )


@router.put("/{slug}", response_model=s.AppOut)
async def update_app(slug: str, body: s.AppUpdate, db: Session = Depends(_get_db)):
    """Update an app."""
    app = db.execute(select(App).where(App.slug == slug)).scalar_one_or_none()
    if not app:
        raise HTTPException(404, f"App '{slug}' not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(app, field, value)

    app.updated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    db.commit()
    db.refresh(app)
    return s.AppOut(
        id=app.id,
        name=app.name,
        slug=app.slug,
        description=app.description,
        icon_url=app.icon_url,
        source=app.source,
        source_url=app.source_url,
        category=app.category,
        risk_level=app.risk_level,
        requires_vm=app.requires_vm,
        installed=app.installed,
        versions=[s.AppVersionOut(
            id=v.id,
            version=v.version,
            image_ref=v.image_ref,
            image_digest=v.image_digest,
            manifest=v.manifest,
            provenance=v.provenance,
            is_current=v.is_current,
        ) for v in app.versions],
        created_at=app.created_at,
    )


@router.delete("/{slug}", status_code=204)
async def delete_app(slug: str, db: Session = Depends(_get_db)):
    """Delete an app (with confirmation)."""
    app = db.execute(select(App).where(App.slug == slug)).scalar_one_or_none()
    if not app:
        raise HTTPException(404, f"App '{slug}' not found")

    # Cannot delete if installed (requires explicit approval)
    if app.installed:
        raise HTTPException(400, "App is installed. Remove before deleting.")

    db.delete(app)
    db.commit()
    return None
