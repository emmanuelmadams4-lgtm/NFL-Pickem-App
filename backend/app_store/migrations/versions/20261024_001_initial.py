"""Alembic migration for the App Store database.

Table creation: apps, app_versions, install_jobs, app_sources, app_credentials,
backups, health_checks, push_subscriptions, audit_logs, passkey_credentials.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261024_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # apps
    # ---------------------------------------------------------------------------
    op.create_table(
        "apps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("icon_url", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("source_image", sa.String(length=512), nullable=True),
        sa.Column("source_repo", sa.String(length=512), nullable=True),
        sa.Column("source_tag", sa.String(length=128), nullable=True),
        sa.Column("source_manifest", sa.JSON(), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="utility"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("requires_vm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("network_policy", sa.String(length=128), nullable=False, server_default="none"),
        sa.Column("resource_limits", sa.JSON(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("installed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("slug", name="uq_apps_slug"),
    )

    # ---------------------------------------------------------------------------
    # app_versions
    # ---------------------------------------------------------------------------
    op.create_table(
        "app_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("image_ref", sa.String(length=256), nullable=True),
        sa.Column("image_digest", sa.String(length=128), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("provenance", sa.String(length=128), nullable=False),
        sa.Column("hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("app_id", "version", name="uq_app_version"),
    )

    # ---------------------------------------------------------------------------
    # install_jobs
    # ---------------------------------------------------------------------------
    op.create_table(
        "install_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("app_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("operation_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("target_version", sa.String(length=64), nullable=True),
        sa.Column("target_image", sa.String(length=256), nullable=True),
        sa.Column("target_container", sa.String(length=128), nullable=True),
        sa.Column("target_network", sa.String(length=128), nullable=True),
        sa.Column("target_cap_drop", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.String(length=32), nullable=True),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["app_versions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("app_id", "operation", "operation_id", name="uq_install_job"),
    )

    # ---------------------------------------------------------------------------
    # app_sources
    # ---------------------------------------------------------------------------
    op.create_table(
        "app_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("source_image", sa.String(length=256), nullable=True),
        sa.Column("source_repo", sa.String(length=512), nullable=True),
        sa.Column("source_tag", sa.String(length=128), nullable=True),
        sa.Column("source_commit", sa.String(length=128), nullable=True),
        sa.Column("source_manifest", sa.JSON(), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("source_parse_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
    )

    # ---------------------------------------------------------------------------
    # app_credentials
    # ---------------------------------------------------------------------------
    op.create_table(
        "app_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False, server_default="AES-256-GCM"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("app_id", "key", name="uq_app_credential"),
    )

    # ---------------------------------------------------------------------------
    # backups
    # ---------------------------------------------------------------------------
    op.create_table(
        "backups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=True),
        sa.Column("backup_type", sa.String(length=32), nullable=False),
        sa.Column("destination", sa.String(length=256), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=True),
        sa.Column("snapshot_path", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_class", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.Column("verified_at", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
    )

    # ---------------------------------------------------------------------------
    # health_checks
    # ---------------------------------------------------------------------------
    op.create_table(
        "health_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("backup_id", sa.Integer(), sa.ForeignKey("backups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("container", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="starting"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["backup_id"], ["backups.id"], ondelete="SET NULL"),
    )

    # ---------------------------------------------------------------------------
    # push_subscriptions
    # ---------------------------------------------------------------------------
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=False),
        sa.Column("p256dh", sa.String(length=256), nullable=False),
        sa.Column("auth", sa.String(length=128), nullable=False),
        sa.Column("subscription", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("endpoint", name="uq_push_endpoint"),
    )

    # ---------------------------------------------------------------------------
    # audit_logs
    # ---------------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("actor_ip", sa.String(length=48), nullable=True),
        sa.Column("actor_user_agent", sa.String(length=256), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("operation_id", sa.String(length=128), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    )

    # ---------------------------------------------------------------------------
    # passkey_credentials
    # ---------------------------------------------------------------------------
    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("raw_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("key_type", sa.String(length=32), nullable=False, server_default="public-key"),
        sa.Column("transports", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("passkey_credentials")
    op.drop_table("audit_logs")
    op.drop_table("push_subscriptions")
    op.drop_table("health_checks")
    op.drop_table("backups")
    op.drop_table("app_credentials")
    op.drop_table("app_sources")
    op.drop_table("install_jobs")
    op.drop_table("app_versions")
    op.drop_table("apps")
