"""Pydantic schemas for the App Store API (separate from Pick'em's).

Public-facing request/response types. The API contract differs from Pick'em's.
"""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class PasskeyCredential(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    raw_id: bytes = Field(..., alias="rawId")
    public_key: bytes
    sign_count: int = 0
    key_type: str = "public-key"
    transports: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Apps catalog
# ---------------------------------------------------------------------------

class AppOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    icon_url: str | None
    source: str
    source_url: str
    category: str
    risk_level: str
    requires_vm: bool
    installed: bool
    versions: list["AppVersionOut"]
    created_at: str


class AppVersionOut(BaseModel):
    id: int
    version: str
    image_ref: str | None
    image_digest: str | None
    manifest: dict | None
    provenance: str
    is_current: bool


class AppCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    icon_url: str | None = None
    source: Literal["docker_registry", "github", "remote_tar"] = "docker_registry"
    source_url: str
    source_image: str | None = None
    source_repo: str | None = None
    source_tag: str | None = None
    category: str = "utility"
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_vm: bool = False
    network_policy: str = "none"
    resource_limits: dict | None = None
    capabilities: list[str] = Field(default_factory=list)


class AppUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    icon_url: str | None = None
    source_url: str | None = None
    source_image: str | None = None
    source_repo: str | None = None
    source_tag: str | None = None
    category: str | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    requires_vm: bool | None = None
    network_policy: str | None = None
    resource_limits: dict | None = None
    capabilities: list[str] | None = None


# ---------------------------------------------------------------------------
# Installer job
# ---------------------------------------------------------------------------

class InstallJobOut(BaseModel):
    id: int
    operation: str  # install|update|backup|restore|remove
    status: str
    error_class: str | None
    error_message: str | None
    operation_id: str
    idempotency_key: str | None
    target_version: str | None
    target_image: str | None
    target_container: str | None
    target_network: str | None
    target_cap_drop: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class InstallJobCreate(BaseModel):
    app_id: int
    operation: Literal["install", "update", "backup", "restore", "remove"]
    operation_id: str = Field(default_factory=lambda: uuid4().hex)
    idempotency_key: str | None = None
    target_version: str | None = None
    target_image: str | None = None


class InstallJobStart(BaseModel):
    app_id: int
    operation: Literal["install", "update", "backup", "restore", "remove"]
    operation_id: str = Field(default_factory=lambda: uuid4().hex)
    idempotency_key: str | None = None
    target_version: str | None = None
    target_image: str | None = None


# ---------------------------------------------------------------------------
# Authentication (passkey)
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    user_id: str


class RegisterResponse(BaseModel):
    credential: PasskeyCredential


class LoginRequest(BaseModel):
    credential: PasskeyCredential


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str | None = None


# ---------------------------------------------------------------------------
# Passkey enrollment
# ---------------------------------------------------------------------------

class PasskeyEnrollRequest(BaseModel):
    user_id: str


class PasskeyEnrollResponse(BaseModel):
    challenge: str
    public_key: str
    rp_id: str
    timeout: int = 60000


class PasskeyVerifyRequest(BaseModel):
    credential: PasskeyCredential
    client_data_json: str
    authenticator_data: str


class PasskeyVerifyResponse(BaseModel):
    success: bool
    user_id: str | None = None


# ---------------------------------------------------------------------------
# Installer job control (restricted boundary)
# ---------------------------------------------------------------------------

class InstallJobStartRequest(BaseModel):
    app_id: int
    operation: Literal["install", "update", "backup", "restore", "remove"]
    operation_id: str = Field(default_factory=lambda: uuid4().hex)
    idempotency_key: str | None = None
    target_version: str | None = None
    target_image: str | None = None


class InstallJobStartResponse(BaseModel):
    job_id: int
    status: str
    operation_id: str


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

class DBHealthOut(BaseModel):
    status: str
    database: bool


# ---------------------------------------------------------------------------
# Health / dashboard
# ---------------------------------------------------------------------------

class BackupOut(BaseModel):
    id: int
    app_id: int | None
    backup_type: str
    destination: str
    snapshot_id: str | None
    snapshot_path: str | None
    status: str
    checksum: str | None
    created_at: str
    completed_at: str | None
    verified_at: str | None


class DashboardOut(BaseModel):
    apps: list[AppOut]
    installed_apps: list[AppOut]
    jobs: list["InstallJobOut"]
    backups: list["BackupOut"]
    health: dict[str, str | int]


class BackupCreate(BaseModel):
    app_id: int | None = None
    backup_type: Literal["full", "incremental", "db"] = "full"
    destination: str


class BackupStartRequest(BaseModel):
    backup: BackupCreate


class BackupStartResponse(BaseModel):
    job_id: int
    status: str
    id: int


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    id: int
    user_id: str
    action: str
    resource_type: str
    resource_id: int | None
    actor_ip: str | None
    actor_user_agent: str | None
    session_id: str | None
    operation_id: str | None
    success: bool
    error_message: str | None
    created_at: str


class AuditLogQuery(BaseModel):
    action: str | None = None
    resource_type: str | None = None
    user_id: str | None = None
    limit: int = 100
    offset: int = 0


class AuditLogEvent(BaseModel):
    user_id: str
    action: str
    resource_type: str
    resource_id: int | None
    actor_ip: str | None = None
    actor_user_agent: str | None = None
    session_id: str | None = None
    operation_id: str | None = None
    success: bool
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Push notifications
# ---------------------------------------------------------------------------

class PushSubscriptionOut(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    subscription: dict


class PushSubscriptionCreate(BaseModel):
    app_id: int
    endpoint: str
    p256dh: str
    auth: str
    subscription: dict


class PushSubscriptionUpdate(BaseModel):
    endpoint: str | None = None
    p256dh: str | None = None
    auth: str | None = None
    subscription: dict | None = None


# ---------------------------------------------------------------------------
# App Credential (secrets)
# ---------------------------------------------------------------------------

class AppCredentialOut(BaseModel):
    id: int
    key: str
    algorithm: str
    created_at: str
    updated_at: str


class AppCredentialCreate(BaseModel):
    app_id: int
    key: str
    value: str
    algorithm: Literal["AES-256-GCM"] = "AES-256-GCM"


class AppCredentialUpdate(BaseModel):
    key: str | None = None
    value: str | None = None
    algorithm: Literal["AES-256-GCM"] | None = None
