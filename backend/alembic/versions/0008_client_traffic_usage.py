"""client traffic usage (NetFlow) + traffic_flow_configured flag on devices

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mikrotik_devices",
        sa.Column("traffic_flow_configured", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.alter_column("mikrotik_devices", "traffic_flow_configured", server_default=None)

    op.create_table(
        "client_traffic_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column(
            "device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mikrotik_devices.id"), nullable=False
        ),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bytes_in", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("bytes_out", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("packets_in", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("packets_out", sa.BigInteger, nullable=False, server_default="0"),
    )
    op.create_index("ix_client_traffic_usage_bucket_start", "client_traffic_usage", ["bucket_start"])
    op.create_unique_constraint(
        "uq_client_traffic_usage_client_bucket", "client_traffic_usage", ["client_id", "bucket_start"]
    )


def downgrade() -> None:
    op.drop_table("client_traffic_usage")
    op.drop_column("mikrotik_devices", "traffic_flow_configured")
