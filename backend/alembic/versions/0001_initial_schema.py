"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    user_role = postgresql.ENUM("admin", "technician", name="user_role", create_type=False)
    device_status = postgresql.ENUM("online", "offline", "unknown", name="device_status", create_type=False)
    client_status = postgresql.ENUM(
        "active", "suspended", "cancelled", name="client_status", create_type=False
    )
    invoice_status = postgresql.ENUM(
        "pending", "paid", "overdue", "cancelled", name="invoice_status", create_type=False
    )
    for enum_type in (user_role, device_status, client_status, invoice_status):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="technician"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "mikrotik_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("site", sa.String(120)),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("api_port", sa.Integer, nullable=False, server_default="8728"),
        sa.Column("api_use_tls", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ssh_port", sa.Integer, nullable=False, server_default="22"),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("encrypted_password", sa.String(500), nullable=False),
        sa.Column("model", sa.String(120)),
        sa.Column("routeros_version", sa.String(60)),
        sa.Column("status", device_status, nullable=False, server_default="unknown"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("download_speed_mbps", sa.Integer, nullable=False),
        sa.Column("upload_speed_mbps", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("identification", sa.String(60)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(40)),
        sa.Column("address", sa.String(255)),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id")),
        sa.Column("mikrotik_device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mikrotik_devices.id")),
        sa.Column("pppoe_username", sa.String(120)),
        sa.Column("encrypted_pppoe_password", sa.String(500)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("status", client_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", invoice_status, nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", sa.String(60), nullable=False),
        sa.Column("reference", sa.String(120)),
        sa.Column("paid_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "device_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mikrotik_devices.id"), nullable=False
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("cpu_load_percent", sa.Integer),
        sa.Column("memory_used_bytes", sa.Integer),
        sa.Column("memory_total_bytes", sa.Integer),
        sa.Column("uptime_seconds", sa.Integer),
        sa.Column("active_ppp_sessions", sa.Integer),
        sa.Column("interfaces", sa.JSON),
    )
    op.create_index("ix_device_metrics_recorded_at", "device_metrics", ["recorded_at"])
    op.create_index("ix_device_metrics_device_id", "device_metrics", ["device_id"])


def downgrade() -> None:
    op.drop_table("device_metrics")
    op.drop_table("payments")
    op.drop_table("invoices")
    op.drop_table("clients")
    op.drop_table("plans")
    op.drop_table("mikrotik_devices")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    postgresql.ENUM(name="invoice_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="client_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="device_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="user_role").drop(bind, checkfirst=True)
