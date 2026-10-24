"""Audit router: append-only operation log."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_store.db import get_session
from app_store.models import AuditLog
from app_store.routers import schemas as s

router = APIRouter(prefix="", tags=["audit"])

def _get_db():
    for session in get_session():
        yield session


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
    """Write an audit log entry (append-only)."""
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
        created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db.add(entry)
    db.commit()
    return {"status": "logged", "id": entry.id}


@router.get("/audit/failed", response_model=list[s.AuditLogOut])
async def get_failed_actions(
    limit: int = 50,
    db: Session = Depends(_get_db),
):
    """List all failed operations (for incident review)."""
    results = db.execute(
        select(AuditLog).where(AuditLog.success == False).order_by(AuditLog.id.desc()).limit(limit)
    ).scalars().all()
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
