"""Health and dashboard router."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_store.db import get_session
from app_store.models import App, InstallJob, Backup, HealthCheck
from app_store.routers import schemas as s

router = APIRouter(prefix="", tags=["health"])


def _get_db():
    for session in get_session():
        yield session


@router.get("/health", response_model=s.DBHealthOut)
async def db_health(db: Session = Depends(_get_db)):
    """Check the database is accessible."""
    try:
        db.execute(select(1))
        return s.DBHealthOut(status="ok", database=True)
    except Exception:
        return s.DBHealthOut(status="error", database=False)


@router.get("/dashboard", response_model=s.DashboardOut)
async def dashboard_full(db: Session = Depends(_get_db)):
    """Full dashboard: apps, installed apps, jobs, backups, health."""
    apps = db.execute(select(App)).scalars().all()
    installed = [a for a in apps if a.installed]
    jobs = db.execute(select(InstallJob)).scalars().all()
    backups = db.execute(select(Backup)).scalars().all()

    return s.DashboardOut(
        apps=[s.AppOut(
            id=a.id, name=a.name, slug=a.slug,
            description=a.description, icon_url=a.icon_url,
            source=a.source, source_url=a.source_url,
            category=a.category, risk_level=a.risk_level,
            requires_vm=a.requires_vm, installed=a.installed,
            versions=[s.AppVersionOut(
                id=v.id, version=v.version,
                image_ref=v.image_ref,
                image_digest=v.image_digest,
                manifest=v.manifest,
                provenance=v.provenance,
                is_current=v.is_current,
            ) for v in a.versions],
            created_at=a.created_at,
        ) for a in apps],
        installed_apps=[s.AppOut(
            id=a.id, name=a.name, slug=a.slug,
            description=a.description, icon_url=a.icon_url,
            source=a.source, source_url=a.source_url,
            category=a.category, risk_level=a.risk_level,
            requires_vm=a.requires_vm, installed=a.installed,
            versions=[s.AppVersionOut(
                id=v.id, version=v.version,
                image_ref=v.image_ref,
                image_digest=v.image_digest,
                manifest=v.manifest,
                provenance=v.provenance,
                is_current=v.is_current,
            ) for v in a.versions],
            created_at=a.created_at,
        ) for a in installed],
        jobs=[s.InstallJobOut(
            id=j.id, operation=j.operation, status=j.status,
            error_class=j.error_class, error_message=j.error_message,
            operation_id=j.operation_id,
            idempotency_key=j.idempotency_key,
            target_version=j.target_version,
            target_image=j.target_image,
            target_container=j.target_container,
            target_network=j.target_network,
            target_cap_drop=j.target_cap_drop,
            created_at=j.created_at, updated_at=j.updated_at,
            started_at=j.started_at, completed_at=j.completed_at,
        ) for j in jobs],
        backups=[s.BackupOut(
            id=b.id, app_id=b.app_id, backup_type=b.backup_type,
            destination=b.destination,
            snapshot_id=b.snapshot_id,
            snapshot_path=b.snapshot_path, status=b.status,
            checksum=b.checksum,
            created_at=b.created_at,
            completed_at=b.completed_at,
            verified_at=b.verified_at,
        ) for b in backups],
        health={
            "database": "ok",
            "backup_count": str(len(backups)),
            "job_count": str(len(jobs)),
            "app_count": str(len(apps)),
            "installed_count": str(len(installed)),
        },
    )
