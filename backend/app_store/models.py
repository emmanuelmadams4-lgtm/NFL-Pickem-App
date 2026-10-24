"""Database models for the App Store.

Concepts:
- App: a curated application in the store (Docker image, source, description)
- AppVersion: pinned immutable version + provenance (where the image came from)
- InstallJob: durable job engine state (validate, reserve, download, provision,
  start, health-check, verify, active, failed, rolled-back)
- AppSource: where an app was imported from (Docker registry, GitHub repo, remote tar)
- AppCredential: encrypted per-app secrets injected into containers
- Backup: versioned snapshot + destination + integrity state
- PushSubscription: device push registration
- AuditLog: append-only operation log
- HealthCheck: per-app live/liveness probe result
"""

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app_store.db import Base


class App(Base):
    """A curated application in the store's catalog."""

    __tablename__ = "apps"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)  # single user
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon_url: Mapped[str | None] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # docker_registry|github|remote_tar
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_image: Mapped[str | None] = mapped_column(String(512))  # for docker_registry
    source_repo: Mapped[str | None] = mapped_column(String(512))  # for github
    source_tag: Mapped[str | None] = mapped_column(String(128))  # docker tag
    source_manifest: Mapped[dict | None] = mapped_column(JSON)
    source_hash: Mapped[str | None] = mapped_column(String(128))  # sha256 of manifest/source
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="utility")
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="low", 
        # low | medium | high (VM-isolated for high)
    )
    requires_vm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    network_policy: Mapped[str] = mapped_column(String(128), nullable=False, default="none")
    resource_limits: Mapped[dict | None] = mapped_column(JSON)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    installed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=lambda: func.strftime("%Y-%m-%dT%H:%M:%SZ", func.now()))
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=lambda: func.strftime("%Y-%m-%dT%H:%M:%SZ", func.now()))
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sources: Mapped[list["AppSource"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )
    versions: Mapped[list["AppVersion"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )
    install_jobs: Mapped[list["InstallJob"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["AppCredential"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )
    health_checks: Mapped[list["HealthCheck"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )


class AppVersion(Base):
    """Pinned immutable version of an app (manifest + image digest)."""

    __tablename__ = "app_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)  # semver
    image_ref: Mapped[str] = mapped_column(String(256))  # docker image ref
    image_digest: Mapped[str | None] = mapped_column(String(128))  # sha256 digest
    manifest: Mapped[dict | None] = mapped_column(JSON)  # container manifest
    provenance: Mapped[str] = mapped_column(String(128))  # dockerhub|github|remote
    hash: Mapped[str] = mapped_column(String(128), nullable=False)  # sha256 of source
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    app: Mapped[App] = relationship(back_populates="versions")
    install_jobs: Mapped[list["InstallJob"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("app_id", "version", name="uq_app_version"),
    )


class InstallJob(Base):
    """Durable job engine for installing / updating / backing up / restoring apps.

    States: pending -> validating -> provisioning -> downloading -> installing
    -> verifying -> active | failed | rolled_back | requires_intervention
    """

    __tablename__ = "install_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("app_versions.id", ondelete="SET NULL"), nullable=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)  # install|update|backup|restore|remove
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        # pending, validating, provisioning, downloading, installing, verifying,
        # active, failed, rolled_back, requires_intervention
    )
    error_class: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # uuid
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    target_version: Mapped[str | None] = mapped_column(String(64))
    target_image: Mapped[str | None] = mapped_column(String(256))
    target_container: Mapped[str | None] = mapped_column(String(128))
    target_network: Mapped[str | None] = mapped_column(String(128))
    target_cap_drop: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(32))
    completed_at: Mapped[str | None] = mapped_column(String(32))

    app: Mapped[App] = relationship(back_populates="install_jobs")
    version: Mapped[AppVersion | None] = relationship(back_populates="install_jobs")

    __table_args__ = (
        UniqueConstraint("app_id", "operation", "operation_id", name="uq_install_job"),
    )


class AppSource(Base):
    """Track where an app was imported from (audit + re-installable)."""

    __tablename__ = "app_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # docker_registry|github|remote_tar
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    source_image: Mapped[str | None] = mapped_column(String(256))
    source_repo: Mapped[str | None] = mapped_column(String(512))
    source_tag: Mapped[str | None] = mapped_column(String(128))
    source_commit: Mapped[str | None] = mapped_column(String(128))  # github commit SHA
    source_manifest: Mapped[dict | None] = mapped_column(JSON)
    source_hash: Mapped[str | None] = mapped_column(String(128))
    source_parse_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    app: Mapped[App] = relationship(back_populates="sources")


class AppCredential(Base):
    """Per-app encrypted credentials (secrets injected into containers)."""

    __tablename__ = "app_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="AES-256-GCM")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    app: Mapped[App] = relationship(back_populates="credentials")

    __table_args__ = (
        UniqueConstraint("app_id", "key", name="uq_app_credential"),
    )


class Backup(Base):
    """Versioned, app-aware backup snapshot."""

    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=True)
    backup_type: Mapped[str] = mapped_column(String(32), nullable=False)  # full|incremental|db
    destination: Mapped[str] = mapped_column(String(256), nullable=False)  # restic repo
    snapshot_id: Mapped[str | None] = mapped_column(String(128))
    snapshot_path: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        # pending, running, completed, failed, verified
    )
    error_class: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(128))  # sha256 of snapshot
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(32))
    verified_at: Mapped[str | None] = mapped_column(String(32))

    health_checks: Mapped[list["HealthCheck"]] = relationship(
        back_populates="backup", cascade="all, delete-orphan"
    )
class HealthCheck(Base):
    """Per-app container health probe results."""

    __tablename__ = "health_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    backup_id: Mapped[int | None] = mapped_column(
        ForeignKey("backups.id", ondelete="SET NULL"), nullable=True
    )
    container: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="starting",
        # starting, healthy, unhealthy, crashed
    )
    exit_code: Mapped[int | None] = mapped_column(Integer)
    output: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    app: Mapped[App] = relationship(back_populates="health_checks")
    backup: Mapped[Backup | None] = relationship(back_populates="health_checks")


class PushSubscription(Base):
    """Device push registration (VAPID)."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    p256dh: Mapped[str] = mapped_column(String(256), nullable=False)
    auth: Mapped[str] = mapped_column(String(128), nullable=False)
    subscription: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    app: Mapped[App] = relationship(back_populates="push_subscriptions")


class AuditLog(Base):
    """Append-only operation log (all privileged actions)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)  # install|update|backup|restore|remove|passkey_login
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)  # app|backup|job
    resource_id: Mapped[int | None] = mapped_column(Integer)
    actor_ip: Mapped[str | None] = mapped_column(String(48))
    actor_user_agent: Mapped[str | None] = mapped_column(String(256))
    session_id: Mapped[str | None] = mapped_column(String(128))
    operation_id: Mapped[str | None] = mapped_column(String(128))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class PasskeyCredential(Base):
    """Registered passkey for user authentication."""

    __tablename__ = "passkey_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_id: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, index=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    key_type: Mapped[str] = mapped_column(String(32), default="public-key")
    transports: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<PasskeyCredential(id={self.id}, user_id={self.user_id[:12]}...)>"
